from __future__ import annotations

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def _legacy_api():
    return load_legacy_module("api.py", "api")


__all__ = []


def __getattr__(name):
    return getattr(_legacy_api(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_api())))
