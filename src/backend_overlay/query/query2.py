from __future__ import annotations

import trustme_api_legacy.query.query2 as _legacy_query2

__all__ = getattr(_legacy_query2, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_query2, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_query2)))
