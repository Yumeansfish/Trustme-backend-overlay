from __future__ import annotations

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def _legacy_config():
    return load_legacy_module("app/config.py", "app.config")


__all__ = []


def __getattr__(name):
    return getattr(_legacy_config(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_config())))
