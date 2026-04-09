from __future__ import annotations

import importlib.util
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


def test_ensure_repo_import_paths_adds_src_before_legacy_root():
    bootstrap = load_bootstrap_module()

    original_sys_path = list(sys.path)
    try:
        sys.path = [entry for entry in sys.path if entry not in {str(REPO_ROOT / "src"), str(REPO_ROOT / "trustme-api")}]
        bootstrap.ensure_repo_import_paths(repo_root=REPO_ROOT)

        assert sys.path[0] == str(REPO_ROOT / "src")
        assert sys.path[1] == str(REPO_ROOT / "trustme-api")
    finally:
        sys.path[:] = original_sys_path


def test_resolve_module_file_uses_import_spec_without_importing_dependencies():
    bootstrap = load_bootstrap_module()

    resolved = bootstrap.resolve_module_file("trustme_api.main", repo_root=REPO_ROOT)

    assert resolved == REPO_ROOT / "trustme-api" / "trustme_api" / "main.py"
