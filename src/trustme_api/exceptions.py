from __future__ import annotations

import backend_overlay.exceptions as _overlay_exceptions

__all__ = getattr(_overlay_exceptions, "__all__", [])


def __getattr__(name):
    return getattr(_overlay_exceptions, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_exceptions)))
