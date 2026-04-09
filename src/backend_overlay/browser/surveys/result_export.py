from __future__ import annotations

import trustme_api_legacy.browser.surveys.result_export as _legacy_result_export

__all__ = getattr(_legacy_result_export, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_result_export, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_result_export)))
