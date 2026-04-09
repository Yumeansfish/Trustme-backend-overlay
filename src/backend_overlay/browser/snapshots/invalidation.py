from __future__ import annotations

import trustme_api_legacy.browser.snapshots.invalidation as _legacy_invalidation

__all__ = getattr(_legacy_invalidation, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_invalidation, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_invalidation)))
