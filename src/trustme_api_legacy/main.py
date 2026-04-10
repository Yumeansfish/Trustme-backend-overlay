from __future__ import annotations

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def _legacy_main():
    return load_legacy_module("main.py", "main")


__all__ = []


def __getattr__(name):
    return getattr(_legacy_main(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_main())))
