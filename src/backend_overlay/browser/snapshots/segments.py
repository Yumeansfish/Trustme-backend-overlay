from __future__ import annotations

import trustme_api_legacy.browser.snapshots.segments as _legacy_segments

__all__ = getattr(_legacy_segments, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_segments, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_segments)))
