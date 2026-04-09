from __future__ import annotations

import trustme_api_legacy.browser.surveys.remote_config as _legacy_remote_config

__all__ = getattr(_legacy_remote_config, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_remote_config, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_remote_config)))
