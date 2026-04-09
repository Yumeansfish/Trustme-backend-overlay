from __future__ import annotations

import trustme_api_legacy.app.custom_static as _legacy_custom_static

__all__ = getattr(_legacy_custom_static, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_custom_static, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_custom_static)))
