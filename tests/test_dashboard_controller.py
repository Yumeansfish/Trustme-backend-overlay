import pytest

pytest.importorskip("flask_restx")

from trustme_api.browser.dashboard.controller import dashboard_api
from trustme_api.browser.dashboard.rest import dashboard_api as legacy_dashboard_api


def test_rest_shim_reexports_controller_namespace():
    assert legacy_dashboard_api is dashboard_api
