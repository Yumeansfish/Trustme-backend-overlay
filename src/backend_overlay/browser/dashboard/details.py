from __future__ import annotations

import trustme_api.browser.dashboard.details as _legacy_details

__all__ = getattr(_legacy_details, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_details, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_details)))
