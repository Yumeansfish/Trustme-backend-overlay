from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, TypedDict

try:
    from trustme_api.shared.dirs import get_data_dir
except ModuleNotFoundError:  # pragma: no cover - overlay-only fallback
    def get_data_dir(appname: str) -> str:
        fallback = Path.home() / ".local" / "share" / appname
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


FIXED_SURVEY_TEMPLATE_ID = "avas-fixed-v1"
FIXED_SURVEY_TITLE = "AVAS Questionnaire"
FIXED_SURVEY_DESCRIPTION = "Fixed survey content bundled with the trust-me backend."


class FixedSurveyOption(TypedDict):
    id: str
    label: str
    order: int


class FixedSurveyQuestion(TypedDict):
    id: str
    type: str
    text: str
    required: bool
    order: int
    options: List[FixedSurveyOption]


class FixedSurveyTemplate(TypedDict):
    survey_template_id: str
    title: str
    description: str
    global_questions: List[FixedSurveyQuestion]
    video_questions: List[FixedSurveyQuestion]
    questions: List[FixedSurveyQuestion]


def _bundled_survey_template_path(module_path: Optional[Path] = None) -> Path:
    return (module_path or Path(__file__)).resolve().with_name("fixed_questionnaire.v1.json")


def _survey_template_path_candidates(module_path: Optional[Path] = None) -> List[Path]:
    resolved_module_path = (module_path or Path(__file__)).resolve()
    candidates = [
        os.getenv("TRUSTME_SURVEY_TEMPLATE_PATH"),
        _bundled_survey_template_path(resolved_module_path),
        resolved_module_path.parents[2] / "Resources" / "aw_server" / "surveys" / "fixed_questionnaire.v1.json",
        Path(get_data_dir("aw-server")) / "surveys" / "fixed_questionnaire.v1.json",
    ]
    return [Path(candidate) for candidate in candidates if candidate]


def _questionnaire_path(module_path: Optional[Path] = None) -> Path:
    bundled_path = _bundled_survey_template_path(module_path)
    for path in _survey_template_path_candidates(module_path):
        if path.exists():
            return path
    return bundled_path


def _normalize_questions(raw_questions: object, *, question_prefix: str) -> List[FixedSurveyQuestion]:
    if not isinstance(raw_questions, list):
        return []

    questions: List[FixedSurveyQuestion] = []
    for question_index, raw_question in enumerate(raw_questions, start=1):
        if not isinstance(raw_question, dict):
            continue
        text = raw_question.get("text")
        options = raw_question.get("options")
        if not isinstance(text, str) or not isinstance(options, list):
            continue
        normalized_options: List[FixedSurveyOption] = []
        for option_index, raw_option in enumerate(options, start=1):
            if not isinstance(raw_option, str):
                continue
            normalized_options.append(
                {
                    "id": f"{question_prefix}{question_index}_o{option_index}",
                    "label": raw_option,
                    "order": option_index,
                }
            )

        questions.append(
            {
                "id": f"{question_prefix}{question_index}",
                "type": "single_choice",
                "text": text,
                "required": True,
                "order": question_index,
                "options": normalized_options,
            }
        )
    return questions


def load_fixed_survey_template() -> FixedSurveyTemplate:
    payload = json.loads(_questionnaire_path().read_text(encoding="utf-8"))
    global_questions = _normalize_questions(
        payload.get("global_questions") if isinstance(payload, dict) else None,
        question_prefix="gq",
    )
    video_questions = _normalize_questions(
        payload.get("video_questions") if isinstance(payload, dict) else payload.get("questions") if isinstance(payload, dict) else None,
        question_prefix="q",
    )

    return {
        "survey_template_id": FIXED_SURVEY_TEMPLATE_ID,
        "title": FIXED_SURVEY_TITLE,
        "description": FIXED_SURVEY_DESCRIPTION,
        "global_questions": global_questions,
        "video_questions": video_questions,
        "questions": video_questions,
    }


FIXED_SURVEY_ID = FIXED_SURVEY_TEMPLATE_ID
load_fixed_survey_manifest = load_fixed_survey_template
