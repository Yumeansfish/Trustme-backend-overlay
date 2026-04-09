import pytest

pytest.importorskip("flask_restx")

from trustme_api.browser.surveys.controller import surveys_api
from trustme_api.browser.surveys.rest import surveys_api as legacy_surveys_api


def test_rest_shim_reexports_controller_namespace():
    assert legacy_surveys_api is surveys_api
