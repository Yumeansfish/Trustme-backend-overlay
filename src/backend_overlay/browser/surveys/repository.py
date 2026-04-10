from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, List, Optional

try:
    from backend_overlay.shared.dirs import get_data_dir
except ModuleNotFoundError:  # pragma: no cover - overlay-only fallback
    def get_data_dir(appname: str) -> str:
        fallback = Path.home() / ".local" / "share" / appname
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


SURVEY_ANSWER_STORE_VERSION = 1


@dataclass(frozen=True)
class StoredSurveyAnswer:
    question_id: str
    option_id: str


@dataclass(frozen=True)
class StoredSurveyVideoAnswers:
    video_id: str
    answers: List[StoredSurveyAnswer]


@dataclass(frozen=True)
class StoredSurveySubmission:
    survey_id: str
    survey_template_id: str
    video_ids: List[str]
    submitted_at: str
    global_answers: List[StoredSurveyAnswer]
    video_answers: List[StoredSurveyVideoAnswers]


class SurveyAnswerRepository:
    def __init__(self, *, testing: bool, path: Optional[Path] = None) -> None:
        filename = f"survey-answers-v{SURVEY_ANSWER_STORE_VERSION}"
        if testing:
            filename += "-testing"
        filename += ".json"
        self.path = path or Path(get_data_dir("aw-server")) / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _load(self) -> Dict[str, Dict]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _save(self, payload: Dict[str, Dict]) -> None:
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def get_submission(self, survey_id: str) -> Optional[StoredSurveySubmission]:
        payload = self._load().get(survey_id)
        if not isinstance(payload, dict):
            return None
        video_ids = payload.get("video_ids")
        normalized_video_ids = [item for item in video_ids if isinstance(item, str)] if isinstance(video_ids, list) else []
        global_answers_payload = payload.get("global_answers")
        global_answers: List[StoredSurveyAnswer] = []
        if isinstance(global_answers_payload, list):
            for answer in global_answers_payload:
                if not isinstance(answer, dict):
                    continue
                question_id = answer.get("question_id")
                option_id = answer.get("option_id")
                if isinstance(question_id, str) and isinstance(option_id, str):
                    global_answers.append(
                        StoredSurveyAnswer(
                            question_id=question_id,
                            option_id=option_id,
                        )
                    )
        video_answers_payload = payload.get("video_answers")
        video_answers: List[StoredSurveyVideoAnswers] = []
        if isinstance(video_answers_payload, list):
            for section in video_answers_payload:
                if not isinstance(section, dict):
                    continue
                video_id = section.get("video_id")
                answers_payload = section.get("answers")
                if not isinstance(video_id, str) or not isinstance(answers_payload, list):
                    continue
                answers: List[StoredSurveyAnswer] = []
                for answer in answers_payload:
                    if not isinstance(answer, dict):
                        continue
                    question_id = answer.get("question_id")
                    option_id = answer.get("option_id")
                    if isinstance(question_id, str) and isinstance(option_id, str):
                        answers.append(
                            StoredSurveyAnswer(
                                question_id=question_id,
                                option_id=option_id,
                            )
                        )
                video_answers.append(
                    StoredSurveyVideoAnswers(
                        video_id=video_id,
                        answers=answers,
                    )
                )
        elif isinstance(payload.get("answers"), list):
            legacy_answers: List[StoredSurveyAnswer] = []
            for answer in payload["answers"]:
                if not isinstance(answer, dict):
                    continue
                question_id = answer.get("question_id")
                option_id = answer.get("option_id")
                if isinstance(question_id, str) and isinstance(option_id, str):
                    legacy_answers.append(
                        StoredSurveyAnswer(
                            question_id=question_id,
                            option_id=option_id,
                        )
                    )
            if normalized_video_ids:
                video_answers.append(
                    StoredSurveyVideoAnswers(
                        video_id=normalized_video_ids[0],
                        answers=legacy_answers,
                    )
                )
        survey_template_id = payload.get("survey_template_id")
        submitted_at = payload.get("submitted_at")
        if not isinstance(survey_template_id, str) or not isinstance(submitted_at, str):
            return None
        return StoredSurveySubmission(
            survey_id=survey_id,
            survey_template_id=survey_template_id,
            video_ids=normalized_video_ids,
            submitted_at=submitted_at,
            global_answers=global_answers,
            video_answers=video_answers,
        )

    def list_completed_survey_ids(self) -> List[str]:
        payload = self._load()
        return sorted(key for key, value in payload.items() if isinstance(value, dict))

    def mark_completed(
        self,
        *,
        survey_id: str,
        survey_template_id: str,
        video_ids: Iterable[str],
        global_answers: Iterable[Dict[str, str]],
        video_answers: Iterable[Dict],
        submitted_at: Optional[str] = None,
    ) -> StoredSurveySubmission:
        normalized_global_answers = [
            StoredSurveyAnswer(
                question_id=str(answer["question_id"]),
                option_id=str(answer["option_id"]),
            )
            for answer in global_answers
            if isinstance(answer, dict)
            and isinstance(answer.get("question_id"), str)
            and isinstance(answer.get("option_id"), str)
        ]
        normalized_video_answers: List[StoredSurveyVideoAnswers] = []
        for section in video_answers:
            if not isinstance(section, dict):
                continue
            video_id = section.get("video_id")
            answers = section.get("answers")
            if not isinstance(video_id, str) or not isinstance(answers, list):
                continue
            normalized_answers = [
                StoredSurveyAnswer(
                    question_id=str(answer["question_id"]),
                    option_id=str(answer["option_id"]),
                )
                for answer in answers
                if isinstance(answer, dict)
                and isinstance(answer.get("question_id"), str)
                and isinstance(answer.get("option_id"), str)
            ]
            normalized_video_answers.append(
                StoredSurveyVideoAnswers(
                    video_id=video_id,
                    answers=normalized_answers,
                )
            )
        submission = StoredSurveySubmission(
            survey_id=survey_id,
            survey_template_id=survey_template_id,
            video_ids=[video_id for video_id in video_ids if isinstance(video_id, str)],
            submitted_at=submitted_at or datetime.now(timezone.utc).isoformat(),
            global_answers=normalized_global_answers,
            video_answers=normalized_video_answers,
        )
        with self._lock:
            payload = self._load()
            payload[survey_id] = {
                "survey_id": submission.survey_id,
                "survey_template_id": submission.survey_template_id,
                "video_ids": list(submission.video_ids),
                "submitted_at": submission.submitted_at,
                "global_answers": [
                    {
                        "question_id": answer.question_id,
                        "option_id": answer.option_id,
                    }
                    for answer in submission.global_answers
                ],
                "video_answers": [
                    {
                        "video_id": section.video_id,
                        "answers": [
                            {
                                "question_id": answer.question_id,
                                "option_id": answer.option_id,
                            }
                            for answer in section.answers
                        ],
                    }
                    for section in submission.video_answers
                ],
            }
            self._save(payload)
        return submission


SurveyAnswerStore = SurveyAnswerRepository
