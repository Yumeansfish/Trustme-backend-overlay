from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_SURVEY_REMOTE_HOST = "uc-workstation"
DEFAULT_SURVEY_VIDEO_REMOTE_DIR = "~/highlights"
DEFAULT_SURVEY_RESULT_REMOTE_PATH = "~/result.csv"


@dataclass(frozen=True)
class SurveyVideoRemoteConfig:
    remote_host: str
    remote_dir: str


@dataclass(frozen=True)
class SurveyResultRemoteConfig:
    remote_host: str
    remote_path: str


def default_survey_remote_host() -> str:
    return os.getenv("TRUSTME_SURVEY_REMOTE_HOST", DEFAULT_SURVEY_REMOTE_HOST)


def default_survey_video_remote_host() -> str:
    return os.getenv("TRUSTME_SURVEY_VIDEO_REMOTE_HOST") or default_survey_remote_host()


def default_survey_video_remote_dir() -> str:
    return os.getenv("TRUSTME_SURVEY_VIDEO_REMOTE_DIR", DEFAULT_SURVEY_VIDEO_REMOTE_DIR)


def default_result_csv_remote_host() -> str:
    return os.getenv("TRUSTME_SURVEY_RESULT_REMOTE_HOST") or default_survey_remote_host()


def default_result_csv_remote_path() -> str:
    return os.getenv("TRUSTME_SURVEY_RESULT_REMOTE_PATH", DEFAULT_SURVEY_RESULT_REMOTE_PATH)


def resolve_survey_video_remote_config(
    *,
    remote_host: str | None = None,
    remote_dir: str | None = None,
) -> SurveyVideoRemoteConfig:
    return SurveyVideoRemoteConfig(
        remote_host=remote_host or default_survey_video_remote_host(),
        remote_dir=remote_dir or default_survey_video_remote_dir(),
    )


def resolve_survey_result_remote_config(
    *,
    remote_host: str | None = None,
    remote_path: str | None = None,
) -> SurveyResultRemoteConfig:
    return SurveyResultRemoteConfig(
        remote_host=remote_host or default_result_csv_remote_host(),
        remote_path=remote_path or default_result_csv_remote_path(),
    )
