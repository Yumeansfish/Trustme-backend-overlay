from __future__ import annotations

import trustme_api_legacy.transform as _legacy_transform

__all__ = getattr(_legacy_transform, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_transform, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_transform)))
