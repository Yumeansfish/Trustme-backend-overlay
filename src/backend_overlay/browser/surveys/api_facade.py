from pathlib import Path
from typing import Callable, Sequence

from .remote_sync import default_survey_video_cache_dir
from .repository import SurveyAnswerRepository
from .service import SurveyAPI as SurveyService, current_submission_timestamp


class SurveyAPI(SurveyService):
    def __init__(
        self,
        *,
        answer_store: SurveyAnswerRepository,
        result_csv_writer: Callable[[Sequence[Sequence[str]]], None] | None = None,
        video_cleanup: Callable[[Sequence[str]], Sequence[str]] | None = None,
    ) -> None:
        super().__init__(
            answer_store=answer_store,
            result_csv_writer=result_csv_writer,
            video_cleanup=video_cleanup,
            timestamp_provider=current_submission_timestamp,
            video_cache_dir_provider=_video_cache_dir,
        )


def _video_cache_dir() -> Path:
    return default_survey_video_cache_dir()

__all__ = [
    "SurveyAPI",
    "current_submission_timestamp",
    "default_survey_video_cache_dir",
]
