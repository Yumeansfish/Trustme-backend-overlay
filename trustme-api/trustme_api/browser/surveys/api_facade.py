from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .answer_store import SurveyAnswerStore
from .dto import SurveyAnswerSubmissionResponse, SurveyBundleDTO
from .questionnaire import FIXED_SURVEY_TEMPLATE_ID
from .result_csv import append_rows_to_remote_result_csv, build_result_csv_rows
from .service import build_fixed_survey_bundle
from .sync import cleanup_submitted_survey_videos, default_survey_video_cache_dir


class SurveyAPI:
    def __init__(
        self,
        *,
        answer_store: SurveyAnswerStore,
        result_csv_writer: Callable[[Sequence[Sequence[str]]], None] | None = None,
        video_cleanup: Callable[[Sequence[str]], Sequence[str]] | None = None,
    ) -> None:
        self.answer_store = answer_store
        self.result_csv_writer = result_csv_writer or (lambda rows: append_rows_to_remote_result_csv(rows))
        self.video_cleanup = video_cleanup or (
            lambda video_ids: cleanup_submitted_survey_videos(
                video_ids,
                local_dir=default_survey_video_cache_dir(),
            )
        )

    def bundle(self, *, date_filter: Optional[str] = None) -> SurveyBundleDTO:
        return build_fixed_survey_bundle(
            local_dir=default_survey_video_cache_dir(),
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

        submitted_at = datetime.now(timezone.utc).isoformat()
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
        return default_survey_video_cache_dir()
