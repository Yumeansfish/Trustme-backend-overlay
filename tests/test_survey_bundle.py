from pathlib import Path

from trustme_api.browser.surveys.service import build_fixed_survey_bundle


def test_build_fixed_survey_bundle_returns_template_and_pending_instances(tmp_path: Path) -> None:
    (tmp_path / "2025-06-17T20-15-45.mov").write_bytes(b"video")
    (tmp_path / "2025-06-17T09-02-20.mov").write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    bundle = build_fixed_survey_bundle(
        local_dir=tmp_path,
        video_base_url="/api/0/surveys/videos",
    )

    assert bundle["survey_template"]["survey_template_id"] == "avas-fixed-v1"
    assert bundle["available_dates"] == ["2025-06-17"]
    assert bundle["earliest_available_date"] == "2025-06-17"
    assert bundle["latest_available_date"] == "2025-06-17"
    assert len(bundle["survey_instances"]) == 1

    first_instance = bundle["survey_instances"][0]
    assert first_instance["survey_id"] == "survey-2025-06-17"
    assert first_instance["survey_template_id"] == "avas-fixed-v1"
    assert first_instance["logical_date"] == "2025-06-17"
    assert first_instance["status"] == "pending"
    assert [video["video_id"] for video in first_instance["videos"]] == [
        "2025-06-17T09-02-20.mov",
        "2025-06-17T20-15-45.mov",
    ]
    assert first_instance["videos"][1]["video_url"] == "/api/0/surveys/videos/2025-06-17T20-15-45.mov"
    assert first_instance["videos"][1]["recorded_at"].startswith("2025-06-17T20:15:45")


def test_build_fixed_survey_bundle_handles_missing_local_cache(tmp_path: Path) -> None:
    bundle = build_fixed_survey_bundle(local_dir=tmp_path / "missing")

    assert bundle["survey_template"]["survey_template_id"] == "avas-fixed-v1"
    assert bundle["available_dates"] == []
    assert bundle["survey_instances"] == []


def test_build_fixed_survey_bundle_filters_by_date_and_applies_completed_status(tmp_path: Path) -> None:
    (tmp_path / "2025-06-17T20-15-45.mov").write_bytes(b"video")
    (tmp_path / "2025-06-18T09-02-20.mov").write_bytes(b"video")
    (tmp_path / "2025-06-18T18-20-00.mov").write_bytes(b"video")

    bundle = build_fixed_survey_bundle(
        local_dir=tmp_path,
        date_filter="2025-06-18",
        completed_survey_ids={"survey-2025-06-18"},
    )

    assert bundle["available_dates"] == ["2025-06-17", "2025-06-18"]
    assert len(bundle["survey_instances"]) == 1
    instance = bundle["survey_instances"][0]
    assert instance["survey_id"] == "survey-2025-06-18"
    assert instance["status"] == "completed"
    assert [video["video_id"] for video in instance["videos"]] == [
        "2025-06-18T09-02-20.mov",
        "2025-06-18T18-20-00.mov",
    ]
