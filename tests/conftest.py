from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "_repo_bootstrap.py"

spec = importlib.util.spec_from_file_location("backend_test_repo_bootstrap", BOOTSTRAP_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load repo bootstrap helper from {BOOTSTRAP_PATH}")

bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
bootstrap.ensure_repo_import_paths(repo_root=REPO_ROOT)
