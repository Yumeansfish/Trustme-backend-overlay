from pathlib import Path

from trustme_api.browser.dashboard import checkins_service as checkins


def _module_path(tmp_path: Path) -> Path:
    return tmp_path / "pkg" / "trustme_api" / "browser" / "dashboard" / "checkins.py"


def test_checkins_candidates_follow_env_package_runtime_order(tmp_path: Path, monkeypatch) -> None:
    module_path = _module_path(tmp_path)
    override_dir = tmp_path / "override-checkins"
    runtime_dir = tmp_path / "runtime-data"

    monkeypatch.setenv("TRUSTME_CHECKINS_DIR", str(override_dir))
    monkeypatch.setattr(checkins, "get_data_dir", lambda _: str(runtime_dir))

    candidates = checkins._checkins_data_dir_candidates(module_path)

    assert candidates == [
        override_dir,
        module_path.parents[1] / "checkins_data",
        module_path.parents[2] / "Resources" / "aw_server" / "checkins_data",
        module_path.parents[3] / "aw_server" / "checkins_data",
        runtime_dir / "checkins",
    ]
    assert all("Desktop/trust-me" not in str(path) for path in candidates)


def test_resolve_checkins_data_dir_prefers_bundled_dir_over_runtime_dir(tmp_path: Path, monkeypatch) -> None:
    module_path = _module_path(tmp_path)
    bundled_dir = module_path.parents[3] / "aw_server" / "checkins_data"
    runtime_dir = tmp_path / "runtime-data" / "checkins"

    bundled_dir.mkdir(parents=True, exist_ok=True)
    (bundled_dir / "2026-03-31").write_text("bundled\n", encoding="utf-8")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "2026-03-31").write_text("runtime\n", encoding="utf-8")

    monkeypatch.delenv("TRUSTME_CHECKINS_DIR", raising=False)
    monkeypatch.setattr(checkins, "get_data_dir", lambda _: str(tmp_path / "runtime-data"))

    assert checkins.resolve_checkins_data_dir(module_path) == bundled_dir
