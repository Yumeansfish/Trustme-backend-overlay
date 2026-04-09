from __future__ import annotations

from pathlib import Path

import trustme_api_legacy.browser.settings as _legacy_settings

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_settings, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_settings.__path__)]


def __getattr__(name):
    return getattr(_legacy_settings, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_settings)))
