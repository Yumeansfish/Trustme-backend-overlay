import json
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from aw_core.models import Event

from .summary_snapshot_categories import resolve_category_for_data
from .summary_snapshot_models import (
    CompiledCategoryRule,
    NumericInterval,
    PeriodBound,
    SummarySegment,
    UNCATEGORIZED_CATEGORY_NAME,
    datetime_to_ms,
    duration_seconds,
)


def empty_summary_segment(logical_period: str, computed_end_ms: float) -> SummarySegment:
    return SummarySegment(
        logical_period=logical_period,
        computed_end_ms=computed_end_ms,
        duration=0.0,
        apps={},
        categories={},
        uncategorized_apps={},
    )


def build_summary_segment(
    db,
    *,
    logical_period: str,
    segment_start: datetime,
    segment_end: datetime,
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    compiled_rules: Sequence[CompiledCategoryRule],
    allowed_categories: Optional[set],
    always_active_pattern: str,
) -> SummarySegment:
    if segment_end <= segment_start:
        return empty_summary_segment(logical_period, datetime_to_ms(segment_end))

    window_events = fetch_events(db, window_buckets, segment_start, segment_end)
    afk_events = fetch_events(db, afk_buckets, segment_start, segment_end)
    manual_events = [
        event
        for event in fetch_events(db, stopwatch_buckets, segment_start, segment_end)
        if isinstance(event.data, dict) and event.data.get("running") is False
    ]

    active_intervals = build_active_intervals(
        afk_events,
        window_events,
        always_active_pattern=always_active_pattern,
    )
    stopwatch_intervals = [
        interval for interval in map(event_to_interval, manual_events) if interval
    ]
    base_visible_intervals = (
        active_intervals
        if filter_afk
        else [NumericInterval(datetime_to_ms(segment_start), datetime_to_ms(segment_end))]
    )
    visible_window_intervals = (
        subtract_intervals(base_visible_intervals, stopwatch_intervals)
        if stopwatch_intervals
        else base_visible_intervals
    )

    app_durations: Dict[str, Dict[str, float]] = {}
    category_durations: Dict[str, Dict[str, Any]] = {}
    uncategorized_apps: Dict[str, Dict[str, float]] = {}
    total_duration = 0.0
    interval_index = 0

    for event in window_events:
        event_interval = event_to_interval(event)
        if event_interval is None:
            continue

        while (
            interval_index < len(visible_window_intervals)
            and visible_window_intervals[interval_index].end_ms <= event_interval.start_ms
        ):
            interval_index += 1

        index = interval_index
        while index < len(visible_window_intervals):
            interval = visible_window_intervals[index]
            if interval.start_ms >= event_interval.end_ms:
                break

            total_duration += accumulate_slice(
                max(event_interval.start_ms, interval.start_ms),
                min(event_interval.end_ms, interval.end_ms),
                event.data or {},
                compiled_rules,
                allowed_categories,
                app_durations,
                category_durations,
                uncategorized_apps,
                [],
                [],
            )

            if interval.end_ms >= event_interval.end_ms:
                break
            index += 1

    for event in manual_events:
        data = dict(event.data or {})
        data["$manual_away"] = True
        total_duration += accumulate_slice(
            datetime_to_ms(event.timestamp),
            datetime_to_ms(event.timestamp) + duration_seconds(event) * 1000,
            data,
            compiled_rules,
            allowed_categories,
            app_durations,
            category_durations,
            uncategorized_apps,
            [],
            [],
        )

    return SummarySegment(
        logical_period=logical_period,
        computed_end_ms=datetime_to_ms(segment_end),
        duration=total_duration,
        apps=app_durations,
        categories=category_durations,
        uncategorized_apps=uncategorized_apps,
    )


def fetch_events(
    db,
    bucket_ids: Sequence[str],
    start: datetime,
    end: datetime,
) -> List[Event]:
    events: List[Event] = []
    for bucket_id in dict.fromkeys(bucket_ids):
        if bucket_id not in db.buckets():
            continue
        events.extend(db[bucket_id].get(-1, start, end))
    events.sort(key=lambda event: event.timestamp)
    return events


def event_to_interval(event: Event) -> Optional[NumericInterval]:
    start_ms = datetime_to_ms(event.timestamp)
    end_ms = start_ms + duration_seconds(event) * 1000
    if end_ms <= start_ms:
        return None
    return NumericInterval(start_ms, end_ms)


def merge_intervals(intervals: Iterable[NumericInterval]) -> List[NumericInterval]:
    ordered = sorted(intervals, key=lambda interval: interval.start_ms)
    if not ordered:
        return []

    merged: List[NumericInterval] = [ordered[0]]
    for interval in ordered[1:]:
        previous = merged[-1]
        if interval.start_ms <= previous.end_ms:
            merged[-1] = NumericInterval(previous.start_ms, max(previous.end_ms, interval.end_ms))
        else:
            merged.append(interval)
    return merged


