from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from subprocess import CalledProcessError, check_output
from typing import Optional


PACKAGE_DISTRIBUTION_NAME = "backend-overlay"
LEGACY_PACKAGE_DISTRIBUTION_NAME = "trustme-api"
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
    installed_version = get_installed_version(package_name)
    if installed_version is None:
        return "0.13.2"
    return installed_version


def get_installed_version(package_name: str) -> Optional[str]:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def get_package_version() -> str:
    return (
        get_installed_version(PACKAGE_DISTRIBUTION_NAME)
        or get_installed_version(LEGACY_PACKAGE_DISTRIBUTION_NAME)
        or "0.13.2"
    )


def _resolve_version() -> str:
    rev = get_rev()
    if rev:
        return f"v{get_package_version()}.dev+{rev}"
    return f"v{get_package_version()}"


__version__ = _resolve_version()

__all__ = [
    "__version__",
    "get_installed_version",
    "get_package_version",
    "get_rev",
    "get_version",
]
