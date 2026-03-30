from pathlib import Path

import pytest

from trustme_api.browser.surveys.answer_store import SurveyAnswerStore
from trustme_api.browser.surveys.api_facade import SurveyAPI
from trustme_api.browser.surveys.questionnaire import load_fixed_survey_template


def _full_video_answers(*, video_id: str):
    template = load_fixed_survey_template()
    return {
        "video_id": video_id,
        "answers": [
            {
                "question_id": question["id"],
                "option_id": question["options"][0]["id"],
            }
            for question in template["video_questions"]
        ],
    }


def _full_global_answers():
    template = load_fixed_survey_template()
    return [
        {
            "question_id": question["id"],
            "option_id": question["options"][0]["id"],
        }
        for question in template["global_questions"]
    ]


def test_submit_answers_marks_multi_video_survey_completed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "2025-06-17T09-02-20.mov").write_bytes(b"video")
    (tmp_path / "2025-06-17T20-15-45.mov").write_bytes(b"video")

    monkeypatch.setattr(
        "trustme_api.browser.surveys.api_facade.default_survey_video_cache_dir",
        lambda: tmp_path,
    )

    store = SurveyAnswerStore(testing=True, path=tmp_path / "survey-answers.json")
    captured_rows = []
    cleaned_video_ids = []
    api = SurveyAPI(
        answer_store=store,
        result_csv_writer=lambda rows: captured_rows.extend(rows),
        video_cleanup=lambda video_ids: cleaned_video_ids.extend(video_ids),
    )

    response = api.submit_answers(
        survey_id="survey-2025-06-17",
        global_answers=_full_global_answers(),
        video_answers=[
            _full_video_answers(video_id="2025-06-17T09-02-20.mov"),
            _full_video_answers(video_id="2025-06-17T20-15-45.mov"),
        ],
    )

    assert response["survey_id"] == "survey-2025-06-17"
    assert response["status"] == "completed"
    assert store.list_completed_survey_ids() == ["survey-2025-06-17"]
    assert len(captured_rows) == 1 + 2 * len(load_fixed_survey_template()["video_questions"])
    assert captured_rows[0][1] == ""
    assert cleaned_video_ids == [
        "2025-06-17T09-02-20.mov",
        "2025-06-17T20-15-45.mov",
    ]


def test_submit_answers_rejects_incomplete_video_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "2025-06-17T09-02-20.mov").write_bytes(b"video")
    (tmp_path / "2025-06-17T20-15-45.mov").write_bytes(b"video")

    monkeypatch.setattr(
        "trustme_api.browser.surveys.api_facade.default_survey_video_cache_dir",
        lambda: tmp_path,
    )

    store = SurveyAnswerStore(testing=True, path=tmp_path / "survey-answers.json")
    api = SurveyAPI(answer_store=store, result_csv_writer=lambda rows: None)

    with pytest.raises(ValueError, match="Incomplete video coverage"):
        api.submit_answers(
            survey_id="survey-2025-06-17",
            global_answers=_full_global_answers(),
            video_answers=[
                _full_video_answers(video_id="2025-06-17T09-02-20.mov"),
            ],
        )


def test_submit_answers_returns_existing_completion_without_rewriting_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "2025-06-17T09-02-20.mov").write_bytes(b"video")
    (tmp_path / "2025-06-17T20-15-45.mov").write_bytes(b"video")

    monkeypatch.setattr(
        "trustme_api.browser.surveys.api_facade.default_survey_video_cache_dir",
        lambda: tmp_path,
    )

    store = SurveyAnswerStore(testing=True, path=tmp_path / "survey-answers.json")
    submitted = store.mark_completed(
        survey_id="survey-2025-06-17",
        survey_template_id="avas-fixed-v1",
        video_ids=["2025-06-17T09-02-20.mov", "2025-06-17T20-15-45.mov"],
        global_answers=_full_global_answers(),
        video_answers=[
            _full_video_answers(video_id="2025-06-17T09-02-20.mov"),
            _full_video_answers(video_id="2025-06-17T20-15-45.mov"),
        ],
        submitted_at="2026-03-30T10:00:00+00:00",
    )

    captured_rows = []
    api = SurveyAPI(
        answer_store=store,
        result_csv_writer=lambda rows: captured_rows.extend(rows),
        video_cleanup=lambda video_ids: (_ for _ in ()).throw(AssertionError("cleanup should not run")),
    )

    response = api.submit_answers(
        survey_id="survey-2025-06-17",
        global_answers=_full_global_answers(),
        video_answers=[
            _full_video_answers(video_id="2025-06-17T09-02-20.mov"),
            _full_video_answers(video_id="2025-06-17T20-15-45.mov"),
        ],
    )

    assert response["survey_id"] == submitted.survey_id
    assert response["submitted_at"] == submitted.submitted_at
    assert captured_rows == []
