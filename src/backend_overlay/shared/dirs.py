from __future__ import annotations

import trustme_api_legacy.shared.dirs as _legacy_dirs

__all__ = getattr(_legacy_dirs, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_dirs, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_dirs)))
