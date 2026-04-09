from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from trustme_api.browser.canonical.repository import SqliteCanonicalUnitRepository
from trustme_api.browser.canonical.strategy import PERSISTED_UNIT_KINDS
from trustme_api.browser.canonical.units import (
    build_calendar_profile,
    parse_time_range,
)
from trustme_api.browser.dashboard.domain_service import (
    DashboardSummaryScope,
    build_dashboard_summary_scopes,
)
from trustme_api.browser.snapshots.scope import build_summary_snapshot_scope_key
from trustme_api.browser.snapshots.repository import SummarySnapshotRepository
from trustme_api.browser.snapshots.warmup_service import (
    SummaryWarmupJob,
    build_dashboard_summary_warmup_jobs,
)


def build_snapshot_targets_from_jobs(
    jobs: List[SummaryWarmupJob],
) -> List[Dict[str, Any]]:
    grouped_targets: Dict[str, Dict[str, Any]] = {}

    for job in jobs:
        scope_key = _scope_key_for_job(job)
        entry = grouped_targets.setdefault(
            scope_key,
            {
                "scope_key": scope_key,
                "logical_periods": set(),
                "group_names": set(),
                "period_names": set(),
            },
        )
        entry["logical_periods"].update(job.logical_periods)
        entry["group_names"].add(job.group_name)
        entry["period_names"].add(job.period_name)

    return [
        {
            "scope_key": scope_key,
            "logical_periods": sorted(entry["logical_periods"]),
            "group_names": sorted(entry["group_names"]),
            "period_names": sorted(entry["period_names"]),
        }
        for scope_key, entry in grouped_targets.items()
    ]


