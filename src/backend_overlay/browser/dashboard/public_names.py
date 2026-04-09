from __future__ import annotations

import trustme_api_legacy.browser.dashboard.public_names as _legacy_public_names

__all__ = getattr(_legacy_public_names, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_public_names, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_public_names)))
