import json

from trustme_api.browser.settings.service import Settings


def test_settings_load_rewrites_normalized_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"alwaysActivePattern": "Zoom"}), encoding="utf-8")

    settings = Settings(testing=True, path=path)

    assert settings.get("always_active_pattern") == "Zoom"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["always_active_pattern"] == "Zoom"
    assert "alwaysActivePattern" not in payload


def test_settings_set_persists_normalized_values(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(testing=True, path=path)

    normalized_key, normalized_value = settings.set("alwaysActivePattern", "Slack")

    assert normalized_key == "always_active_pattern"
    assert normalized_value == "Slack"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["always_active_pattern"] == "Slack"
