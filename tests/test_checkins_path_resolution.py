from pathlib import Path

from trustme_api.browser.dashboard import checkins_service as checkins


def _patch_checkins_get_data_dir(monkeypatch, provider) -> None:
    modules = [checkins]

    legacy_module = getattr(checkins, "_legacy_checkins_service", None)
    if legacy_module is not None:
        modules.append(legacy_module)
    overlay_module = getattr(checkins, "_overlay_module", None)
    if overlay_module is not None:
        modules.append(overlay_module)

    for module in list(modules):
        load_legacy_module = getattr(module, "_legacy_module", None)
        if load_legacy_module is not None:
            modules.append(load_legacy_module())

    for module in modules:
        monkeypatch.setattr(module, "get_data_dir", provider, raising=False)


def _module_path(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "scripts").mkdir(parents=True)
    (repo_root / "scripts" / "_repo_bootstrap.py").write_text("# marker\n", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return repo_root / "src" / "backend_overlay" / "browser" / "dashboard" / "checkins_service.py"


def test_checkins_candidates_follow_env_package_runtime_order(tmp_path: Path, monkeypatch) -> None:
    module_path = _module_path(tmp_path)
    repo_local_dir = module_path.parents[4] / ".local" / "checkins_data"
    override_dir = tmp_path / "override-checkins"
    runtime_dir = tmp_path / "runtime-data"

    monkeypatch.setenv("TRUSTME_CHECKINS_DIR", str(override_dir))
    _patch_checkins_get_data_dir(monkeypatch, lambda _: str(runtime_dir))

    candidates = checkins._checkins_data_dir_candidates(module_path)

    assert candidates == [
        override_dir,
        repo_local_dir,
        module_path.parents[1] / "checkins_data",
        module_path.parents[2] / "Resources" / "aw_server" / "checkins_data",
        module_path.parents[3] / "aw_server" / "checkins_data",
        runtime_dir / "checkins",
    ]
    assert all("Desktop/trust-me" not in str(path) for path in candidates)


def test_resolve_checkins_data_dir_prefers_repo_local_dir_over_bundled_and_runtime_dirs(tmp_path: Path, monkeypatch) -> None:
    module_path = _module_path(tmp_path)
    repo_local_dir = module_path.parents[4] / ".local" / "checkins_data"
    bundled_dir = module_path.parents[3] / "aw_server" / "checkins_data"
    runtime_dir = tmp_path / "runtime-data" / "checkins"

    repo_local_dir.mkdir(parents=True, exist_ok=True)
    (repo_local_dir / "2026-03-31").write_text("repo-local\n", encoding="utf-8")
    bundled_dir.mkdir(parents=True, exist_ok=True)
    (bundled_dir / "2026-03-31").write_text("bundled\n", encoding="utf-8")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "2026-03-31").write_text("runtime\n", encoding="utf-8")

    monkeypatch.delenv("TRUSTME_CHECKINS_DIR", raising=False)
    _patch_checkins_get_data_dir(monkeypatch, lambda _: str(tmp_path / "runtime-data"))

    assert checkins.resolve_checkins_data_dir(module_path) == repo_local_dir
