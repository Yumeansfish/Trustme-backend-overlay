from __future__ import annotations

from pathlib import Path

import trustme_api_legacy.browser.canonical as _legacy_canonical

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_canonical, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_canonical.__path__)]


def __getattr__(name):
    return getattr(_legacy_canonical, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_canonical)))
