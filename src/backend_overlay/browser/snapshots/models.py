from __future__ import annotations

import trustme_api_legacy.browser.snapshots.models as _legacy_models

__all__ = getattr(_legacy_models, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_models, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_models)))
