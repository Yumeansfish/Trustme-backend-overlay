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


def test_every_repo_local_module_has_backend_overlay_counterpart():
    legacy_root = REPO_ROOT / "trustme-api" / "trustme_api"
    overlay_root = REPO_ROOT / "src" / "backend_overlay"

    missing = []
    for legacy_module in sorted(legacy_root.rglob("*.py")):
        relative_path = legacy_module.relative_to(legacy_root)
        overlay_module = overlay_root / relative_path
        if not overlay_module.exists():
            missing.append(str(relative_path))

    assert missing == []


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

    assert resolved == REPO_ROOT / "src" / "trustme_api" / "main.py"


def test_resolve_public_trustme_api_shims_use_src_entrypoints():
    bootstrap = load_bootstrap_module()

    expected = {
        "trustme_api.__about__": REPO_ROOT / "src" / "trustme_api" / "__about__.py",
        "trustme_api.api": REPO_ROOT / "src" / "trustme_api" / "api.py",
        "trustme_api.exceptions": REPO_ROOT / "src" / "trustme_api" / "exceptions.py",
        "trustme_api.main": REPO_ROOT / "src" / "trustme_api" / "main.py",
        "trustme_api.storage": REPO_ROOT / "src" / "trustme_api" / "storage.py",
        "trustme_api.transform": REPO_ROOT / "src" / "trustme_api" / "transform.py",
        "trustme_api.app": REPO_ROOT / "src" / "trustme_api" / "app" / "__init__.py",
        "trustme_api.browser": REPO_ROOT / "src" / "trustme_api" / "browser" / "__init__.py",
        "trustme_api.shared": REPO_ROOT / "src" / "trustme_api" / "shared" / "__init__.py",
        "trustme_api.query": REPO_ROOT / "src" / "trustme_api" / "query" / "__init__.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_public_trustme_api_feature_packages_use_src_entrypoints():
    bootstrap = load_bootstrap_module()

    expected = {
        "trustme_api.browser.canonical": REPO_ROOT / "src" / "trustme_api" / "browser" / "canonical" / "__init__.py",
        "trustme_api.browser.dashboard": REPO_ROOT / "src" / "trustme_api" / "browser" / "dashboard" / "__init__.py",
        "trustme_api.browser.settings": REPO_ROOT / "src" / "trustme_api" / "browser" / "settings" / "__init__.py",
        "trustme_api.browser.snapshots": REPO_ROOT / "src" / "trustme_api" / "browser" / "snapshots" / "__init__.py",
        "trustme_api.browser.surveys": REPO_ROOT / "src" / "trustme_api" / "browser" / "surveys" / "__init__.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


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
        "backend_overlay.transform": REPO_ROOT / "src" / "backend_overlay" / "transform.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_backend_overlay_shared_and_query_modules_use_overlay_shims():
    bootstrap = load_bootstrap_module()

    expected = {
        "backend_overlay.shared": REPO_ROOT / "src" / "backend_overlay" / "shared" / "__init__.py",
        "backend_overlay.shared.config": REPO_ROOT / "src" / "backend_overlay" / "shared" / "config.py",
        "backend_overlay.shared.dirs": REPO_ROOT / "src" / "backend_overlay" / "shared" / "dirs.py",
        "backend_overlay.shared.log": REPO_ROOT / "src" / "backend_overlay" / "shared" / "log.py",
        "backend_overlay.shared.models": REPO_ROOT / "src" / "backend_overlay" / "shared" / "models.py",
        "backend_overlay.shared.schema": REPO_ROOT / "src" / "backend_overlay" / "shared" / "schema.py",
        "backend_overlay.query": REPO_ROOT / "src" / "backend_overlay" / "query" / "__init__.py",
        "backend_overlay.query.exceptions": REPO_ROOT / "src" / "backend_overlay" / "query" / "exceptions.py",
        "backend_overlay.query.query2": REPO_ROOT / "src" / "backend_overlay" / "query" / "query2.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_backend_overlay_primary_feature_modules_use_overlay_shims():
    bootstrap = load_bootstrap_module()

    expected = {
        "backend_overlay.browser.dashboard.api_facade": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "api_facade.py",
        "backend_overlay.browser.dashboard.api_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "api_service.py",
        "backend_overlay.browser.dashboard.availability_store": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "availability_store.py",
        "backend_overlay.browser.dashboard.checkins": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "checkins.py",
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
        "backend_overlay.browser.dashboard.details": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "details.py",
        "backend_overlay.browser.dashboard.domain_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "domain_service.py",
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
        "backend_overlay.browser.dashboard.rest": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "dashboard"
        / "rest.py",
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
        "backend_overlay.browser.surveys.answer_store": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "answer_store.py",
        "backend_overlay.browser.surveys.api_facade": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "api_facade.py",
        "backend_overlay.browser.surveys.questionnaire": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "questionnaire.py",
        "backend_overlay.browser.surveys.repository": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "repository.py",
        "backend_overlay.browser.surveys.rest": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "rest.py",
        "backend_overlay.browser.surveys.result_csv": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "surveys"
        / "result_csv.py",
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
        "backend_overlay.browser.snapshots.invalidation": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "invalidation.py",
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
        "backend_overlay.browser.snapshots.response": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "response.py",
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
        "backend_overlay.browser.snapshots.store": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "store.py",
        "backend_overlay.browser.snapshots.summary": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "summary.py",
        "backend_overlay.browser.snapshots.summary_service": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "summary_service.py",
        "backend_overlay.browser.snapshots.warmup": REPO_ROOT
        / "src"
        / "backend_overlay"
        / "browser"
        / "snapshots"
        / "warmup.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_backend_overlay_canonical_compat_modules_use_overlay_shims():
    bootstrap = load_bootstrap_module()

    assert bootstrap.resolve_module_file("backend_overlay.browser.canonical.store", repo_root=REPO_ROOT) == (
        REPO_ROOT / "src" / "backend_overlay" / "browser" / "canonical" / "store.py"
    )


def test_trustme_api_import_works_with_only_src_on_sys_path():
    script = f"""
import sys
from pathlib import Path
repo_root = Path({str(REPO_ROOT)!r})
sys.path = [str(repo_root / "src")] + [entry for entry in sys.path if entry not in {{str(repo_root / "src"), str(repo_root / "trustme-api")}}]
import trustme_api
import trustme_api.browser
import trustme_api.shared
import trustme_api.query
from trustme_api.browser.settings import schema
print(trustme_api.__file__)
print(trustme_api.browser.__file__)
print(trustme_api.shared.__file__)
print(trustme_api.query.__file__)
print(schema.__file__)
print(list(trustme_api.__path__))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    output_lines = completed.stdout.strip().splitlines()

    assert output_lines[0].endswith("src/trustme_api/__init__.py")
    assert output_lines[1].endswith("src/trustme_api/browser/__init__.py")
    assert output_lines[2].endswith("src/trustme_api/shared/__init__.py")
    assert output_lines[3].endswith("src/trustme_api/query/__init__.py")
    assert output_lines[4].endswith("src/backend_overlay/browser/settings/schema.py")
    assert "trustme-api/trustme_api" not in output_lines[5]


def test_trustme_api_bridges_upstream_aw_core_modules_with_only_src_on_sys_path():
    script = f"""
import sys
from pathlib import Path
repo_root = Path({str(REPO_ROOT)!r})
sys.path = [str(repo_root / "src")] + [entry for entry in sys.path if entry not in {{str(repo_root / "src"), str(repo_root / "trustme-api")}}]
from trustme_api.shared.dirs import get_data_dir
from trustme_api.query import query2
from trustme_api.query.exceptions import QueryException
from trustme_api.storage import Datastore, get_storage_methods
from trustme_api.transform import heartbeat_merge
import backend_overlay.storage as overlay_storage
print(get_data_dir.__module__)
print(query2.__name__)
print(QueryException.__module__)
print(Datastore.__module__)
print(get_storage_methods.__module__)
print(heartbeat_merge.__module__)
print(overlay_storage.get_storage_methods.__module__)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    output_lines = completed.stdout.strip().splitlines()

    assert output_lines == [
        "aw_core.dirs",
        "aw_query.query2",
        "aw_query.exceptions",
        "aw_datastore.datastore",
        "aw_datastore",
        "aw_transform.heartbeats",
        "aw_datastore",
    ]


def test_trustme_api_legacy_import_works_with_only_src_on_sys_path():
    script = f"""
import sys
from pathlib import Path
repo_root = Path({str(REPO_ROOT)!r})
sys.path = [str(repo_root / "src")] + [entry for entry in sys.path if entry not in {{str(repo_root / "src"), str(repo_root / "trustme-api")}}]
import trustme_api_legacy
from trustme_api_legacy.browser.settings import schema
print(trustme_api_legacy.__file__)
print(schema.__file__)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    output_lines = completed.stdout.strip().splitlines()

    assert output_lines[0].endswith("src/trustme_api_legacy/__init__.py")
    assert output_lines[1].endswith("trustme-api/trustme_api/browser/settings/schema.py")


def test_resolve_trustme_api_legacy_top_level_shims_use_src_entrypoints():
    bootstrap = load_bootstrap_module()

    expected = {
        "trustme_api_legacy.__about__": REPO_ROOT / "src" / "trustme_api_legacy" / "__about__.py",
        "trustme_api_legacy.api": REPO_ROOT / "src" / "trustme_api_legacy" / "api.py",
        "trustme_api_legacy.exceptions": REPO_ROOT / "src" / "trustme_api_legacy" / "exceptions.py",
        "trustme_api_legacy.main": REPO_ROOT / "src" / "trustme_api_legacy" / "main.py",
        "trustme_api_legacy.app": REPO_ROOT / "src" / "trustme_api_legacy" / "app" / "__init__.py",
        "trustme_api_legacy.browser": REPO_ROOT / "src" / "trustme_api_legacy" / "browser" / "__init__.py",
        "trustme_api_legacy.browser.dashboard_dto": REPO_ROOT
        / "src"
        / "trustme_api_legacy"
        / "browser"
        / "dashboard_dto.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path


def test_resolve_trustme_api_legacy_feature_packages_use_src_entrypoints():
    bootstrap = load_bootstrap_module()

    expected = {
        "trustme_api_legacy.browser.canonical": REPO_ROOT
        / "src"
        / "trustme_api_legacy"
        / "browser"
        / "canonical"
        / "__init__.py",
        "trustme_api_legacy.browser.dashboard": REPO_ROOT
        / "src"
        / "trustme_api_legacy"
        / "browser"
        / "dashboard"
        / "__init__.py",
        "trustme_api_legacy.browser.settings": REPO_ROOT
        / "src"
        / "trustme_api_legacy"
        / "browser"
        / "settings"
        / "__init__.py",
        "trustme_api_legacy.browser.snapshots": REPO_ROOT
        / "src"
        / "trustme_api_legacy"
        / "browser"
        / "snapshots"
        / "__init__.py",
        "trustme_api_legacy.browser.surveys": REPO_ROOT
        / "src"
        / "trustme_api_legacy"
        / "browser"
        / "surveys"
        / "__init__.py",
    }

    for module_name, expected_path in expected.items():
        assert bootstrap.resolve_module_file(module_name, repo_root=REPO_ROOT) == expected_path
