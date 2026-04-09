from pathlib import Path
import tomllib

import backend_overlay
import backend_overlay.app as overlay_app
import backend_overlay.browser as overlay_browser
import backend_overlay.browser.canonical as overlay_canonical
import backend_overlay.browser.dashboard as overlay_dashboard
import backend_overlay.browser.settings as overlay_settings
import backend_overlay.browser.snapshots as overlay_snapshots
import backend_overlay.browser.surveys as overlay_surveys
import trustme_api
import trustme_api.app as trustme_app
import trustme_api.browser as trustme_browser
import trustme_api.browser.canonical as trustme_canonical
import trustme_api.browser.dashboard as trustme_dashboard
import trustme_api.browser.settings as trustme_settings
import trustme_api.browser.snapshots as trustme_snapshots
import trustme_api.browser.surveys as trustme_surveys

from backend_overlay.browser.surveys import survey_template as overlay_survey_template
from backend_overlay.browser.settings import schema as overlay_schema
from trustme_api_legacy.browser.settings import schema as legacy_schema
from trustme_api.browser.surveys import survey_template as trustme_survey_template
from trustme_api.browser.settings import schema as trustme_schema


def test_backend_overlay_exposes_trustme_api_metadata():
    assert backend_overlay.__version__ == trustme_api.__version__
    overlay_path = list(backend_overlay.__path__)
    trustme_path = list(trustme_api.__path__)

    assert overlay_path[0].endswith("src/backend_overlay")
    assert overlay_path[1].endswith("src/trustme_api_legacy")
    assert overlay_path[-1] == trustme_path[-1]


def test_backend_overlay_namespace_resolves_existing_subpackages():
    assert overlay_schema.__file__.endswith("src/backend_overlay/browser/settings/schema.py")
    assert overlay_schema.normalize_settings_data is legacy_schema.normalize_settings_data
    assert overlay_schema.normalize_settings_data is not trustme_schema.normalize_settings_data


def test_backend_overlay_subpackage_shims_preserve_own_package_roots():
    assert list(overlay_app.__path__)[0].endswith("src/backend_overlay/app")
    assert list(overlay_app.__path__)[1:] == list(trustme_app.__path__)
    assert list(overlay_browser.__path__)[0].endswith("src/backend_overlay/browser")
    assert list(overlay_browser.__path__)[1:] == list(trustme_browser.__path__)

    assert list(overlay_dashboard.__path__)[0].endswith("src/backend_overlay/browser/dashboard")
    assert list(overlay_dashboard.__path__)[1:] == list(trustme_dashboard.__path__)
    assert list(overlay_settings.__path__)[0].endswith("src/backend_overlay/browser/settings")
    assert list(overlay_settings.__path__)[1:] == list(trustme_settings.__path__)
    assert list(overlay_surveys.__path__)[0].endswith("src/backend_overlay/browser/surveys")
    assert list(overlay_surveys.__path__)[1:] == list(trustme_surveys.__path__)
    assert list(overlay_canonical.__path__)[0].endswith("src/backend_overlay/browser/canonical")
    assert list(overlay_canonical.__path__)[1:] == list(trustme_canonical.__path__)
    assert list(overlay_snapshots.__path__)[0].endswith("src/backend_overlay/browser/snapshots")
    assert list(overlay_snapshots.__path__)[1:] == list(trustme_snapshots.__path__)


def test_backend_overlay_browser_shims_use_internal_legacy_bridge():
    browser_root = Path("src/backend_overlay/browser")
    offenders = []

    for path in browser_root.rglob("*.py"):
        if "trustme_api.browser." in path.read_text(encoding="utf-8"):
            offenders.append(path.as_posix())

    assert offenders == []


def test_backend_overlay_package_includes_overlay_json_assets():
    overlay_settings_asset = Path(overlay_schema.__file__).with_name("settings_seed_knowledgebase.v1.json")
    overlay_surveys_asset = Path(overlay_survey_template.__file__).with_name("fixed_questionnaire.v1.json")
    trustme_settings_asset = Path(trustme_schema.__file__).with_name("settings_seed_knowledgebase.v1.json")
    trustme_surveys_asset = Path(trustme_survey_template.__file__).with_name("fixed_questionnaire.v1.json")

    assert overlay_settings_asset.exists()
    assert overlay_surveys_asset.exists()
    assert overlay_settings_asset.read_text(encoding="utf-8") == trustme_settings_asset.read_text(encoding="utf-8")
    assert overlay_surveys_asset.read_text(encoding="utf-8") == trustme_surveys_asset.read_text(encoding="utf-8")


def test_pyproject_declares_overlay_package_data_entries():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]

    assert package_data["backend_overlay.browser.settings"] == ["*.json"]
    assert package_data["backend_overlay.browser.surveys"] == ["*.json"]
