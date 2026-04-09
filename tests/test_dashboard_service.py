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

from trustme_api.browser.dashboard.api_facade import DashboardAPI as LegacyDashboardAPI
from trustme_api.browser.dashboard.api_service import (
    build_dashboard_details_response as legacy_build_dashboard_details_response,
    build_dashboard_scope_response as legacy_build_dashboard_scope_response,
    build_default_dashboard_hosts_response as legacy_build_default_dashboard_hosts_response,
    build_summary_snapshot_response as legacy_build_summary_snapshot_response,
)
from trustme_api.browser.dashboard.service import (
    DashboardAPI,
    build_dashboard_details_response,
    build_dashboard_scope_response,
    build_default_dashboard_hosts_response,
    build_summary_snapshot_response,
)


def test_api_facade_shim_reexports_dashboard_api():
    assert LegacyDashboardAPI is DashboardAPI


def test_api_service_shim_reexports_service_functions():
    assert legacy_build_dashboard_details_response is build_dashboard_details_response
    assert legacy_build_dashboard_scope_response is build_dashboard_scope_response
    assert legacy_build_default_dashboard_hosts_response is build_default_dashboard_hosts_response
    assert legacy_build_summary_snapshot_response is build_summary_snapshot_response
