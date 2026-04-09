from __future__ import annotations

import trustme_api.browser.surveys.result_csv as _legacy_result_csv

__all__ = getattr(_legacy_result_csv, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_result_csv, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_result_csv)))
