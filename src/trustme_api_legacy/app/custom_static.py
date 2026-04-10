from __future__ import annotations

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def _legacy_custom_static():
    return load_legacy_module("app/custom_static.py", "app.custom_static")


__all__ = []


def __getattr__(name):
    return getattr(_legacy_custom_static(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_custom_static())))
