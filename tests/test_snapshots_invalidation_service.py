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

from trustme_api.browser.snapshots.invalidation import (
    build_snapshot_targets_from_jobs as legacy_build_targets,
)
from trustme_api.browser.snapshots.invalidation_service import build_snapshot_targets_from_jobs


def test_invalidation_shim_reexports_invalidation_service():
    assert legacy_build_targets is build_snapshot_targets_from_jobs
