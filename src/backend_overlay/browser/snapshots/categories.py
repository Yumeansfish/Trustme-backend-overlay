from __future__ import annotations

import trustme_api.browser.snapshots.categories as _legacy_categories

__all__ = getattr(_legacy_categories, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_categories, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_categories)))
