from __future__ import annotations

import trustme_api_legacy.browser.snapshots.warmup as _legacy_warmup

__all__ = getattr(_legacy_warmup, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_warmup, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_warmup)))
