from __future__ import annotations

import json
from pathlib import Path

from aw_core.dirs import get_config_dir

from .settings_schema import canonicalize_setting_key, normalize_settings_data, normalize_setting_value


class Settings:
    def __init__(self, testing: bool, path: Path | None = None):
        filename = "settings.json" if not testing else "settings-testing.json"
        self.config_file = path or (Path(get_config_dir("aw-server")) / filename)
        self.load()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def load(self):
        if self.config_file.exists():
            with open(self.config_file) as f:
                raw_data = json.load(f)
        else:
            raw_data = {}

        self.data, changed = normalize_settings_data(raw_data)
        if changed and self.config_file.exists():
            self.save()

    def save(self):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self.data, f, indent=4)

    def get(self, key: str, default=None):
        if not key:
            return self.data
        return self.data.get(canonicalize_setting_key(key), default)

    def set(self, key, value):
        canonical_key = canonicalize_setting_key(key)
        if canonical_key in self.data:
            self.data[canonical_key] = normalize_setting_value(
                canonical_key,
                value,
                strict=True,
            )
        else:
            self.data[canonical_key] = value
        self.data, _ = normalize_settings_data(self.data)
        self.save()
        return canonical_key, self.data.get(canonical_key)
