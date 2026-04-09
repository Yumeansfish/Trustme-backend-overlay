from __future__ import annotations

from pathlib import Path

import trustme_api.browser.surveys as _legacy_surveys

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_surveys, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_surveys.__path__)]


def __getattr__(name):
    return getattr(_legacy_surveys, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_surveys)))
