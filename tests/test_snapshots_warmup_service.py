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

from trustme_api.browser.snapshots.warmup import (
    build_dashboard_summary_warmup_jobs as legacy_build_jobs,
    warm_dashboard_summary_snapshots as legacy_warm,
)
from trustme_api.browser.snapshots.warmup_service import (
    build_dashboard_summary_warmup_jobs,
    warm_dashboard_summary_snapshots,
)


def test_warmup_shim_reexports_warmup_service():
    assert legacy_build_jobs is build_dashboard_summary_warmup_jobs
    assert legacy_warm is warm_dashboard_summary_snapshots
