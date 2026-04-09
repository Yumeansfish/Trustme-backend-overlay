from __future__ import annotations

import trustme_api.browser.surveys.sync as _legacy_sync

__all__ = getattr(_legacy_sync, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_sync, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_sync)))
