from __future__ import annotations

from pathlib import Path

import backend_overlay.query as _overlay_query

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_query, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_overlay_query.__path__)]


def __getattr__(name):
    return getattr(_overlay_query, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_query)))
