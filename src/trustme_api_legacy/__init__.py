from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
LEGACY_PACKAGE_ROOT = REPO_ROOT / "trustme-api" / "trustme_api"

__path__ = [str(PACKAGE_ROOT)]
if LEGACY_PACKAGE_ROOT.is_dir():
    __path__.append(str(LEGACY_PACKAGE_ROOT))

from .__about__ import __version__

__all__ = [
    "__version__",
    "main",
]


def __getattr__(name):
    if name == "main":
        from trustme_api_legacy.main import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
