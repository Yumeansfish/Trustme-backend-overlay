from trustme_api.browser.dashboard.domain_service import (
    build_dashboard_summary_scopes as legacy_build_dashboard_summary_scopes,
    resolve_dashboard_scope as legacy_resolve_dashboard_scope,
)
from trustme_api.browser.dashboard.scope_service import (
    build_dashboard_summary_scopes,
    resolve_dashboard_scope,
)


def test_domain_service_shim_reexports_scope_service():
    assert legacy_build_dashboard_summary_scopes is build_dashboard_summary_scopes
    assert legacy_resolve_dashboard_scope is resolve_dashboard_scope
