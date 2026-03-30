from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from flask import current_app, jsonify, request, send_from_directory
from flask_restx import Namespace, Resource, fields

from trustme_api.exceptions import BadRequest, NotFound


surveys_api = Namespace(
    "surveys",
    path="/0/surveys",
    description="Survey/video delivery endpoints.",
)


survey_answer_model = surveys_api.model(
    "SurveyAnswer",
    {
        "question_id": fields.String(required=True),
        "option_id": fields.String(required=True),
    },
)

survey_video_answers_model = surveys_api.model(
    "SurveyVideoAnswers",
    {
        "video_id": fields.String(required=True),
        "answers": fields.List(fields.Nested(survey_answer_model), required=True),
    },
)

survey_submit_model = surveys_api.model(
    "SurveySubmit",
    {
        "survey_id": fields.String(required=True),
        "global_answers": fields.List(fields.Nested(survey_answer_model), required=False),
        "video_answers": fields.List(fields.Nested(survey_video_answers_model), required=False),
        "answers": fields.List(fields.Nested(survey_answer_model), required=False),
    },
)


def _parse_answer_list(data: Dict[str, Any]) -> List[Dict[str, str]]:
    answers = data.get("answers")
    if not isinstance(answers, list):
        raise BadRequest("InvalidSurveyAnswers", "answers must be a list")
    normalized: List[Dict[str, str]] = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise BadRequest("InvalidSurveyAnswers", "answers must contain objects")
        question_id = answer.get("question_id")
        option_id = answer.get("option_id")
        if not isinstance(question_id, str) or not isinstance(option_id, str):
            raise BadRequest("InvalidSurveyAnswers", "answer fields must be strings")
        normalized.append({"question_id": question_id, "option_id": option_id})
    return normalized


def _parse_video_answers(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    video_answers = data.get("video_answers")
    if isinstance(video_answers, list):
        normalized: List[Dict[str, Any]] = []
        for section in video_answers:
            if not isinstance(section, dict):
                raise BadRequest("InvalidSurveyAnswers", "video_answers must contain objects")
            video_id = section.get("video_id")
            if not isinstance(video_id, str) or not video_id:
                raise BadRequest("InvalidSurveyAnswers", "video_id must be a string")
            normalized.append(
                {
                    "video_id": video_id,
                    "answers": _parse_answer_list(section),
                }
            )
        return normalized

    answers = data.get("answers")
    if isinstance(answers, list):
        return [
            {
                "video_id": "__legacy_single_video__",
                "answers": _parse_answer_list(data),
            }
        ]

    raise BadRequest("InvalidSurveyAnswers", "video_answers must be a list")


def _parse_global_answers(data: Dict[str, Any]) -> List[Dict[str, str]]:
    global_answers = data.get("global_answers")
    if global_answers is None:
        return []
    if not isinstance(global_answers, list):
        raise BadRequest("InvalidSurveyAnswers", "global_answers must be a list")
    return _parse_answer_list({"answers": global_answers})


@surveys_api.route("")
class SurveysResource(Resource):
    def get(self):
        date_filter = request.args.get("date") or None
        return jsonify(current_app.api.surveys.bundle(date_filter=date_filter))


@surveys_api.route("/answers")
class SurveyAnswersResource(Resource):
    @surveys_api.expect(survey_submit_model, validate=False)
    def post(self):
        data = request.get_json() or {}
        survey_id = data.get("survey_id")
        if not isinstance(survey_id, str) or not survey_id:
            raise BadRequest("InvalidSurveySubmission", "survey_id must be a string")
        try:
            result = current_app.api.surveys.submit_answers(
                survey_id=survey_id,
                global_answers=_parse_global_answers(data),
                video_answers=_parse_video_answers(data),
            )
        except ValueError as exc:
            raise BadRequest("InvalidSurveySubmission", str(exc)) from exc
        except LookupError as exc:
            raise NotFound("NoSuchSurvey", str(exc)) from exc
        except RuntimeError as exc:
            raise BadRequest("SurveyDeliveryFailed", str(exc)) from exc
        return jsonify(result)


@surveys_api.route("/videos/<path:filename>")
class SurveyVideoResource(Resource):
    def get(self, filename: str):
        directory = current_app.api.surveys.video_directory()
        path = Path(directory) / filename
        if not path.is_file():
            raise NotFound("NoSuchSurveyVideo", f"No survey video named {filename}")
        return send_from_directory(str(directory), filename, conditional=True)
