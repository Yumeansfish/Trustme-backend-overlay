from __future__ import annotations

import trustme_api_legacy.browser.surveys.dto as _legacy_dto

__all__ = getattr(_legacy_dto, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_dto, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_dto)))
