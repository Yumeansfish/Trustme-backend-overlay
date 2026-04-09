from __future__ import annotations

from trustme_api_legacy._upstream_aw_core_bootstrap import ensure_aw_core_import_paths

ensure_aw_core_import_paths()

import aw_query.exceptions as _legacy_exceptions

__all__ = getattr(_legacy_exceptions, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_exceptions, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_exceptions)))
