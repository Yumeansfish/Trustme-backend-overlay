from __future__ import annotations

import trustme_api_legacy.browser.dashboard.rest as _legacy_rest

__all__ = getattr(_legacy_rest, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_rest, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_rest)))
