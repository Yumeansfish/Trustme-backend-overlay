from __future__ import annotations

import trustme_api_legacy.browser.snapshots.warmup_service as _legacy_warmup_service

__all__ = getattr(_legacy_warmup_service, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_warmup_service, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_warmup_service)))
