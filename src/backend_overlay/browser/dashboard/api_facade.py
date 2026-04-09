from __future__ import annotations

import trustme_api.browser.dashboard.api_facade as _legacy_api_facade

__all__ = getattr(_legacy_api_facade, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_api_facade, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_api_facade)))
