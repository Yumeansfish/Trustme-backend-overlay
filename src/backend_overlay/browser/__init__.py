from __future__ import annotations

from pathlib import Path

import trustme_api.browser as _legacy_browser

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_browser, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_browser.__path__)]


def __getattr__(name):
    return getattr(_legacy_browser, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_browser)))
