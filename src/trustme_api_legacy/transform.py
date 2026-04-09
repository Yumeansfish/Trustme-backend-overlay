from __future__ import annotations

from trustme_api_legacy._upstream_aw_core_bootstrap import ensure_aw_core_import_paths

ensure_aw_core_import_paths()

import aw_transform as _legacy_transform

__all__ = getattr(_legacy_transform, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_transform, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_transform)))
