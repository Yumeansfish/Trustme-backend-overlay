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

from backend_overlay.browser.settings import schema as overlay_schema
from trustme_api.browser.settings import schema as trustme_schema


def test_backend_overlay_exposes_trustme_api_metadata():
    assert backend_overlay.__version__ == trustme_api.__version__
    assert list(backend_overlay.__path__)[0].endswith("src/backend_overlay")
    assert list(backend_overlay.__path__)[1:] == list(trustme_api.__path__)


def test_backend_overlay_namespace_resolves_existing_subpackages():
    assert overlay_schema.__file__.endswith("src/backend_overlay/browser/settings/schema.py")
    assert overlay_schema.normalize_settings_data is trustme_schema.normalize_settings_data


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
