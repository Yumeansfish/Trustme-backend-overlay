import sys
import types

shared_module = types.ModuleType("trustme_api.shared")
shared_dirs_module = types.ModuleType("trustme_api.shared.dirs")
shared_models_module = types.ModuleType("trustme_api.shared.models")


class Event(dict):
    pass


shared_models_module.Event = Event
shared_dirs_module.get_data_dir = lambda appname: "/tmp"
sys.modules.setdefault("trustme_api.shared", shared_module)
sys.modules["trustme_api.shared.dirs"] = shared_dirs_module
sys.modules["trustme_api.shared.models"] = shared_models_module

from trustme_api.browser.snapshots.summary import build_summary_snapshot_from_scope as legacy_build
from trustme_api.browser.snapshots.summary_service import build_summary_snapshot_from_scope


def test_summary_shim_reexports_summary_service():
    assert legacy_build is build_summary_snapshot_from_scope
