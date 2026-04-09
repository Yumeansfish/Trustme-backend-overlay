from __future__ import annotations

from trustme_api_legacy._upstream_aw_core_bootstrap import ensure_aw_core_import_paths

ensure_aw_core_import_paths()

import aw_core.dirs as _legacy_dirs

__all__ = getattr(_legacy_dirs, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_dirs, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_dirs)))
