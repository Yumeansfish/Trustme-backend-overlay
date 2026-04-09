from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from trustme_api.browser.dashboard.checkins_service import build_checkins_payload
from trustme_api.browser.dashboard.details_service import build_dashboard_details
from trustme_api.browser.dashboard.scope_service import (
    build_ad_hoc_summary_scope,
    build_bucket_records,
    build_settings_backed_summary_scope,
    resolve_default_dashboard_scope,
    resolve_dashboard_scope as resolve_dashboard_scope_request,
)
from trustme_api.browser.dashboard.dto import (
    CheckinsResponse,
    DashboardDefaultHostsResponse,
    DashboardDetailsResponse,
    DashboardScopeResponse,
    SummarySnapshotResponse,
    serialize_dashboard_default_hosts_response,
    serialize_dashboard_details_response,
    serialize_dashboard_scope_response,
    serialize_summary_snapshot_response,
)
def build_summary_snapshot_response(
    *,
    db,
    settings_data: Dict[str, Any],
    summary_snapshot_store,
    canonical_unit_store,
    range_start: datetime,
    range_end: datetime,
    category_periods: Sequence[str],
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    filter_categories: Sequence[Sequence[str]],
    categories: Optional[Sequence[Any]] = None,
    always_active_pattern: Optional[str] = None,
    group_name: Optional[str] = None,
) -> SummarySnapshotResponse:
    from trustme_api.browser.snapshots.summary_service import build_summary_snapshot_from_scope

    if categories is None and always_active_pattern is None:
        scope = build_settings_backed_summary_scope(
            settings_data=settings_data,
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            stopwatch_buckets=stopwatch_buckets,
            filter_afk=filter_afk,
            filter_categories=filter_categories,
            group_name=group_name or "dashboard",
        )
    else:
        scope = build_ad_hoc_summary_scope(
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            stopwatch_buckets=stopwatch_buckets,
            filter_afk=filter_afk,
            categories=categories or [],
            filter_categories=filter_categories,
            always_active_pattern=always_active_pattern or "",
            group_name=group_name or "ad-hoc",
        )

    return serialize_summary_snapshot_response(
        build_summary_snapshot_from_scope(
            db,
            range_start=range_start,
            range_end=range_end,
            category_periods=category_periods,
            scope=scope,
            store=summary_snapshot_store,
            calendar_settings=settings_data,
            canonical_unit_store=canonical_unit_store,
        ),
        category_periods=category_periods,
    )


def build_dashboard_scope_response(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    requested_hosts: Sequence[str],
    requested_group_name: Optional[str] = None,
    range_start: Optional[datetime] = None,
    range_end: Optional[datetime] = None,
    db=None,
    availability_store=None,
) -> DashboardScopeResponse:
    overlap_start_ms = range_start.timestamp() * 1000 if range_start else None
    overlap_end_ms = range_end.timestamp() * 1000 if range_end else None
    return serialize_dashboard_scope_response(
        resolve_dashboard_scope_request(
            settings_data=settings_data,
            bucket_records=bucket_records,
            requested_hosts=requested_hosts,
            requested_group_name=requested_group_name,
            overlap_start_ms=overlap_start_ms,
            overlap_end_ms=overlap_end_ms,
            db=db,
            availability_store=availability_store,
        )
    )


def build_default_dashboard_hosts_response(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
) -> DashboardDefaultHostsResponse:
    default_scope = resolve_default_dashboard_scope(
        settings_data=settings_data,
        bucket_records=bucket_records,
    )
    return serialize_dashboard_default_hosts_response(
        {
            "group_name": default_scope.group_name,
            "resolved_hosts": default_scope.resolved_hosts,
        }
    )


def build_dashboard_details_response(
    *,
    db,
    range_start: datetime,
    range_end: datetime,
    window_buckets: List[str],
    browser_buckets: List[str],
    stopwatch_buckets: List[str],
) -> DashboardDetailsResponse:
    return serialize_dashboard_details_response(
        build_dashboard_details(
            db,
            range_start=range_start,
            range_end=range_end,
            window_buckets=window_buckets,
            browser_buckets=browser_buckets,
            stopwatch_buckets=stopwatch_buckets,
        )
    )


class DashboardAPI:
    def __init__(
        self,
        *,
        db,
        settings,
        summary_snapshot_store,
        canonical_unit_store,
        dashboard_availability_store,
        get_buckets: Callable[[], Dict[str, Dict[str, Any]]],
    ) -> None:
        self.db = db
        self.settings = settings
        self.summary_snapshot_store = summary_snapshot_store
        self.canonical_unit_store = canonical_unit_store
        self.dashboard_availability_store = dashboard_availability_store
        self.get_buckets = get_buckets

    def summary_snapshot(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        category_periods: List[str],
        window_buckets: List[str],
        afk_buckets: List[str],
        stopwatch_buckets: List[str],
        filter_afk: bool,
        filter_categories: List[List[str]],
        categories: Optional[List[Any]] = None,
        always_active_pattern: Optional[str] = None,
        group_name: Optional[str] = None,
    ) -> SummarySnapshotResponse:
        return build_summary_snapshot_response(
            db=self.db,
            settings_data=self.settings.get(""),
            summary_snapshot_store=self.summary_snapshot_store,
            canonical_unit_store=self.canonical_unit_store,
            range_start=range_start,
            range_end=range_end,
            category_periods=category_periods,
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            stopwatch_buckets=stopwatch_buckets,
            filter_afk=filter_afk,
            filter_categories=filter_categories,
            categories=categories,
            always_active_pattern=always_active_pattern,
            group_name=group_name,
        )

    def checkins(self, *, date_filter: Optional[str] = None) -> CheckinsResponse:
        return build_checkins_payload(date_filter=date_filter)

    def resolve_scope(
        self,
        *,
        requested_hosts: List[str],
        requested_group_name: Optional[str] = None,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> DashboardScopeResponse:
        return build_dashboard_scope_response(
            db=self.db,
            settings_data=self.settings.get(""),
            bucket_records=build_bucket_records(self.get_buckets()),
            requested_hosts=requested_hosts,
            requested_group_name=requested_group_name,
            range_start=range_start,
            range_end=range_end,
            availability_store=self.dashboard_availability_store,
        )

    def default_hosts(self) -> DashboardDefaultHostsResponse:
        return build_default_dashboard_hosts_response(
            settings_data=self.settings.get(""),
            bucket_records=build_bucket_records(self.get_buckets()),
        )

    def details(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        window_buckets: List[str],
        browser_buckets: List[str],
        stopwatch_buckets: List[str],
    ) -> DashboardDetailsResponse:
        return build_dashboard_details_response(
            db=self.db,
            range_start=range_start,
            range_end=range_end,
            window_buckets=window_buckets,
            browser_buckets=browser_buckets,
            stopwatch_buckets=stopwatch_buckets,
        )
