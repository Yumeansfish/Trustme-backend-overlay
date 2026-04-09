from __future__ import annotations

import trustme_api_legacy.browser.snapshots.response as _legacy_response

__all__ = getattr(_legacy_response, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_response, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_response)))
