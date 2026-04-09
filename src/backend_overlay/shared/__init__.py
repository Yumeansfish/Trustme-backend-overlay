from __future__ import annotations

from pathlib import Path

import trustme_api_legacy.shared as _legacy_shared

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_shared, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_legacy_shared.__path__)]


def __getattr__(name):
    return getattr(_legacy_shared, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_shared)))
