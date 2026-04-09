from __future__ import annotations

import trustme_api_legacy.query.exceptions as _legacy_exceptions

__all__ = getattr(_legacy_exceptions, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_exceptions, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_exceptions)))
