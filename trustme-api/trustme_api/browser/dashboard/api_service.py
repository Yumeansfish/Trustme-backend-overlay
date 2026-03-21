from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from .dashboard_details import build_dashboard_details
from .dashboard_domain_service import (
    build_ad_hoc_summary_scope,
    build_settings_backed_summary_scope,
    resolve_default_dashboard_hosts,
    resolve_dashboard_scope as resolve_dashboard_scope_request,
)
from .dashboard_dto import (
    DashboardDefaultHostsResponse,
    DashboardDetailsResponse,
    DashboardScopeResponse,
    SummarySnapshotResponse,
    serialize_dashboard_default_hosts_response,
    serialize_dashboard_details_response,
    serialize_dashboard_scope_response,
    serialize_summary_snapshot_response,
)
from .summary_snapshot import build_summary_snapshot_from_scope


def build_summary_snapshot_response(
    *,
    db,
    settings_data: Dict[str, Any],
    summary_snapshot_store,
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
) -> SummarySnapshotResponse:
    if categories is None and always_active_pattern is None:
        scope = build_settings_backed_summary_scope(
            settings_data=settings_data,
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            stopwatch_buckets=stopwatch_buckets,
            filter_afk=filter_afk,
            filter_categories=filter_categories,
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
        )

    return serialize_summary_snapshot_response(
        build_summary_snapshot_from_scope(
            db,
            range_start=range_start,
            range_end=range_end,
            category_periods=category_periods,
            scope=scope,
            store=summary_snapshot_store,
        ),
        category_periods=category_periods,
    )


def build_dashboard_scope_response(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    requested_hosts: Sequence[str],
    range_start: Optional[datetime] = None,
    range_end: Optional[datetime] = None,
) -> DashboardScopeResponse:
    overlap_start_ms = range_start.timestamp() * 1000 if range_start else None
    overlap_end_ms = range_end.timestamp() * 1000 if range_end else None
    return serialize_dashboard_scope_response(
        resolve_dashboard_scope_request(
            settings_data=settings_data,
            bucket_records=bucket_records,
            requested_hosts=requested_hosts,
            overlap_start_ms=overlap_start_ms,
            overlap_end_ms=overlap_end_ms,
        )
    )


def build_default_dashboard_hosts_response(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
) -> DashboardDefaultHostsResponse:
    return serialize_dashboard_default_hosts_response(
        {
            "resolved_hosts": resolve_default_dashboard_hosts(
                settings_data=settings_data,
                bucket_records=bucket_records,
            )
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
