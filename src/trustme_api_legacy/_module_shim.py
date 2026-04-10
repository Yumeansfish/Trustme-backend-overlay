from __future__ import annotations

from typing import Any, MutableMapping

from trustme_api_legacy._legacy_module_loader import load_legacy_module


def bind_legacy_module(module_globals: MutableMapping[str, Any], relative_path: str, alias: str) -> None:
    def legacy_module():
        return load_legacy_module(relative_path, alias)

    def __getattr__(name):
        return getattr(legacy_module(), name)

    def __dir__():
        return sorted(set(module_globals) | set(dir(legacy_module())))

    module_globals["__all__"] = []
    module_globals["_legacy_module"] = legacy_module
    module_globals["__getattr__"] = __getattr__
    module_globals["__dir__"] = __dir__
