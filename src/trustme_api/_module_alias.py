from __future__ import annotations

import importlib
from typing import Any, MutableMapping


def bind_overlay_module(module_globals: MutableMapping[str, Any], overlay_module_name: str) -> None:
    overlay_module = importlib.import_module(overlay_module_name)
    export_names = getattr(overlay_module, "__all__", None)
    if not export_names:
        export_names = [name for name in dir(overlay_module) if not name.startswith("_")]

    for name in export_names:
        module_globals[name] = getattr(overlay_module, name)

    def __getattr__(name):
        return getattr(overlay_module, name)

    def __dir__():
        return sorted(set(module_globals) | set(dir(overlay_module)))

    module_globals["__all__"] = list(export_names)
    module_globals["_overlay_module"] = overlay_module
    module_globals["__getattr__"] = __getattr__
    module_globals["__dir__"] = __dir__
