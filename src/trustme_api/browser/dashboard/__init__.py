from __future__ import annotations

from pathlib import Path

import backend_overlay.browser.dashboard as _overlay_dashboard

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_dashboard, "__all__", [])
__path__ = [str(PACKAGE_ROOT)]


def __getattr__(name):
    return getattr(_overlay_dashboard, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_dashboard)))
