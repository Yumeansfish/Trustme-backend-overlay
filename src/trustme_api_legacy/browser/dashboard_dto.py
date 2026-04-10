from __future__ import annotations

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def _legacy_dashboard_dto():
    return load_legacy_module("browser/dashboard_dto.py", "browser.dashboard_dto")


__all__ = []


def __getattr__(name):
    return getattr(_legacy_dashboard_dto(), name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_dashboard_dto())))