def build_snapshot_invalidation_targets(
    *,
    settings_data: Dict[str, Any],
    bucket_records: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    jobs = build_dashboard_summary_warmup_jobs(
        settings_data=settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    return build_snapshot_targets_from_jobs(jobs)


def build_snapshot_invalidation_targets_for_settings_change(
    *,
    previous_settings_data: Dict[str, Any],
    settings_data: Dict[str, Any],
    bucket_records: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    previous_targets = build_snapshot_invalidation_targets(
        settings_data=previous_settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    current_targets = build_snapshot_invalidation_targets(
        settings_data=settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    return diff_snapshot_targets(previous_targets, current_targets)


def diff_snapshot_targets(
    previous_targets: List[Dict[str, Any]],
    current_targets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    previous_map = _target_period_map(previous_targets)
    current_map = _target_period_map(current_targets)

    diff_targets = []
    for scope_key in sorted(set(previous_map) | set(current_map)):
        logical_periods = sorted(previous_map.get(scope_key, set()) ^ current_map.get(scope_key, set()))
        if logical_periods:
            diff_targets.append(
                {
                    "scope_key": scope_key,
                    "logical_periods": logical_periods,
                }
            )
    return diff_targets


def invalidate_summary_snapshots_for_targets(
    *,
    store: SummarySnapshotRepository,
    targets: List[Dict[str, Any]],
) -> int:
    deleted = 0
    for target in targets:
        deleted += store.delete_segments(
            scope_key=target["scope_key"],
            logical_periods=target["logical_periods"],
        )
    return deleted


def invalidate_summary_snapshots_for_settings(
    *,
    store: SummarySnapshotRepository,
    previous_settings_data: Dict[str, Any],
    settings_data: Dict[str, Any],
    bucket_records: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> int:
    targets = build_snapshot_invalidation_targets_for_settings_change(
        previous_settings_data=previous_settings_data,
        settings_data=settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    return invalidate_summary_snapshots_for_targets(store=store, targets=targets)


def invalidate_canonical_units_for_bucket_time_range(
    *,
    store: SqliteCanonicalUnitRepository,
    settings_data: Dict[str, Any],
    bucket_records: List[Dict[str, Any]],
    bucket_id: str,
    range_start: datetime,
    range_end: datetime,
) -> int:
    effective_start, effective_end = _coerce_nonempty_range(range_start, range_end)
    calendar_key = build_calendar_profile(settings_data).key
    scopes = build_dashboard_summary_scopes(
        settings_data=settings_data,
        bucket_records=bucket_records,
        overlap_start_ms=effective_start.timestamp() * 1000,
        overlap_end_ms=effective_end.timestamp() * 1000,
    )

    deleted = 0
    for scope in scopes:
        if bucket_id not in {
            *scope.window_buckets,
            *scope.afk_buckets,
            *scope.stopwatch_buckets,
        }:
            continue
        deleted += store.delete_units(
            scope_key=_scope_key_for_scope(scope),
            calendar_key=calendar_key,
            unit_kinds=PERSISTED_UNIT_KINDS,
            range_start=effective_start,
            range_end=effective_end,
        )
    return deleted


def invalidate_canonical_units_for_settings(
    *,
    store: SqliteCanonicalUnitRepository,
    previous_settings_data: Dict[str, Any],
    settings_data: Dict[str, Any],
    bucket_records: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> int:
    previous_targets = build_snapshot_invalidation_targets(
        settings_data=previous_settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    current_targets = build_snapshot_invalidation_targets(
        settings_data=settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    previous_map = _target_period_map(previous_targets)
    current_map = _target_period_map(current_targets)

    deleted = 0
    deleted += _invalidate_canonical_units_for_period_map(
        store=store,
        calendar_key=build_calendar_profile(previous_settings_data).key,
        period_map={
            scope_key: periods - current_map.get(scope_key, set())
            for scope_key, periods in previous_map.items()
            if periods - current_map.get(scope_key, set())
        },
    )
    deleted += _invalidate_canonical_units_for_period_map(
        store=store,
        calendar_key=build_calendar_profile(settings_data).key,
        period_map={
            scope_key: periods - previous_map.get(scope_key, set())
            for scope_key, periods in current_map.items()
            if periods - previous_map.get(scope_key, set())
        },
    )
    return deleted


def _scope_key_for_job(job: SummaryWarmupJob) -> str:
    return _scope_key_for_scope(job.scope)


def _scope_key_for_scope(scope: DashboardSummaryScope) -> str:
    return build_summary_snapshot_scope_key(
        group_name=scope.group_name,
        window_buckets=scope.window_buckets,
        afk_buckets=scope.afk_buckets,
        stopwatch_buckets=scope.stopwatch_buckets,
        filter_afk=scope.filter_afk,
        categories=scope.categories,
        filter_categories=scope.filter_categories,
        always_active_pattern=scope.always_active_pattern,
    )


def _target_period_map(targets: List[Dict[str, Any]]) -> Dict[str, set[str]]:
    target_map: Dict[str, set[str]] = {}
    for target in targets:
        scope_key = str(target["scope_key"])
        entry = target_map.setdefault(scope_key, set())
        entry.update(str(period) for period in target.get("logical_periods", []))
    return target_map


def _invalidate_canonical_units_for_period_map(
    *,
    store: SqliteCanonicalUnitRepository,
    calendar_key: str,
    period_map: Dict[str, set[str]],
) -> int:
    deleted = 0
    for scope_key, logical_periods in period_map.items():
        for logical_period in sorted(logical_periods):
            period = parse_time_range(logical_period)
            if period is None:
                continue
            effective_start, effective_end = _coerce_nonempty_range(period.start, period.end)
            deleted += store.delete_units(
                scope_key=scope_key,
                calendar_key=calendar_key,
                unit_kinds=PERSISTED_UNIT_KINDS,
                range_start=effective_start,
                range_end=effective_end,
            )
    return deleted


def _coerce_nonempty_range(range_start: datetime, range_end: datetime) -> tuple[datetime, datetime]:
    if range_end > range_start:
        return range_start, range_end
    return range_start, range_start + timedelta(microseconds=1)
