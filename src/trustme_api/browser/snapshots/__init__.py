from __future__ import annotations

from pathlib import Path

import backend_overlay.browser.snapshots as _overlay_snapshots

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_overlay_snapshots, "__all__", [])
__path__ = [str(PACKAGE_ROOT), *list(_overlay_snapshots.__path__)]


def __getattr__(name):
    return getattr(_overlay_snapshots, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_overlay_snapshots)))
