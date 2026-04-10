from __future__ import annotations

import backend_overlay.main as _overlay_main

__all__ = getattr(_overlay_main, "__all__", [])


def __getattr__(name):
    return getattr(_overlay_main, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_main)))
