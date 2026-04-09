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

from trustme_api.browser.snapshots.scheduler import (
    SUMMARY_WARMUP_INTERVAL_SECONDS,
    start_dashboard_summary_warmup,
)
from trustme_api.browser.snapshots.warmup import (
    SUMMARY_WARMUP_INTERVAL_SECONDS as legacy_interval,
    start_dashboard_summary_warmup as legacy_start,
)


def test_warmup_shim_reexports_scheduler_entrypoints():
    assert legacy_start is start_dashboard_summary_warmup
    assert legacy_interval == SUMMARY_WARMUP_INTERVAL_SECONDS
