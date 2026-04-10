from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
__path__ = [str(PACKAGE_ROOT)]

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
