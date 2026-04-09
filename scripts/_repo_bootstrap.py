from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def is_repo_root(candidate: Path) -> bool:
    return (
        (candidate / "pyproject.toml").is_file()
        and (candidate / "scripts" / "_repo_bootstrap.py").is_file()
    )


def legacy_source_root(*, repo_root: Path) -> Path:
    return repo_root / "trustme-api"


def legacy_package_root(*, repo_root: Path) -> Path:
    return legacy_source_root(repo_root=repo_root) / "trustme_api"


def discover_repo_root(anchor: Path | None = None) -> Path:
    start = (anchor or Path(__file__)).resolve()
    current = start if start.is_dir() else start.parent

    for candidate in (current, *current.parents):
        if is_repo_root(candidate):
            return candidate

    raise RuntimeError(f"Failed to locate backend repo root from {start}")


def ensure_repo_import_paths(*, repo_root: Path | None = None) -> Path:
    resolved_root = repo_root or discover_repo_root()
    import_roots = [
        resolved_root / "src",
        legacy_source_root(repo_root=resolved_root),
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
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise RuntimeError(f"Failed to resolve import spec for module {module_name}")
    if isinstance(spec.origin, str):
        return Path(spec.origin).resolve()
    if spec.submodule_search_locations:
        first_location = next(iter(spec.submodule_search_locations), None)
        if isinstance(first_location, str):
            return (Path(first_location) / "__init__.py").resolve()
    raise RuntimeError(f"Module {module_name} does not define a filesystem path")
