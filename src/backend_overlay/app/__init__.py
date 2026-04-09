from __future__ import annotations

from pathlib import Path

import trustme_api_legacy.app as _legacy_app

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_app, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_app.__path__)]


def __getattr__(name):
    return getattr(_legacy_app, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_app)))
