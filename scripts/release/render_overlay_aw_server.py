#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path


FILE_MODULE_MAP = {
    "aw_server/main.py": "backend_overlay.main",
    "aw_server/api.py": "backend_overlay.api",
    "aw_server/exceptions.py": "backend_overlay.exceptions",
    "aw_server/dashboard_dto.py": "backend_overlay.browser.dashboard_dto",
    "aw_server/config.py": "backend_overlay.app.config",
    "aw_server/custom_static.py": "backend_overlay.app.custom_static",
    "aw_server/log.py": "backend_overlay.app.log",
    "aw_server/rest.py": "backend_overlay.app.rest",
    "aw_server/server.py": "backend_overlay.app.server",
}

DIR_MODULE_MAP = {
    "aw_server/dashboard": "backend_overlay.browser.dashboard",
    "aw_server/snapshots": "backend_overlay.browser.snapshots",
    "aw_server/settings": "backend_overlay.browser.settings",
    "aw_server/canonical": "backend_overlay.browser.canonical",
    "aw_server/surveys": "backend_overlay.browser.surveys",
}

OPTIONAL_DIR_CANDIDATES = {
    "aw_server/checkins_data": [
        ".local/checkins_data",
    ],
}

REPLACEMENTS = [
    ("from trustme_api.app import rest", "from aw_server import rest"),
    ("from trustme_api.app.config import", "from aw_server.config import"),
    ("from trustme_api.app.custom_static import", "from aw_server.custom_static import"),
    ("from trustme_api.app.log import", "from aw_server.log import"),
    ("from trustme_api.app.server import", "from aw_server.server import"),
    ("from trustme_api.api import", "from aw_server.api import"),
    ("from trustme_api.exceptions import", "from aw_server.exceptions import"),
    ("from trustme_api.query.exceptions import", "from aw_query.exceptions import"),
    ("from trustme_api.query import query2", "from aw_query import query2"),
    ("from trustme_api.shared import schema", "from aw_core import schema"),
    ("from trustme_api.shared.config import", "from aw_core.config import"),
    ("from trustme_api.shared.dirs import", "from aw_core.dirs import"),
    ("from trustme_api.shared.log import", "from aw_core.log import"),
    ("from trustme_api.shared.models import", "from aw_core.models import"),
    ("from trustme_api.storage import Datastore, get_storage_methods", "from aw_datastore import Datastore, get_storage_methods"),
    ("from trustme_api.storage import get_storage_methods", "from aw_datastore import get_storage_methods"),
    ("from trustme_api.transform import heartbeat_merge", "from aw_transform import heartbeat_merge"),
    ("trustme_api.browser.", "aw_server."),
    ("trustme_api.", "aw_server."),
]

