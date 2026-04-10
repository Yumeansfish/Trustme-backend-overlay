from __future__ import annotations

from pathlib import Path

import backend_overlay.browser.settings as _overlay_settings

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_settings, "__all__", [])
__path__ = [str(PACKAGE_ROOT)]


def __getattr__(name):
    return getattr(_overlay_settings, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_settings)))
