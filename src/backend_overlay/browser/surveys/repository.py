from __future__ import annotations

import trustme_api_legacy.browser.surveys.repository as _legacy_repository

__all__ = getattr(_legacy_repository, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_repository, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_repository)))