SPEC_NEEDLE = '        (os.path.join(aw_core_path, "schemas"), "aw_core/schemas"),\n'
SPEC_INSERT_LINES = [
    '        ("aw_server/settings/settings_seed_knowledgebase.v1.json", "aw_server/settings"),\n',
    '        ("aw_server/surveys/fixed_questionnaire.v1.json", "aw_server/surveys"),\n',
]
OPTIONAL_SPEC_INSERT_LINES = {
    "aw_server/checkins_data": '        ("aw_server/checkins_data", "aw_server/checkins_data"),\n',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render overlay aw-server tree from backend overlay + upstream aw-server.")
    parser.add_argument("--backend-dir", required=True)
    parser.add_argument("--upstream-aw-server-dir", required=True)
    parser.add_argument("--frontend-artifact-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def load_repo_bootstrap(backend_dir: Path):
    bootstrap_path = backend_dir / "scripts" / "_repo_bootstrap.py"
    spec = importlib.util.spec_from_file_location("backend_release_repo_bootstrap", bootstrap_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load repo bootstrap helper from {bootstrap_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_overlay_file_map(backend_dir: Path) -> dict[str, Path]:
    repo_bootstrap = load_repo_bootstrap(backend_dir)
    return {
        relative_dst: repo_bootstrap.resolve_module_file(module_name, repo_root=backend_dir)
        for relative_dst, module_name in FILE_MODULE_MAP.items()
    }


def resolve_overlay_dir_map(backend_dir: Path) -> dict[str, Path]:
    repo_bootstrap = load_repo_bootstrap(backend_dir)
    return {
        relative_dst: repo_bootstrap.resolve_module_file(module_name, repo_root=backend_dir).parent
        for relative_dst, module_name in DIR_MODULE_MAP.items()
    }


def resolve_optional_overlay_dir_map(backend_dir: Path) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for relative_dst, candidates in OPTIONAL_DIR_CANDIDATES.items():
        for relative_src in candidates:
            candidate = (backend_dir / relative_src).resolve()
            if candidate.exists():
                resolved[relative_dst] = candidate
                break
    return resolved


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "dist", "build"))


def copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def rewrite_python_file(path: Path) -> None:
    if path.suffix != ".py":
        return
    data = path.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        data = data.replace(old, new)
    path.write_text(data, encoding="utf-8")


def rewrite_tree(path: Path) -> None:
    if path.is_file():
        rewrite_python_file(path)
        return
    for file_path in path.rglob("*.py"):
        rewrite_python_file(file_path)


def patch_aw_server_spec(path: Path, *, optional_overlay_dirs: dict[str, Path] | None = None) -> None:
    data = path.read_text(encoding="utf-8")
    if '"aw_server/settings/settings_seed_knowledgebase.v1.json"' in data:
        return
    insert_lines = [SPEC_NEEDLE, *SPEC_INSERT_LINES]
    for relative_dst in (optional_overlay_dirs or {}):
        optional_line = OPTIONAL_SPEC_INSERT_LINES.get(relative_dst)
        if optional_line is not None:
            insert_lines.append(optional_line)
    data = data.replace(SPEC_NEEDLE, "".join(insert_lines))
    path.write_text(data, encoding="utf-8")


def replace_frontend_static(frontend_artifact_dir: Path, output_dir: Path) -> None:
    static_dir = output_dir / "aw_server" / "static"
    if static_dir.exists():
        shutil.rmtree(static_dir)
    shutil.copytree(frontend_artifact_dir, static_dir)


def main() -> None:
    args = parse_args()
    backend_dir = Path(args.backend_dir).resolve()
    upstream_aw_server_dir = Path(args.upstream_aw_server_dir).resolve()
    frontend_artifact_dir = Path(args.frontend_artifact_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not upstream_aw_server_dir.is_dir():
        raise SystemExit(f"Upstream aw-server directory not found: {upstream_aw_server_dir}")
    if not frontend_artifact_dir.is_dir():
        raise SystemExit(f"Frontend artifact directory not found: {frontend_artifact_dir}")

    copy_tree(upstream_aw_server_dir, output_dir)
    file_map = resolve_overlay_file_map(backend_dir)
    dir_map = resolve_overlay_dir_map(backend_dir)
    optional_dir_map = resolve_optional_overlay_dir_map(backend_dir)

    legacy_settings_module = output_dir / "aw_server" / "settings.py"
    if legacy_settings_module.exists():
        legacy_settings_module.unlink()

    for relative_dst, src in file_map.items():
        dst = output_dir / relative_dst
        copy_path(src, dst)
        rewrite_tree(dst)

    for relative_dst, src in dir_map.items():
        dst = output_dir / relative_dst
        copy_path(src, dst)
        rewrite_tree(dst)

    for relative_dst, src in optional_dir_map.items():
        dst = output_dir / relative_dst
        copy_path(src, dst)
        rewrite_tree(dst)

    replace_frontend_static(frontend_artifact_dir, output_dir)
    patch_aw_server_spec(output_dir / "aw-server.spec", optional_overlay_dirs=optional_dir_map)


if __name__ == "__main__":
    main()
