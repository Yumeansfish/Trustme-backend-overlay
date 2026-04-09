from __future__ import annotations

import trustme_api.app.server as _legacy_server

__all__ = getattr(_legacy_server, "__all__", [])


def __getattr__(name):
    return getattr(_legacy_server, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy_server)))
