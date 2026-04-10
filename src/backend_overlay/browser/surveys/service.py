from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import quote

from .dto import SurveyAnswerSubmissionResponse, SurveyBundleDTO, SurveyInstanceDTO, SurveyVideoDTO
from .repository import SurveyAnswerRepository
from .result_export import append_rows_to_remote_result_csv, build_result_csv_rows
from .survey_template import FIXED_SURVEY_TEMPLATE_ID, load_fixed_survey_template
from .remote_sync import (
    ALLOWED_VIDEO_SUFFIXES,
    cleanup_submitted_survey_videos,
    default_survey_video_cache_dir,
)

LOCAL_TZ = datetime.now().astimezone().tzinfo


@dataclass(frozen=True)
class LocalSurveyVideo:
    filename: str
    recorded_at: str


def _parse_recorded_at_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    try:
        parsed = datetime.strptime(stem, "%Y-%m-%dT%H-%M-%S")
    except ValueError:
        return ""
    return parsed.replace(tzinfo=LOCAL_TZ).isoformat()


def list_local_survey_videos(local_dir: Path | None = None) -> List[LocalSurveyVideo]:
    resolved_local_dir = (local_dir or default_survey_video_cache_dir()).expanduser().resolve()
    if not resolved_local_dir.exists():
        return []

    videos: List[LocalSurveyVideo] = []
    for entry in sorted(resolved_local_dir.iterdir(), key=lambda path: path.name, reverse=True):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
            continue
        videos.append(
            LocalSurveyVideo(
                filename=entry.name,
                recorded_at=_parse_recorded_at_from_filename(entry.name),
            )
        )
    return videos


def _logical_date_for_video(video: LocalSurveyVideo) -> str:
    return video.recorded_at[:10] if len(video.recorded_at) >= 10 else ""


def _build_survey_id(logical_key: str) -> str:
    return f"survey-{logical_key}"


def _build_video_url(filename: str, *, video_base_url: str) -> str:
    normalized_base_url = video_base_url.rstrip("/")
    return f"{normalized_base_url}/{quote(filename)}"


def build_fixed_survey_bundle(
    *,
    local_dir: Path | None = None,
    date_filter: Optional[str] = None,
    completed_survey_ids: Optional[Set[str]] = None,
    video_base_url: str = "/api/0/surveys/videos",
) -> SurveyBundleDTO:
    survey_template = load_fixed_survey_template()
    local_videos = list_local_survey_videos(local_dir)
    available_dates = sorted(
        {
            video.recorded_at[:10]
            for video in local_videos
            if len(video.recorded_at) >= 10
        }
    )
    completed = completed_survey_ids or set()
    grouped_videos: Dict[str, List[LocalSurveyVideo]] = {}
    for local_video in local_videos:
        logical_date = _logical_date_for_video(local_video)
        if date_filter and logical_date != date_filter:
            continue
        group_key = logical_date or Path(local_video.filename).stem
        grouped_videos.setdefault(group_key, []).append(local_video)

    survey_instances: List[SurveyInstanceDTO] = []
    for group_key in sorted(grouped_videos.keys(), reverse=True):
        group_videos = sorted(
            grouped_videos[group_key],
            key=lambda item: (item.recorded_at or item.filename, item.filename),
        )
        logical_date = _logical_date_for_video(group_videos[0])
        survey_id = _build_survey_id(group_key)
        videos: List[SurveyVideoDTO] = [
            {
                "video_id": local_video.filename,
                "filename": local_video.filename,
                "video_url": _build_video_url(local_video.filename, video_base_url=video_base_url),
                "recorded_at": local_video.recorded_at,
            }
            for local_video in group_videos
        ]
        survey_instances.append(
            {
                "survey_id": survey_id,
                "survey_template_id": FIXED_SURVEY_TEMPLATE_ID,
                "logical_date": logical_date,
                "status": "completed" if survey_id in completed else "pending",
                "videos": videos,
            }
        )

    return {
        "survey_template": survey_template,
        "available_dates": available_dates,
        "earliest_available_date": available_dates[0] if available_dates else "",
        "latest_available_date": available_dates[-1] if available_dates else "",
        "survey_instances": survey_instances,
    }


