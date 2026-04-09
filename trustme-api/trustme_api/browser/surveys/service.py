from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import quote

from .dto import SurveyBundleDTO, SurveyInstanceDTO, SurveyVideoDTO
from .survey_template import FIXED_SURVEY_TEMPLATE_ID, load_fixed_survey_template
from .sync import ALLOWED_VIDEO_SUFFIXES, default_survey_video_cache_dir

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
