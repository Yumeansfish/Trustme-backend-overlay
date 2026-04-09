import sys
import types

shared_module = types.ModuleType("trustme_api.shared")
shared_models_module = types.ModuleType("trustme_api.shared.models")


class Event(dict):
    pass


shared_models_module.Event = Event
sys.modules.setdefault("trustme_api.shared", shared_module)
sys.modules["trustme_api.shared.models"] = shared_models_module

from trustme_api.browser.dashboard.details import build_dashboard_details as legacy_build_dashboard_details
from trustme_api.browser.dashboard.details_service import build_dashboard_details


def test_details_shim_reexports_details_service():
    assert legacy_build_dashboard_details is build_dashboard_details
