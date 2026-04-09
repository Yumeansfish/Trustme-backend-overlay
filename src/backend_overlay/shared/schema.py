from __future__ import annotations

import trustme_api_legacy.shared.schema as _legacy_schema

__all__ = getattr(_legacy_schema, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_schema, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_schema)))
