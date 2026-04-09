import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from trustme_api.browser.canonical.strategy import PERSISTED_UNIT_KINDS
from trustme_api.browser.canonical.units import (
    ExperimentalCanonicalQueryEngine,
    infer_bucket_kind_for_logical_periods,
)
from trustme_api.browser.dashboard.domain_service import (
    DashboardSummaryScope,
    build_ad_hoc_summary_scope,
)
from trustme_api.browser.dashboard.dto import SummarySnapshotResponse
from trustme_api.browser.snapshots.categories import (
    compile_category_rules,
    normalize_category_name,
)
from trustme_api.browser.snapshots.response_mapper import (
    build_snapshot_response,
    deserialize_segments,
    empty_summary_snapshot,
    merge_summary_segments,
    serialize_summary_segment,
)
from trustme_api.browser.snapshots.scope import (
    build_period_bounds,
    build_summary_snapshot_scope_key,
    expand_range_to_cover_periods,
)
from trustme_api.browser.snapshots.segments import (
    build_summary_segment,
    empty_summary_segment,
)
from trustme_api.browser.snapshots.models import (
    CompiledCategoryMatcher,
    SummarySegment,
    datetime_to_ms,
)
from trustme_api.browser.snapshots.repository import SummarySnapshotRepository


def build_summary_snapshot(
    db,
    *,
    range_start: datetime,
    range_end: datetime,
    category_periods: Sequence[str],
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    categories: Sequence[Any],
    filter_categories: Sequence[Sequence[str]],
    always_active_pattern: str = "",
    store: Optional[SummarySnapshotRepository] = None,
    calendar_settings: Optional[Dict[str, Any]] = None,
    canonical_unit_store=None,
    now: Optional[datetime] = None,
) -> SummarySnapshotResponse:
    scope = build_ad_hoc_summary_scope(
        window_buckets=window_buckets,
        afk_buckets=afk_buckets,
        stopwatch_buckets=stopwatch_buckets,
        filter_afk=filter_afk,
        categories=categories,
        filter_categories=filter_categories,
        always_active_pattern=always_active_pattern,
    )
    return build_summary_snapshot_from_scope(
        db,
        range_start=range_start,
        range_end=range_end,
        category_periods=category_periods,
        scope=scope,
        store=store,
        calendar_settings=calendar_settings,
        canonical_unit_store=canonical_unit_store,
        now=now,
    )


