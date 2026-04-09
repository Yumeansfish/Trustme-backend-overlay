from __future__ import annotations

import trustme_api as _trustme_api

__all__ = getattr(_trustme_api, "__all__", [])
__path__ = list(_trustme_api.__path__)
__version__ = _trustme_api.__version__


def __getattr__(name):
    return getattr(_trustme_api, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_trustme_api)))
