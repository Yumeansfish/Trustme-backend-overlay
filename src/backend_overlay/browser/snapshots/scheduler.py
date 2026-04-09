from __future__ import annotations

import trustme_api.browser.snapshots.scheduler as _legacy_scheduler

__all__ = getattr(_legacy_scheduler, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_scheduler, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_scheduler)))
