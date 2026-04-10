from __future__ import annotations

from pathlib import Path

import backend_overlay.browser.canonical as _overlay_canonical

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_canonical, "__all__", [])
__path__ = [str(PACKAGE_ROOT)]


def __getattr__(name):
    return getattr(_overlay_canonical, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_canonical)))
