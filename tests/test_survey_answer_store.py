from pathlib import Path

from trustme_api.browser.surveys.answer_store import SurveyAnswerStore


def test_mark_completed_round_trips_submission(tmp_path: Path) -> None:
    store = SurveyAnswerStore(testing=True, path=tmp_path / "survey-answers.json")

    submission = store.mark_completed(
        survey_id="survey-2025-06-17",
        survey_template_id="avas-fixed-v1",
        video_ids=["2025-06-17T09-02-20.mov", "2025-06-17T20-15-45.mov"],
        global_answers=[
            {"question_id": "gq1", "option_id": "gq1_o2"},
        ],
        video_answers=[
            {
                "video_id": "2025-06-17T09-02-20.mov",
                "answers": [
                    {"question_id": "q1", "option_id": "q1_o2"},
                    {"question_id": "q2", "option_id": "q2_o5"},
                ],
            },
            {
                "video_id": "2025-06-17T20-15-45.mov",
                "answers": [
                    {"question_id": "q1", "option_id": "q1_o3"},
                    {"question_id": "q2", "option_id": "q2_o4"},
                ],
            },
        ],
    )

    assert submission.survey_id == "survey-2025-06-17"
    assert store.list_completed_survey_ids() == ["survey-2025-06-17"]

    loaded = store.get_submission("survey-2025-06-17")
    assert loaded is not None
    assert loaded.survey_template_id == "avas-fixed-v1"
    assert loaded.video_ids == ["2025-06-17T09-02-20.mov", "2025-06-17T20-15-45.mov"]
    assert [answer.question_id for answer in loaded.global_answers] == ["gq1"]
    assert [section.video_id for section in loaded.video_answers] == [
        "2025-06-17T09-02-20.mov",
        "2025-06-17T20-15-45.mov",
    ]
    assert [answer.question_id for answer in loaded.video_answers[0].answers] == ["q1", "q2"]
