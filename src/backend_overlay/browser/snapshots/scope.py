from __future__ import annotations

import trustme_api_legacy.browser.snapshots.scope as _legacy_scope

__all__ = getattr(_legacy_scope, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_scope, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_scope)))
