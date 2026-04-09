from __future__ import annotations

import trustme_api.browser.dashboard_dto as _legacy_dashboard_dto

__all__ = getattr(_legacy_dashboard_dto, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_dashboard_dto, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_dashboard_dto)))
