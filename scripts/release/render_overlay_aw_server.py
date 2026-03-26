#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


FILE_MAP = {
    "trustme-api/trustme_api/main.py": "aw_server/main.py",
    "trustme-api/trustme_api/api.py": "aw_server/api.py",
    "trustme-api/trustme_api/exceptions.py": "aw_server/exceptions.py",
    "trustme-api/trustme_api/browser/dashboard_dto.py": "aw_server/dashboard_dto.py",
    "trustme-api/trustme_api/app/config.py": "aw_server/config.py",
    "trustme-api/trustme_api/app/custom_static.py": "aw_server/custom_static.py",
    "trustme-api/trustme_api/app/log.py": "aw_server/log.py",
    "trustme-api/trustme_api/app/rest.py": "aw_server/rest.py",
    "trustme-api/trustme_api/app/server.py": "aw_server/server.py",
}

DIR_MAP = {
    "trustme-api/trustme_api/browser/dashboard": "aw_server/dashboard",
    "trustme-api/trustme_api/browser/snapshots": "aw_server/snapshots",
    "trustme-api/trustme_api/browser/settings": "aw_server/settings",
    "trustme-api/trustme_api/browser/canonical": "aw_server/canonical",
    "trustme-api/aw_server/checkins_data": "aw_server/checkins_data",
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
SPEC_INSERT = (
    '        (os.path.join(aw_core_path, "schemas"), "aw_core/schemas"),\n'
    '        ("aw_server/settings/settings_seed_knowledgebase.v1.json", "aw_server/settings"),\n'
    '        ("aw_server/checkins_data", "aw_server/checkins_data"),\n'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render overlay aw-server tree from backend overlay + upstream aw-server.")
    parser.add_argument("--backend-dir", required=True)
    parser.add_argument("--upstream-aw-server-dir", required=True)
    parser.add_argument("--frontend-artifact-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


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


def patch_aw_server_spec(path: Path) -> None:
    data = path.read_text(encoding="utf-8")
    if '"aw_server/checkins_data"' in data:
        return
    data = data.replace(SPEC_NEEDLE, SPEC_INSERT)
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

    legacy_settings_module = output_dir / "aw_server" / "settings.py"
    if legacy_settings_module.exists():
        legacy_settings_module.unlink()

    for relative_src, relative_dst in FILE_MAP.items():
        src = backend_dir / relative_src
        dst = output_dir / relative_dst
        copy_path(src, dst)
        rewrite_tree(dst)

    for relative_src, relative_dst in DIR_MAP.items():
        src = backend_dir / relative_src
        dst = output_dir / relative_dst
        copy_path(src, dst)
        rewrite_tree(dst)

    replace_frontend_static(frontend_artifact_dir, output_dir)
    patch_aw_server_spec(output_dir / "aw-server.spec")


if __name__ == "__main__":
    main()