class SurveyAPI:
    def __init__(
        self,
        *,
        answer_store: SurveyAnswerRepository,
        result_csv_writer: Callable[[Sequence[Sequence[str]]], None] | None = None,
        video_cleanup: Callable[[Sequence[str]], Sequence[str]] | None = None,
        timestamp_provider: Callable[[], str] | None = None,
        video_cache_dir_provider: Callable[[], Path] | None = None,
    ) -> None:
        self.answer_store = answer_store
        self.timestamp_provider = timestamp_provider or current_submission_timestamp
        self.video_cache_dir_provider = video_cache_dir_provider or default_survey_video_cache_dir
        self.result_csv_writer = result_csv_writer or (lambda rows: append_rows_to_remote_result_csv(rows))
        self.video_cleanup = video_cleanup or (
            lambda video_ids: cleanup_submitted_survey_videos(
                video_ids,
                local_dir=self.video_cache_dir_provider(),
            )
        )

    def bundle(self, *, date_filter: Optional[str] = None) -> SurveyBundleDTO:
        return build_fixed_survey_bundle(
            local_dir=self.video_cache_dir_provider(),
            date_filter=date_filter,
            completed_survey_ids=set(self.answer_store.list_completed_survey_ids()),
        )

    def submit_answers(
        self,
        *,
        survey_id: str,
        global_answers: List[Dict[str, str]],
        video_answers: List[Dict[str, Any]],
    ) -> SurveyAnswerSubmissionResponse:
        existing_submission = self.answer_store.get_submission(survey_id)
        if existing_submission is not None:
            return {
                "survey_id": existing_submission.survey_id,
                "survey_template_id": existing_submission.survey_template_id,
                "status": "completed",
                "submitted_at": existing_submission.submitted_at,
            }

        bundle = self.bundle()
        instance = next(
            (item for item in bundle["survey_instances"] if item["survey_id"] == survey_id),
            None,
        )
        if instance is None:
            raise LookupError(f"Unknown survey_id: {survey_id}")

        global_question_ids = {question["id"] for question in bundle["survey_template"]["global_questions"]}
        global_option_ids = {
            option["id"]
            for question in bundle["survey_template"]["global_questions"]
            for option in question["options"]
        }
        video_question_ids = {question["id"] for question in bundle["survey_template"]["video_questions"]}
        video_option_ids = {
            option["id"]
            for question in bundle["survey_template"]["video_questions"]
            for option in question["options"]
        }
        required_global_question_ids = set(global_question_ids)
        required_video_question_ids = set(video_question_ids)
        instance_video_ids = [video["video_id"] for video in instance["videos"]]
        normalized_global_answers = [
            {
                "question_id": answer["question_id"],
                "option_id": answer["option_id"],
            }
            for answer in global_answers
            if isinstance(answer, dict)
            and answer.get("question_id") in global_question_ids
            and answer.get("option_id") in global_option_ids
        ]
        answered_global_question_ids = {answer["question_id"] for answer in normalized_global_answers}
        if answered_global_question_ids != required_global_question_ids:
            raise ValueError(f"Incomplete global answers for survey_id: {survey_id}")
        normalized_video_answers: List[Dict[str, Any]] = []
        seen_video_ids = set()

        for section in video_answers:
            if not isinstance(section, dict):
                continue
            video_id = section.get("video_id")
            answers = section.get("answers")
            if not isinstance(video_id, str) or not isinstance(answers, list):
                continue
            if video_id == "__legacy_single_video__":
                if len(instance_video_ids) != 1:
                    raise ValueError(
                        f"Legacy single-video submission is invalid for multi-video survey_id: {survey_id}"
                    )
                video_id = instance_video_ids[0]
            if video_id not in instance_video_ids:
                continue
            normalized_answers = [
                {
                    "question_id": answer["question_id"],
                    "option_id": answer["option_id"],
                }
                for answer in answers
                if isinstance(answer, dict)
                and answer.get("question_id") in video_question_ids
                and answer.get("option_id") in video_option_ids
            ]
            answered_question_ids = {answer["question_id"] for answer in normalized_answers}
            if answered_question_ids != required_video_question_ids:
                raise ValueError(f"Incomplete answers for video_id: {video_id}")
            normalized_video_answers.append(
                {
                    "video_id": video_id,
                    "answers": normalized_answers,
                }
            )
            seen_video_ids.add(video_id)

        if set(instance_video_ids) != seen_video_ids:
            raise ValueError(f"Incomplete video coverage for survey_id: {survey_id}")

        submitted_at = self.timestamp_provider()
        csv_rows = build_result_csv_rows(
            submitted_at=submitted_at,
            survey_template=bundle["survey_template"],
            videos=instance["videos"],
            global_answers=normalized_global_answers,
            video_answers=normalized_video_answers,
        )
        self.result_csv_writer(csv_rows)

        submission = self.answer_store.mark_completed(
            survey_id=survey_id,
            survey_template_id=FIXED_SURVEY_TEMPLATE_ID,
            video_ids=instance_video_ids,
            global_answers=normalized_global_answers,
            video_answers=normalized_video_answers,
            submitted_at=submitted_at,
        )
        response: SurveyAnswerSubmissionResponse = {
            "survey_id": submission.survey_id,
            "survey_template_id": submission.survey_template_id,
            "status": "completed",
            "submitted_at": submission.submitted_at,
        }
        cleanup_warning: str | None = None
        try:
            self.video_cleanup(instance_video_ids)
        except RuntimeError as exc:
            cleanup_warning = str(exc)
        if cleanup_warning:
            response["cleanup_warning"] = cleanup_warning
        return response

    def video_directory(self) -> Path:
        return self.video_cache_dir_provider()


def current_submission_timestamp() -> str:
    return datetime.now().astimezone().isoformat()
