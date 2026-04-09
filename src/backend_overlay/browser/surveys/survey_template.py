from __future__ import annotations

import trustme_api_legacy.browser.surveys.survey_template as _legacy_survey_template

__all__ = getattr(_legacy_survey_template, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_survey_template, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_survey_template)))
