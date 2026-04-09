from __future__ import annotations

from pathlib import Path

import trustme_api.browser.dashboard as _legacy_dashboard

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_dashboard, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_dashboard.__path__)]


def __getattr__(name):
    return getattr(_legacy_dashboard, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_dashboard)))
