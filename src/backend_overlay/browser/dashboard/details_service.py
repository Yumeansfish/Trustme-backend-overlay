from __future__ import annotations

import trustme_api.browser.dashboard.details_service as _legacy_details_service

__all__ = getattr(_legacy_details_service, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_details_service, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_details_service)))
