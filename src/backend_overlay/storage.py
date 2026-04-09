from __future__ import annotations

import trustme_api.storage as _legacy_storage

__all__ = getattr(_legacy_storage, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_storage, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_storage)))
