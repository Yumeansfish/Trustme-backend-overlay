from __future__ import annotations

import backend_overlay.__about__ as _overlay_about

__all__ = getattr(_overlay_about, "__all__", [])


def __getattr__(name):
    return getattr(_overlay_about, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_about)))
