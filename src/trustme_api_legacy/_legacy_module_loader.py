from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
LEGACY_PACKAGE_ROOT = REPO_ROOT / "trustme-api" / "trustme_api"


def load_legacy_module(relative_path: str, alias: str) -> ModuleType:
    module_name = f"_trustme_api_legacy_{alias.replace('.', '_')}"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    module_path = LEGACY_PACKAGE_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Failed to load legacy module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
