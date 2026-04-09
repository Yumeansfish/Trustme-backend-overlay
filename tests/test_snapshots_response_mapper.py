import sys
import types

shared_module = types.ModuleType("trustme_api.shared")
shared_models_module = types.ModuleType("trustme_api.shared.models")


class Event(dict):
    pass


shared_models_module.Event = Event
sys.modules.setdefault("trustme_api.shared", shared_module)
sys.modules["trustme_api.shared.models"] = shared_models_module

from trustme_api.browser.snapshots.response import build_event_json as legacy_build_event_json
from trustme_api.browser.snapshots.response_mapper import build_event_json


def test_response_shim_reexports_response_mapper():
    assert legacy_build_event_json is build_event_json
