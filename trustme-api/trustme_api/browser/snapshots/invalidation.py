from datetime import datetime
from typing import Any, Dict, List, Optional

from .dashboard_domain_service import DashboardSummaryScope
from .dashboard_summary_store import SummarySnapshotStore
from .dashboard_summary_warmup import (
    SummaryWarmupJob,
    build_dashboard_summary_warmup_jobs,
)
from .summary_snapshot import build_summary_snapshot_scope_key


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


def invalidate_summary_snapshots_for_targets(
    *,
    store: SummarySnapshotStore,
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
    store: SummarySnapshotStore,
    settings_data: Dict[str, Any],
    bucket_records: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> int:
    targets = build_snapshot_invalidation_targets(
        settings_data=settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    return invalidate_summary_snapshots_for_targets(store=store, targets=targets)


def _scope_key_for_job(job: SummaryWarmupJob) -> str:
    return _scope_key_for_scope(job.scope)


def _scope_key_for_scope(scope: DashboardSummaryScope) -> str:
    return build_summary_snapshot_scope_key(
        window_buckets=scope.window_buckets,
        afk_buckets=scope.afk_buckets,
        stopwatch_buckets=scope.stopwatch_buckets,
        filter_afk=scope.filter_afk,
        categories=scope.categories,
        filter_categories=scope.filter_categories,
        always_active_pattern=scope.always_active_pattern,
    )