def build_summary_snapshot_from_scope(
    db,
    *,
    range_start: datetime,
    range_end: datetime,
    category_periods: Sequence[str],
    scope: DashboardSummaryScope,
    store: Optional[SummarySnapshotRepository] = None,
    calendar_settings: Optional[Dict[str, Any]] = None,
    canonical_unit_store=None,
    now: Optional[datetime] = None,
) -> SummarySnapshotResponse:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    range_start, range_end = expand_range_to_cover_periods(
        range_start, range_end, category_periods
    )
    range_end = min(range_end, now)
    period_bounds = build_period_bounds(category_periods)

    allowed_categories = (
        {json.dumps(normalize_category_name(category)) for category in scope.filter_categories}
        if scope.filter_categories
        else None
    )
    if range_end <= range_start or not period_bounds:
        return empty_summary_snapshot(category_periods)

    if not _scope_has_snapshot_activity(
        db,
        range_start=range_start,
        range_end=range_end,
        scope=scope,
    ):
        return empty_summary_snapshot(category_periods)

    canonical_response = _build_canonical_summary_snapshot_from_scope(
        db,
        range_end=range_end,
        category_periods=category_periods,
        scope=scope,
        calendar_settings=calendar_settings,
        canonical_unit_store=canonical_unit_store,
    )
    if canonical_response is not None:
        return canonical_response

    scope_key = build_summary_snapshot_scope_key(
        group_name=scope.group_name,
        window_buckets=scope.window_buckets,
        afk_buckets=scope.afk_buckets,
        stopwatch_buckets=scope.stopwatch_buckets,
        filter_afk=scope.filter_afk,
        categories=scope.categories,
        filter_categories=scope.filter_categories,
        always_active_pattern=scope.always_active_pattern,
    )
    cached_segments = (
        deserialize_segments(store.get_segments(scope_key, [period.key for period in period_bounds]))
        if store
        else {}
    )

    segments: Dict[str, SummarySegment] = {}
    range_end_ms = datetime_to_ms(range_end)
    stored_at = datetime.now(timezone.utc).isoformat()
    compiled_rules: Optional[CompiledCategoryMatcher] = None
    category_cache: Dict[Tuple[str, str, str], List[str]] = {}

    for period in period_bounds:
        effective_end_ms = min(period.end_ms, range_end_ms)
        if effective_end_ms <= period.start_ms:
            continue

        cached_segment = cached_segments.get(period.key)
        if cached_segment and cached_segment.computed_end_ms >= effective_end_ms:
            segments[period.key] = cached_segment
            continue

        compute_start_ms = period.start_ms
        working_segment = empty_summary_segment(period.key, compute_start_ms)
        if cached_segment and cached_segment.computed_end_ms > period.start_ms:
            compute_start_ms = cached_segment.computed_end_ms
            working_segment = cached_segment

        if compiled_rules is None:
            compiled_rules = compile_category_rules(scope.categories)

        compute_start = datetime.fromtimestamp(compute_start_ms / 1000, tz=timezone.utc)
        compute_end = datetime.fromtimestamp(effective_end_ms / 1000, tz=timezone.utc)
        delta_segment = build_summary_segment(
            db,
            logical_period=period.key,
            segment_start=compute_start,
            segment_end=compute_end,
            window_buckets=scope.window_buckets,
            afk_buckets=scope.afk_buckets,
            stopwatch_buckets=scope.stopwatch_buckets,
            filter_afk=scope.filter_afk,
            compiled_rules=compiled_rules,
            allowed_categories=allowed_categories,
            always_active_pattern=scope.always_active_pattern,
            category_cache=category_cache,
        )
        merged_segment = merge_summary_segments(working_segment, delta_segment)
        segments[period.key] = merged_segment

        if store:
            store.put_segment(
                scope_key,
                period.key,
                computed_end=datetime.fromtimestamp(
                    merged_segment.computed_end_ms / 1000, tz=timezone.utc
                ).isoformat(),
                stored_at=stored_at,
                payload=serialize_summary_segment(merged_segment),
            )

    return build_snapshot_response(period_bounds, segments)


def _build_canonical_summary_snapshot_from_scope(
    db,
    *,
    range_end: datetime,
    category_periods: Sequence[str],
    scope: DashboardSummaryScope,
    calendar_settings: Optional[Dict[str, Any]],
    canonical_unit_store,
) -> Optional[SummarySnapshotResponse]:
    if not category_periods or calendar_settings is None or canonical_unit_store is None:
        return None

    engine = ExperimentalCanonicalQueryEngine(
        db=db,
        scope=scope,
        settings_data=calendar_settings,
        store=canonical_unit_store,
        persisted_unit_kinds=PERSISTED_UNIT_KINDS,
    )
    if infer_bucket_kind_for_logical_periods(category_periods, profile=engine.profile) is None:
        return None

    return engine.execute_logical_periods(
        logical_periods=category_periods,
        range_end=range_end,
    )["response"]


def _scope_has_snapshot_activity(
    db,
    *,
    range_start: datetime,
    range_end: datetime,
    scope: DashboardSummaryScope,
) -> bool:
    if not scope.window_buckets or not scope.afk_buckets:
        return False

    if not _bucket_ids_have_events(db, scope.window_buckets, range_start, range_end):
        return False

    if not _bucket_ids_have_events(db, scope.afk_buckets, range_start, range_end):
        return False

    return True


def _bucket_ids_have_events(
    db,
    bucket_ids: Sequence[str],
    range_start: datetime,
    range_end: datetime,
) -> bool:
    for bucket_id in bucket_ids:
        if not isinstance(bucket_id, str) or not bucket_id:
            continue
        try:
            if db[bucket_id].get_eventcount(range_start, range_end) > 0:
                return True
        except KeyError:
            continue
    return False
