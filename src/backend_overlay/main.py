from __future__ import annotations

import trustme_api.main as _legacy_main

__all__ = getattr(_legacy_main, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_main, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_main)))
