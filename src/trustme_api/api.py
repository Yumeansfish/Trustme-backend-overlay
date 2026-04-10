from __future__ import annotations

import backend_overlay.api as _overlay_api

__all__ = getattr(_overlay_api, "__all__", [])


def __getattr__(name):
    return getattr(_overlay_api, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_api)))