def subtract_intervals(
    base_intervals: Sequence[NumericInterval],
    blocked_intervals: Sequence[NumericInterval],
) -> List[NumericInterval]:
    merged_base = merge_intervals(base_intervals)
    if not merged_base:
        return []

    merged_blocked = merge_intervals(blocked_intervals)
    if not merged_blocked:
        return merged_base

    results: List[NumericInterval] = []
    blocked_index = 0

    for base in merged_base:
        while blocked_index < len(merged_blocked) and merged_blocked[blocked_index].end_ms <= base.start_ms:
            blocked_index += 1

        cursor = base.start_ms
        index = blocked_index
        while index < len(merged_blocked):
            blocked = merged_blocked[index]
            if blocked.start_ms >= base.end_ms:
                break

            if blocked.start_ms > cursor:
                results.append(NumericInterval(cursor, min(blocked.start_ms, base.end_ms)))

            cursor = max(cursor, blocked.end_ms)
            if cursor >= base.end_ms:
                break
            index += 1

        if cursor < base.end_ms:
            results.append(NumericInterval(cursor, base.end_ms))

    return results


def build_active_intervals(
    afk_events: Sequence[Event],
    window_events: Sequence[Event],
    *,
    always_active_pattern: str,
) -> List[NumericInterval]:
    base_intervals = [
        interval
        for interval in (
            event_to_interval(event)
            for event in afk_events
            if isinstance(event.data, dict) and event.data.get("status") == "not-afk"
        )
        if interval
    ]

    if not always_active_pattern:
        return merge_intervals(base_intervals)

    try:
        regex = re.compile(always_active_pattern)
    except re.error:
        return merge_intervals(base_intervals)

    forced_intervals = [
        interval
        for interval in (
            event_to_interval(event)
            for event in window_events
            if matches_always_active(regex, event.data or {})
        )
        if interval
    ]
    return merge_intervals([*base_intervals, *forced_intervals])


def matches_always_active(regex, data: Dict[str, Any]) -> bool:
    app = data.get("app") if isinstance(data.get("app"), str) else ""
    title = data.get("title") if isinstance(data.get("title"), str) else ""
    return bool(regex.search(app) or regex.search(title))


def find_first_overlapping_period(period_bounds: Sequence[PeriodBound], event_start_ms: float) -> int:
    low = 0
    high = len(period_bounds)
    while low < high:
        mid = (low + high) >> 1
        if period_bounds[mid].end_ms <= event_start_ms:
            low = mid + 1
        else:
            high = mid
    return low


def accumulate_slice(
    start_ms: float,
    end_ms: float,
    data: Dict[str, Any],
    compiled_rules: Sequence[CompiledCategoryRule],
    allowed_categories: Optional[set],
    app_durations: Dict[str, Dict[str, float]],
    category_durations: Dict[str, Dict[str, Any]],
    uncategorized_apps: Dict[str, Dict[str, float]],
    period_bounds: Sequence[PeriodBound],
    by_period_maps: Sequence[Dict[str, Dict[str, Any]]],
) -> float:
    if end_ms <= start_ms:
        return 0.0

    duration = (end_ms - start_ms) / 1000
    category = resolve_category_for_data(data, compiled_rules)
    category_key = json.dumps(category)
    app = data.get("app").strip() if isinstance(data.get("app"), str) else ""

    if category == UNCATEGORIZED_CATEGORY_NAME and app:
        existing_uncategorized = uncategorized_apps.get(app)
        if existing_uncategorized:
            existing_uncategorized["duration"] += duration
            existing_uncategorized["timestamp_ms"] = min(
                existing_uncategorized["timestamp_ms"], start_ms
            )
        else:
            uncategorized_apps[app] = {
                "duration": duration,
                "timestamp_ms": start_ms,
            }

    if allowed_categories is not None and category_key not in allowed_categories:
        return 0.0

    existing_category = category_durations.get(category_key)
    if existing_category:
        existing_category["duration"] += duration
        existing_category["timestamp_ms"] = min(existing_category["timestamp_ms"], start_ms)
    else:
        category_durations[category_key] = {
            "category": category,
            "duration": duration,
            "timestamp_ms": start_ms,
        }

    if app:
        existing_app = app_durations.get(app)
        if existing_app:
            existing_app["duration"] += duration
            existing_app["timestamp_ms"] = min(existing_app["timestamp_ms"], start_ms)
        else:
            app_durations[app] = {
                "duration": duration,
                "timestamp_ms": start_ms,
            }

    period_index = find_first_overlapping_period(period_bounds, start_ms)
    while period_index < len(period_bounds) and period_bounds[period_index].start_ms < end_ms:
        period = period_bounds[period_index]
        overlap_start = max(start_ms, period.start_ms)
        overlap_end = min(end_ms, period.end_ms)
        if overlap_end > overlap_start:
            entry = by_period_maps[period_index].get(category_key)
            overlap_duration = (overlap_end - overlap_start) / 1000
            if entry:
                entry["duration"] += overlap_duration
            else:
                by_period_maps[period_index][category_key] = {
                    "category": category,
                    "duration": overlap_duration,
                }
        period_index += 1

    return duration
