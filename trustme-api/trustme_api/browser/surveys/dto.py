from __future__ import annotations

from typing import List, Literal, NotRequired, TypedDict

from .questionnaire import FixedSurveyQuestion


SurveyInstanceStatus = Literal["pending", "completed"]


class SurveyTemplateDTO(TypedDict):
    survey_template_id: str
    title: str
    description: str
    global_questions: List[FixedSurveyQuestion]
    video_questions: List[FixedSurveyQuestion]
    questions: List[FixedSurveyQuestion]


class SurveyVideoDTO(TypedDict):
    video_id: str
    filename: str
    video_url: str
    recorded_at: str


class SurveyInstanceDTO(TypedDict):
    survey_id: str
    survey_template_id: str
    logical_date: str
    status: SurveyInstanceStatus
    videos: List[SurveyVideoDTO]


class SurveyBundleDTO(TypedDict):
    survey_template: SurveyTemplateDTO
    available_dates: List[str]
    earliest_available_date: str
    latest_available_date: str
    survey_instances: List[SurveyInstanceDTO]


class SurveyAnswerSubmission(TypedDict):
    question_id: str
    option_id: str


class SurveyVideoAnswerSubmission(TypedDict):
    video_id: str
    answers: List[SurveyAnswerSubmission]


class SurveyGlobalAnswerSubmission(TypedDict):
    question_id: str
    option_id: str


class SurveyAnswerSubmissionResponse(TypedDict):
    survey_id: str
    survey_template_id: str
    status: SurveyInstanceStatus
    submitted_at: str
    cleanup_warning: NotRequired[str]
