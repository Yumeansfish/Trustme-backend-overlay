from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "_repo_bootstrap.py"


def load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("test_repo_bootstrap", BOOTSTRAP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load bootstrap helper from {BOOTSTRAP_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discover_repo_root_uses_repo_markers():
    bootstrap = load_bootstrap_module()

    discovered = bootstrap.discover_repo_root(REPO_ROOT / "scripts" / "release" / "render_overlay_aw_server.py")

    assert discovered == REPO_ROOT
    assert bootstrap.is_repo_root(discovered) is True


def test_legacy_paths_are_derived_from_repo_root():
    bootstrap = load_bootstrap_module()

    assert bootstrap.legacy_source_root(repo_root=REPO_ROOT) == REPO_ROOT / "trustme-api"
    assert bootstrap.legacy_package_root(repo_root=REPO_ROOT) == REPO_ROOT / "trustme-api" / "trustme_api"


def test_ensure_repo_import_paths_only_adds_src_root():
    bootstrap = load_bootstrap_module()

    original_sys_path = list(sys.path)
    try:
        sys.path = [entry for entry in sys.path if entry not in {str(REPO_ROOT / "src"), str(REPO_ROOT / "trustme-api")}]
        bootstrap.ensure_repo_import_paths(repo_root=REPO_ROOT)

        assert sys.path[0] == str(REPO_ROOT / "src")
        assert str(REPO_ROOT / "trustme-api") not in sys.path
    finally:
        sys.path[:] = original_sys_path


def test_resolve_module_file_uses_import_spec_without_importing_dependencies():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("trustme_api.main", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "trustme-api" / "trustme_api" / "main.py"


def test_resolve_backend_overlay_module_file_uses_overlay_entrypoint():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("backend_overlay.main", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "src" / "backend_overlay" / "main.py"


def test_resolve_backend_overlay_api_module_file_uses_overlay_entrypoint():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("backend_overlay.api", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "src" / "backend_overlay" / "api.py"


def test_resolve_backend_overlay_app_package_uses_overlay_entrypoint():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("backend_overlay.app", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "src" / "backend_overlay" / "app" / "__init__.py"


def test_resolve_backend_overlay_browser_package_uses_overlay_entrypoint():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("backend_overlay.browser", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "src" / "backend_overlay" / "browser" / "__init__.py"


def test_resolve_backend_overlay_dashboard_dto_module_uses_overlay_entrypoint():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("backend_overlay.browser.dashboard_dto", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "src" / "backend_overlay" / "browser" / "dashboard_dto.py"


def test_resolve_backend_overlay_feature_packages_use_overlay_entrypoints():
    bootstrap = load_bootstrap_module()

    assert bootstrap.resolve_module_file("backend_overlay.browser.dashboard", repo_root=REPO_ROOT) == (
        REPO_ROOT / "src" / "backend_overlay" / "browser" / "dashboard" / "__init__.py"
    )
    assert bootstrap.resolve_module_file("backend_overlay.browser.settings", repo_root=REPO_ROOT) == (
        REPO_ROOT / "src" / "backend_overlay" / "browser" / "settings" / "__init__.py"
    )
    assert bootstrap.resolve_module_file("backend_overlay.browser.surveys", repo_root=REPO_ROOT) == (
        REPO_ROOT / "src" / "backend_overlay" / "browser" / "surveys" / "__init__.py"
    )
    assert bootstrap.resolve_module_file("backend_overlay.browser.canonical", repo_root=REPO_ROOT) == (
        REPO_ROOT / "src" / "backend_overlay" / "browser" / "canonical" / "__init__.py"
    )
    assert bootstrap.resolve_module_file("backend_overlay.browser.snapshots", repo_root=REPO_ROOT) == (
        REPO_ROOT / "src" / "backend_overlay" / "browser" / "snapshots" / "__init__.py"
    )


def test_resolve_backend_overlay_script_dependency_modules_use_overlay_entrypoints():
    bootstrap = load_bootstrap_module()

    expected = {
        "backend_overlay.app.config": REPO_ROOT / "src" / "backend_overlay" / "app" / "config.py",
        "backend_overlay.storage": REPO_ROOT / "src" / "backend_overlay" / "storage.py",
        "backend_overlay.browser.canonical.repository": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "canonical"
        / "repository.py",
        "backend_overlay.browser.canonical.strategy": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "canonical"
        / "strategy.py",
        "backend_overlay.browser.canonical.units": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "canonical"
        / "units.py",
        "backend_overlay.browser.dashboard.scope_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "scope_service.py",
        "backend_overlay.browser.snapshots.invalidation_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "invalidation_service.py",
        "backend_overlay.browser.snapshots.warmup_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "warmup_service.py",
        "backend_overlay.browser.surveys.sync": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "sync.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_backend_overlay_runtime_entrypoints_use_overlay_shims():
    bootstrap = load_bootstrap_module()

    expected = {
        "backend_overlay.__about__": REPO_ROOT / "src" / "backend_overlay" / "__about__.py",
        "backend_overlay.exceptions": REPO_ROOT / "src" / "backend_overlay" / "exceptions.py",
        "backend_overlay.app.custom_static": REPO_ROOT / "src" / "backend_overlay" / "app" / "custom_static.py",
        "backend_overlay.app.log": REPO_ROOT / "src" / "backend_overlay" / "app" / "log.py",
        "backend_overlay.app.rest": REPO_ROOT / "src" / "backend_overlay" / "app" / "rest.py",
        "backend_overlay.app.server": REPO_ROOT / "src" / "backend_overlay" / "app" / "server.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_backend_overlay_primary_feature_modules_use_overlay_shims():
    bootstrap = load_bootstrap_module()

    expected = {
        "backend_overlay.browser.dashboard.checkins_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "checkins_service.py",
        "backend_overlay.browser.dashboard.controller": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "controller.py",
        "backend_overlay.browser.dashboard.details_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "details_service.py",
        "backend_overlay.browser.dashboard.dto": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "dto.py",
        "backend_overlay.browser.dashboard.public_names": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "public_names.py",
        "backend_overlay.browser.dashboard.repository": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "repository.py",
        "backend_overlay.browser.dashboard.service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "service.py",
        "backend_overlay.browser.settings.repository": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "settings"
        / "repository.py",
        "backend_overlay.browser.settings.schema": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "settings"
        / "schema.py",
        "backend_overlay.browser.settings.service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "settings"
        / "service.py",
        "backend_overlay.browser.surveys.controller": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "controller.py",
        "backend_overlay.browser.surveys.dto": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "dto.py",
        "backend_overlay.browser.surveys.remote_config": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "remote_config.py",
        "backend_overlay.browser.surveys.remote_sync": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "remote_sync.py",
        "backend_overlay.browser.surveys.repository": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "repository.py",
        "backend_overlay.browser.surveys.result_export": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "result_export.py",
        "backend_overlay.browser.surveys.service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "service.py",
        "backend_overlay.browser.surveys.survey_template": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "survey_template.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_backend_overlay_snapshot_modules_use_overlay_shims():
    bootstrap = load_bootstrap_module()

    expected = {
        "backend_overlay.browser.snapshots.categories": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "categories.py",
        "backend_overlay.browser.snapshots.models": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "models.py",
        "backend_overlay.browser.snapshots.repository": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "repository.py",
        "backend_overlay.browser.snapshots.response_mapper": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "response_mapper.py",
        "backend_overlay.browser.snapshots.scheduler": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "scheduler.py",
        "backend_overlay.browser.snapshots.scope": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "scope.py",
        "backend_overlay.browser.snapshots.segments": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "segments.py",
        "backend_overlay.browser.snapshots.summary_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "summary_service.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_trustme_api_import_works_with_only_src_on_sys_path():
    script = f"""
import sys
from pathlib import Path
repo_root = Path({str(REPO_ROOT)!r})
sys.path = [str(repo_root / "src")] + [entry for entry in sys.path if entry not in {{str(repo_root / "src"), str(repo_root / "trustme-api")}}]
import trustme_api
from trustme_api.browser.settings import schema
print(trustme_api.__file__)
print(schema.__file__)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    output_lines = completed.stdout.strip().splitlines()

    assert output_lines[0].endswith("src/trustme_api/__init__.py")
    assert output_lines[1].endswith("trustme-api/trustme_api/browser/settings/schema.py")
