from __future__ import annotations

import trustme_api.browser.dashboard.checkins as _legacy_checkins

__all__ = getattr(_legacy_checkins, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_checkins, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_checkins)))
