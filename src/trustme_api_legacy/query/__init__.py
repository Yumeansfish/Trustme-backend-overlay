from __future__ import annotations

from pathlib import Path

from trustme_api_legacy._upstream_aw_core_bootstrap import ensure_aw_core_import_paths

ensure_aw_core_import_paths()

import aw_query as _legacy_query

PACKAGE_ROOT = Path(__file__).resolve().parent

__all__ = getattr(_legacy_query, "__all__", [])
__path__ = [str(PACKAGE_ROOT)]


def __getattr__(name):
    return getattr(_legacy_query, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_query)))
