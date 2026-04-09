from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from trustme_api.shared.dirs import get_config_dir
except ModuleNotFoundError:  # pragma: no cover - overlay-only fallback
    def get_config_dir(appname: str) -> str:
        fallback = Path.home() / ".config" / appname
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


def default_settings_path(*, testing: bool) -> Path:
    filename = "settings.json" if not testing else "settings-testing.json"
    return Path(get_config_dir("aw-server")) / filename


class SettingsRepository:
    def __init__(self, *, testing: bool, path: Path | None = None) -> None:
        self.path = path or default_settings_path(testing=testing)

    def exists(self) -> bool:
        return self.path.exists()

    def load_data(self) -> Dict[str, Any]:
        if not self.exists():
            return {}

        with self.path.open() as handle:
            return json.load(handle)

    def save_data(self, payload: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as handle:
            json.dump(payload, handle, indent=4)
