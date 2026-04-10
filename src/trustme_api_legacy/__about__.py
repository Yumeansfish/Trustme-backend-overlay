from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from subprocess import CalledProcessError, check_output
from typing import Optional


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]


def get_rev() -> Optional[str]:
    try:
        return (
            check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=REPO_ROOT,
                timeout=1,
            )
            .decode("ascii")
            .strip()
        )
    except (CalledProcessError, FileNotFoundError, TimeoutError):
        return None


def get_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "0.13.2"


def _resolve_version() -> str:
    rev = get_rev()
    if rev:
        return f"v{get_version('trustme-api')}.dev+{rev}"
    return f"v{get_version('trustme-api')}"


__version__ = _resolve_version()

__all__ = [
    "__version__",
    "get_rev",
    "get_version",
]
