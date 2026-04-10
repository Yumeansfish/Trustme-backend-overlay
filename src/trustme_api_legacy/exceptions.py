from __future__ import annotations

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def _legacy_exceptions():
    return load_legacy_module("exceptions.py", "exceptions")


__all__ = []


def __getattr__(name):
    return getattr(_legacy_exceptions(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_exceptions())))
