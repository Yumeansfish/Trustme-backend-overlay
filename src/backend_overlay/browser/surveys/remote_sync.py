from __future__ import annotations

import trustme_api.browser.surveys.remote_sync as _legacy_remote_sync

__all__ = getattr(_legacy_remote_sync, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_remote_sync, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_remote_sync)))
