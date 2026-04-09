import backend_overlay
import backend_overlay.app as overlay_app
import backend_overlay.browser as overlay_browser
import trustme_api
import trustme_api.app as trustme_app
import trustme_api.browser as trustme_browser

from backend_overlay.browser.settings import schema as overlay_schema
from trustme_api.browser.settings import schema as trustme_schema


def test_backend_overlay_exposes_trustme_api_metadata():
    assert backend_overlay.__version__ == trustme_api.__version__
    assert list(backend_overlay.__path__)[0].endswith("src/backend_overlay")
    assert list(backend_overlay.__path__)[1:] == list(trustme_api.__path__)


def test_backend_overlay_namespace_resolves_existing_subpackages():
    assert overlay_schema.__file__ == trustme_schema.__file__


def test_backend_overlay_subpackage_shims_preserve_own_package_roots():
    assert list(overlay_app.__path__)[0].endswith("src/backend_overlay/app")
    assert list(overlay_app.__path__)[1:] == list(trustme_app.__path__)
    assert list(overlay_browser.__path__)[0].endswith("src/backend_overlay/browser")
    assert list(overlay_browser.__path__)[1:] == list(trustme_browser.__path__)
