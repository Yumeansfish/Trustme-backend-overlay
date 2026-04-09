from __future__ import annotations

import trustme_api_legacy.browser.surveys.controller as _legacy_controller

__all__ = getattr(_legacy_controller, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_controller, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_controller)))
