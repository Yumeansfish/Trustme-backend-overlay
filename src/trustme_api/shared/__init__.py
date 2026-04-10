from __future__ import annotations

from pathlib import Path

import backend_overlay.shared as _overlay_shared

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_shared, "__all__", [])
__path__ = [str(PACKAGE_ROOT)]


def __getattr__(name):
    return getattr(_overlay_shared, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_shared)))
