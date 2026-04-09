from __future__ import annotations

import trustme_api.browser.canonical.strategy as _legacy_strategy

__all__ = getattr(_legacy_strategy, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_strategy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_strategy)))
