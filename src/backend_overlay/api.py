from __future__ import annotations

import trustme_api.api as _legacy_api

__all__ = getattr(_legacy_api, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_api, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_api)))
