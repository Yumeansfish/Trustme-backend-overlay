from __future__ import annotations

import trustme_api_legacy.__about__ as _legacy_about

__all__ = getattr(_legacy_about, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_about, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_about)))
