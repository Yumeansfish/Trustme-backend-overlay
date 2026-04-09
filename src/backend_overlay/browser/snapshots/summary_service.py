from __future__ import annotations

import trustme_api_legacy.browser.snapshots.summary_service as _legacy_summary_service

__all__ = getattr(_legacy_summary_service, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_summary_service, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_summary_service)))
