from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, TypedDict


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


def _questionnaire_path() -> Path:
    module_path = Path(__file__).resolve()
    workspace_path = (
        Path.home()
        / "Desktop"
        / "trust-me"
        / "backend"
        / "trustme-api"
        / "trustme_api"
        / "browser"
        / "surveys"
        / "fixed_questionnaire.v1.json"
    )
    candidates = [
        os.getenv("TRUSTME_SURVEY_TEMPLATE_PATH"),
        workspace_path,
        Path(__file__).with_name("fixed_questionnaire.v1.json"),
        module_path.parents[1] / "surveys" / "fixed_questionnaire.v1.json",
        module_path.parents[2] / "Resources" / "aw_server" / "surveys" / "fixed_questionnaire.v1.json",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return Path(__file__).with_name("fixed_questionnaire.v1.json")


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
