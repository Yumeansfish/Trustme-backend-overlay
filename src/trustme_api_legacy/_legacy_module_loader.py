from __future__ import annotations

import importlib
from types import ModuleType


def load_legacy_module(relative_path: str, alias: str) -> ModuleType:
    del relative_path
    return importlib.import_module(f"backend_overlay.{alias}")
