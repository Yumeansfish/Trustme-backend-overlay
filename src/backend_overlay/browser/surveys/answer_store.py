from __future__ import annotations

import trustme_api_legacy.browser.surveys.answer_store as _legacy_answer_store

__all__ = getattr(_legacy_answer_store, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_answer_store, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_answer_store)))
