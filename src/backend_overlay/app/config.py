from __future__ import annotations

import trustme_api_legacy.app.config as _legacy_config

__all__ = getattr(_legacy_config, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_config, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_config)))
