from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent

AW_CORE_IMPORT_ROOT_CANDIDATES = [
    WORKSPACE_ROOT / "upstream" / "activitywatch" / "aw-core",
    WORKSPACE_ROOT / "upstream" / "build" / "worktree" / "activitywatch" / "aw-core",
    WORKSPACE_ROOT
    / "upstream"
    / "build"
    / "python-3.11"
    / "lib"
    / "python3.11"
    / "site-packages",
]


def ensure_aw_core_import_paths() -> None:
    for path in reversed(AW_CORE_IMPORT_ROOT_CANDIDATES):
        if not path.exists():
            continue
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
