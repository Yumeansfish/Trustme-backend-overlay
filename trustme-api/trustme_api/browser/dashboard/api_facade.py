from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .checkins import build_checkins_payload
from .dashboard_api_service import (
    build_dashboard_details_response,
    build_dashboard_scope_response,
    build_default_dashboard_hosts_response,
    build_summary_snapshot_response,
)
from .dashboard_dto import (
    CheckinsResponse,
    DashboardDetailsResponse,
    DashboardDefaultHostsResponse,
    DashboardScopeResponse,
    SummarySnapshotResponse,
)
from .dashboard_summary_warmup import build_bucket_records


class DashboardAPI:
    def __init__(
        self,
        *,
        db,
        settings,
        summary_snapshot_store,
        get_buckets: Callable[[], Dict[str, Dict[str, Any]]],
    ) -> None:
        self.db = db
        self.settings = settings
        self.summary_snapshot_store = summary_snapshot_store
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
    ) -> SummarySnapshotResponse:
        return build_summary_snapshot_response(
            db=self.db,
            settings_data=self.settings.get(""),
            summary_snapshot_store=self.summary_snapshot_store,
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
        )

    def checkins(self, *, date_filter: Optional[str] = None) -> CheckinsResponse:
        return build_checkins_payload(date_filter=date_filter)

    def resolve_scope(
        self,
        *,
        requested_hosts: List[str],
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> DashboardScopeResponse:
        return build_dashboard_scope_response(
            settings_data=self.settings.get(""),
            bucket_records=build_bucket_records(self.get_buckets()),
            requested_hosts=requested_hosts,
            range_start=range_start,
            range_end=range_end,
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
