from __future__ import annotations

import trustme_api.browser.dashboard.scope_service as _legacy_scope_service

__all__ = getattr(_legacy_scope_service, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_scope_service, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_scope_service)))
