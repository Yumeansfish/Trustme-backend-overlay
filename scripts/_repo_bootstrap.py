from __future__ import annotations

import importlib
import sys
from pathlib import Path


def discover_repo_root(anchor: Path | None = None) -> Path:
    start = (anchor or Path(__file__)).resolve()
    current = start if start.is_dir() else start.parent

    for candidate in (current, *current.parents):
        if (candidate / "trustme-api" / "trustme_api" / "__init__.py").exists():
            return candidate

    raise RuntimeError(f"Failed to locate backend repo root from {start}")


def ensure_repo_import_paths(*, repo_root: Path | None = None) -> Path:
    resolved_root = repo_root or discover_repo_root()
    import_roots = [
        resolved_root / "src",
        resolved_root / "trustme-api",
    ]

    for path in reversed(import_roots):
        if not path.exists():
            continue
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return resolved_root


def resolve_module_file(module_name: str, *, repo_root: Path | None = None) -> Path:
    ensure_repo_import_paths(repo_root=repo_root)
    module = importlib.import_module(module_name)
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str):
        raise RuntimeError(f"Module {module_name} does not define a filesystem path")
    return Path(module_file).resolve()
