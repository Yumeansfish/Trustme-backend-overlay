from __future__ import annotations

import trustme_api_legacy.app.log as _legacy_log

__all__ = getattr(_legacy_log, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_log, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_log)))
