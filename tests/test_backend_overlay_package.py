import backend_overlay
import trustme_api

from backend_overlay.browser.settings import schema as overlay_schema
from trustme_api.browser.settings import schema as trustme_schema


def test_backend_overlay_exposes_trustme_api_metadata():
    assert backend_overlay.__version__ == trustme_api.__version__
    assert list(backend_overlay.__path__) == list(trustme_api.__path__)


def test_backend_overlay_namespace_resolves_existing_subpackages():
    assert overlay_schema.__file__ == trustme_schema.__file__
