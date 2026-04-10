from __future__ import annotations

from pathlib import Path

import backend_overlay.browser.surveys as _overlay_surveys

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_surveys, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_overlay_surveys.__path__)]


def __getattr__(name):
    return getattr(_overlay_surveys, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_surveys)))
