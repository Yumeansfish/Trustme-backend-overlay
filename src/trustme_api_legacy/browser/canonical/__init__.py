from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[3]
LEGACY_PACKAGE_ROOT = REPO_ROOT / "trustme-api" / "trustme_api" / "browser" / "canonical"

__all__ = []
__path__ = [str(PACKAGE_ROOT)]
if LEGACY_PACKAGE_ROOT.is_dir():
    __path__.append(str(LEGACY_PACKAGE_ROOT))
