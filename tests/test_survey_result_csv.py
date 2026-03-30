from trustme_api.browser.surveys.result_csv import build_result_csv_rows


def test_build_result_csv_rows_flattens_global_and_video_answers() -> None:
    rows = build_result_csv_rows(
        submitted_at="2026-03-30T12:34:56+02:00",
        survey_template={
            "global_questions": [
                {
                    "id": "gq1",
                    "text": "How many times did you sleep yesterday?",
                    "options": [
                        {"id": "gq1_o1", "label": "5-", "order": 1},
                        {"id": "gq1_o2", "label": "6", "order": 2},
                    ],
                }
            ],
            "video_questions": [
                {
                    "id": "q1",
                    "text": "How positive or negative emotions did you feel at that moment?",
                    "options": [
                        {"id": "q1_o1", "label": "-3 (negative)", "order": 1},
                        {"id": "q1_o2", "label": "0 (neutral)", "order": 2},
                    ],
                }
            ],
        },
        videos=[
            {
                "video_id": "2026-03-29T09-15-00.mov",
                "filename": "2026-03-29T09-15-00.mov",
            }
        ],
        global_answers=[{"question_id": "gq1", "option_id": "gq1_o2"}],
        video_answers=[
            {
                "video_id": "2026-03-29T09-15-00.mov",
                "answers": [{"question_id": "q1", "option_id": "q1_o2"}],
            }
        ],
    )

    assert rows == [
        [
            "2026-03-30T12:34:56+02:00",
            "",
            "How many times did you sleep yesterday?",
            "6",
        ],
        [
            "2026-03-30T12:34:56+02:00",
            "2026-03-29T09-15-00.mov",
            "How positive or negative emotions did you feel at that moment?",
            "0 (neutral)",
        ],
    ]
