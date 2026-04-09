from __future__ import annotations

import trustme_api.browser.snapshots.response_mapper as _legacy_response_mapper

__all__ = getattr(_legacy_response_mapper, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_response_mapper, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_response_mapper)))
