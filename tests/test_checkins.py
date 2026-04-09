from pathlib import Path

from trustme_api.browser.dashboard.checkins import build_checkins_payload


def test_build_checkins_payload_uses_fixed_timeline_window(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "checkins"
    data_dir.mkdir()
    (data_dir / "2026-03-31").write_text(
        "\n".join(
            [
                "2026-03-31 10:00:00 CURRENT QUESTION: 1",
                "2026-03-31 10:00:12 FEEDBACK LEVEL: 4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("TRUSTME_CHECKINS_DIR", str(data_dir))

    payload = build_checkins_payload(date_filter="2026-03-31")

    assert payload["available_dates"] == ["2026-03-31"]
    assert len(payload["sessions"]) == 1

    session = payload["sessions"][0]
    assert session["started_at"].startswith("2026-03-31T10:00:00")
    assert session["timeline_start"].startswith("2026-03-31T09:55:00")
    assert session["timeline_end"].startswith("2026-03-31T10:05:00")
