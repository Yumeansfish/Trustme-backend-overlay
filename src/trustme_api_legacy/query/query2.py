from __future__ import annotations

from trustme_api_legacy._upstream_aw_core_bootstrap import ensure_aw_core_import_paths

ensure_aw_core_import_paths()

import aw_query.query2 as _legacy_query2

__all__ = getattr(_legacy_query2, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_query2, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_query2)))
