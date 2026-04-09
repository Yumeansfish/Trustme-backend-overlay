from __future__ import annotations

import trustme_api_legacy.browser.surveys.questionnaire as _legacy_questionnaire

__all__ = getattr(_legacy_questionnaire, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_questionnaire, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_questionnaire)))
