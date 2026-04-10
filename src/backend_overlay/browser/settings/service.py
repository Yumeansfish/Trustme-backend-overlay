from __future__ import annotations

from pathlib import Path

from backend_overlay.browser.settings.repository import SettingsRepository
from backend_overlay.browser.settings.schema import (
    canonicalize_setting_key,
    normalize_settings_data,
    normalize_setting_value,
)


class Settings:
    def __init__(
        self,
        testing: bool,
        path: Path | None = None,
        repository: SettingsRepository | None = None,
    ):
        self.repository = repository or SettingsRepository(testing=testing, path=path)
        self.data = {}
        self.load()

    @property
    def config_file(self) -> Path:
        return self.repository.path

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def load(self):
        raw_data = self.repository.load_data()
        self.data, changed = normalize_settings_data(raw_data)
        if changed and self.repository.exists():
            self.save()

    def save(self):
        self.repository.save_data(self.data)

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
