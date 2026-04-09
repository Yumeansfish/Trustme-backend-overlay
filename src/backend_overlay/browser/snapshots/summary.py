from __future__ import annotations

import trustme_api_legacy.browser.snapshots.summary as _legacy_summary

__all__ = getattr(_legacy_summary, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_summary, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_summary)))
