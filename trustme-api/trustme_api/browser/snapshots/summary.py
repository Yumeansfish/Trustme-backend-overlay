import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from aw_core.models import Event

from .dashboard_summary_store import SummarySnapshotStore


LOCAL_AGGREGATION_LIMIT = 100
UNCATEGORIZED_CATEGORY_NAME = ["Uncategorized"]


@dataclass(frozen=True)
class NumericInterval:
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class PeriodBound:
    key: str
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class CompiledCategoryRule:
    category: List[str]
    regex: Any


@dataclass(frozen=True)
class SummarySegment:
    logical_period: str
    computed_end_ms: float
    duration: float
    apps: Dict[str, Dict[str, float]]
    categories: Dict[str, Dict[str, Any]]
    uncategorized_apps: Dict[str, Dict[str, float]]


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
    store: Optional[SummarySnapshotStore] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    range_start, range_end = _expand_range_to_cover_periods(
        range_start, range_end, category_periods
    )
    range_end = min(range_end, now)
    period_bounds = _build_period_bounds(category_periods)

    allowed_categories = (
        {json.dumps(_normalize_category_name(category)) for category in filter_categories}
        if filter_categories
        else None
    )
    if range_end <= range_start or not period_bounds:
        return _empty_summary_snapshot(category_periods)

    scope_key = _build_snapshot_scope_key(
        window_buckets=window_buckets,
        afk_buckets=afk_buckets,
        stopwatch_buckets=stopwatch_buckets,
        filter_afk=filter_afk,
        categories=categories,
        filter_categories=filter_categories,
        always_active_pattern=always_active_pattern,
    )
    cached_segments = (
        _deserialize_segments(store.get_segments(scope_key, [period.key for period in period_bounds]))
        if store
        else {}
    )

    segments: Dict[str, SummarySegment] = {}
    range_end_ms = _datetime_to_ms(range_end)
    stored_at = datetime.now(timezone.utc).isoformat()
    compiled_rules: Optional[Sequence[CompiledCategoryRule]] = None

    for period in period_bounds:
        effective_end_ms = min(period.end_ms, range_end_ms)
        if effective_end_ms <= period.start_ms:
            continue

        cached_segment = cached_segments.get(period.key)
        if cached_segment and cached_segment.computed_end_ms >= effective_end_ms:
            segments[period.key] = cached_segment
            continue

        compute_start_ms = period.start_ms
        working_segment = _empty_summary_segment(period.key, compute_start_ms)
        if cached_segment and cached_segment.computed_end_ms > period.start_ms:
            compute_start_ms = cached_segment.computed_end_ms
            working_segment = cached_segment

        if compiled_rules is None:
            compiled_rules = _compile_category_rules(categories)

        compute_start = datetime.fromtimestamp(compute_start_ms / 1000, tz=timezone.utc)
        compute_end = datetime.fromtimestamp(effective_end_ms / 1000, tz=timezone.utc)
        delta_segment = _build_summary_segment(
            db,
            logical_period=period.key,
            segment_start=compute_start,
            segment_end=compute_end,
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            stopwatch_buckets=stopwatch_buckets,
            filter_afk=filter_afk,
            compiled_rules=compiled_rules,
            allowed_categories=allowed_categories,
            always_active_pattern=always_active_pattern,
        )
        merged_segment = _merge_summary_segments(working_segment, delta_segment)
        segments[period.key] = merged_segment

        if store:
            store.put_segment(
                scope_key,
                period.key,
                computed_end=datetime.fromtimestamp(
                    merged_segment.computed_end_ms / 1000, tz=timezone.utc
                ).isoformat(),
                stored_at=stored_at,
                payload=_serialize_summary_segment(merged_segment),
            )

    return _build_snapshot_response(period_bounds, segments)


def _empty_summary_snapshot(category_periods: Sequence[str]) -> Dict[str, Any]:
    return {
        "window": {
            "app_events": [],
            "title_events": [],
            "cat_events": [],
            "active_events": [],
            "duration": 0,
        },
        "by_period": {period: {"cat_events": []} for period in category_periods},
        "uncategorized_rows": [],
    }


def _empty_summary_segment(logical_period: str, computed_end_ms: float) -> SummarySegment:
    return SummarySegment(
        logical_period=logical_period,
        computed_end_ms=computed_end_ms,
        duration=0.0,
        apps={},
        categories={},
        uncategorized_apps={},
    )


def _build_snapshot_scope_key(
    *,
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    categories: Sequence[Any],
    filter_categories: Sequence[Sequence[str]],
    always_active_pattern: str,
) -> str:
    normalized_window_buckets = sorted(dict.fromkeys(window_buckets))
    normalized_afk_buckets = sorted(dict.fromkeys(afk_buckets))
    normalized_stopwatch_buckets = sorted(dict.fromkeys(stopwatch_buckets))
    normalized_categories = sorted(
        json.dumps(category, sort_keys=True, separators=(",", ":")) for category in categories
    )
    normalized_filter_categories = sorted(
        json.dumps(_normalize_category_name(category), separators=(",", ":"))
        for category in filter_categories
    )
    payload = {
        "version": 1,
        "window_buckets": normalized_window_buckets,
        "afk_buckets": normalized_afk_buckets,
        "stopwatch_buckets": normalized_stopwatch_buckets,
        "filter_afk": bool(filter_afk),
        "categories": normalized_categories,
        "filter_categories": normalized_filter_categories,
        "always_active_pattern": always_active_pattern or "",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest.hexdigest()


def _deserialize_segments(raw_segments: Dict[str, Dict[str, Any]]) -> Dict[str, SummarySegment]:
    segments = {}
    for logical_period, row in raw_segments.items():
        payload = row["payload"]
        segments[logical_period] = SummarySegment(
            logical_period=logical_period,
            computed_end_ms=_datetime_to_ms(
                datetime.fromisoformat(row["computed_end"].replace("Z", "+00:00"))
            ),
            duration=float(payload.get("duration", 0.0)),
            apps={
                app: {
                    "duration": float(entry.get("duration", 0.0)),
                    "timestamp_ms": float(entry.get("timestamp_ms", 0.0)),
                }
                for app, entry in (payload.get("apps") or {}).items()
            },
            categories={
                key: {
                    "category": _normalize_category_name(entry.get("category")),
                    "duration": float(entry.get("duration", 0.0)),
                    "timestamp_ms": float(entry.get("timestamp_ms", 0.0)),
                }
                for key, entry in (payload.get("categories") or {}).items()
            },
            uncategorized_apps={
                app: {
                    "duration": float(entry.get("duration", 0.0)),
                    "timestamp_ms": float(entry.get("timestamp_ms", 0.0)),
                }
                for app, entry in (payload.get("uncategorized_apps") or {}).items()
            },
        )
    return segments


def _serialize_summary_segment(segment: SummarySegment) -> Dict[str, Any]:
    return {
        "duration": segment.duration,
        "apps": segment.apps,
        "categories": segment.categories,
        "uncategorized_apps": segment.uncategorized_apps,
    }


def _merge_summary_segments(base: SummarySegment, delta: SummarySegment) -> SummarySegment:
    apps = {
        app: {
            "duration": float(entry["duration"]),
            "timestamp_ms": float(entry["timestamp_ms"]),
        }
        for app, entry in base.apps.items()
    }
    categories = {
        key: {
            "category": list(entry["category"]),
            "duration": float(entry["duration"]),
            "timestamp_ms": float(entry["timestamp_ms"]),
        }
        for key, entry in base.categories.items()
    }
    uncategorized_apps = {
        app: {
            "duration": float(entry["duration"]),
            "timestamp_ms": float(entry["timestamp_ms"]),
        }
        for app, entry in base.uncategorized_apps.items()
    }

    for app, entry in delta.apps.items():
        existing = apps.get(app)
        if existing:
            existing["duration"] += float(entry["duration"])
            existing["timestamp_ms"] = min(existing["timestamp_ms"], float(entry["timestamp_ms"]))
        else:
            apps[app] = {
                "duration": float(entry["duration"]),
                "timestamp_ms": float(entry["timestamp_ms"]),
            }

    for key, entry in delta.categories.items():
        existing = categories.get(key)
        if existing:
            existing["duration"] += float(entry["duration"])
            existing["timestamp_ms"] = min(existing["timestamp_ms"], float(entry["timestamp_ms"]))
        else:
            categories[key] = {
                "category": list(entry["category"]),
                "duration": float(entry["duration"]),
                "timestamp_ms": float(entry["timestamp_ms"]),
            }

    for app, entry in delta.uncategorized_apps.items():
        existing = uncategorized_apps.get(app)
        if existing:
            existing["duration"] += float(entry["duration"])
            existing["timestamp_ms"] = min(existing["timestamp_ms"], float(entry["timestamp_ms"]))
        else:
            uncategorized_apps[app] = {
                "duration": float(entry["duration"]),
                "timestamp_ms": float(entry["timestamp_ms"]),
            }

    return SummarySegment(
        logical_period=base.logical_period,
        computed_end_ms=max(base.computed_end_ms, delta.computed_end_ms),
        duration=base.duration + delta.duration,
        apps=apps,
        categories=categories,
        uncategorized_apps=uncategorized_apps,
    )


def _build_summary_segment(
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
        return _empty_summary_segment(logical_period, _datetime_to_ms(segment_end))

    window_events = _fetch_events(db, window_buckets, segment_start, segment_end)
    afk_events = _fetch_events(db, afk_buckets, segment_start, segment_end)
    manual_events = [
        event
        for event in _fetch_events(db, stopwatch_buckets, segment_start, segment_end)
        if isinstance(event.data, dict) and event.data.get("running") is False
    ]

    active_intervals = _build_active_intervals(
        afk_events,
        window_events,
        always_active_pattern=always_active_pattern,
    )
    stopwatch_intervals = [
        interval for interval in map(_event_to_interval, manual_events) if interval
    ]
    base_visible_intervals = (
        active_intervals
        if filter_afk
        else [NumericInterval(_datetime_to_ms(segment_start), _datetime_to_ms(segment_end))]
    )
    visible_window_intervals = (
        _subtract_intervals(base_visible_intervals, stopwatch_intervals)
        if stopwatch_intervals
        else base_visible_intervals
    )

    app_durations: Dict[str, Dict[str, float]] = {}
    category_durations: Dict[str, Dict[str, Any]] = {}
    uncategorized_apps: Dict[str, Dict[str, float]] = {}
    total_duration = 0.0
    interval_index = 0

    for event in window_events:
        event_interval = _event_to_interval(event)
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

            total_duration += _accumulate_slice(
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
        total_duration += _accumulate_slice(
            _datetime_to_ms(event.timestamp),
            _datetime_to_ms(event.timestamp) + _duration_seconds(event) * 1000,
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
        computed_end_ms=_datetime_to_ms(segment_end),
        duration=total_duration,
        apps=app_durations,
        categories=category_durations,
        uncategorized_apps=uncategorized_apps,
    )


def _build_snapshot_response(
    period_bounds: Sequence[PeriodBound],
    segments: Dict[str, SummarySegment],
) -> Dict[str, Any]:
    app_durations: Dict[str, Dict[str, float]] = {}
    category_durations: Dict[str, Dict[str, Any]] = {}
    uncategorized_apps: Dict[str, Dict[str, float]] = {}
    total_duration = 0.0
    by_period: Dict[str, Dict[str, Any]] = {}

    for period in period_bounds:
        segment = segments.get(period.key)
        if segment is None:
            by_period[period.key] = {"cat_events": []}
            continue

        total_duration += segment.duration
        for app, entry in segment.apps.items():
            existing_app = app_durations.get(app)
            if existing_app:
                existing_app["duration"] += entry["duration"]
                existing_app["timestamp_ms"] = min(
                    existing_app["timestamp_ms"], entry["timestamp_ms"]
                )
            else:
                app_durations[app] = dict(entry)

        for key, entry in segment.categories.items():
            existing_category = category_durations.get(key)
            if existing_category:
                existing_category["duration"] += entry["duration"]
                existing_category["timestamp_ms"] = min(
                    existing_category["timestamp_ms"], entry["timestamp_ms"]
                )
            else:
                category_durations[key] = {
                    "category": list(entry["category"]),
                    "duration": float(entry["duration"]),
                    "timestamp_ms": float(entry["timestamp_ms"]),
                }

        for app, entry in segment.uncategorized_apps.items():
            existing_uncategorized = uncategorized_apps.get(app)
            if existing_uncategorized:
                existing_uncategorized["duration"] += entry["duration"]
                existing_uncategorized["timestamp_ms"] = min(
                    existing_uncategorized["timestamp_ms"], entry["timestamp_ms"]
                )
            else:
                uncategorized_apps[app] = {
                    "duration": float(entry["duration"]),
                    "timestamp_ms": float(entry["timestamp_ms"]),
                }

        by_period[period.key] = {
            "cat_events": [
                _build_event_json(
                    period.start_ms,
                    entry["duration"],
                    {"$category": entry["category"]},
                )
                for entry in sorted(
                    segment.categories.values(),
                    key=lambda item: item["duration"],
                    reverse=True,
                )
            ]
        }

    return {
        "window": {
            "app_events": [
                _build_event_json(entry["timestamp_ms"], entry["duration"], {"app": app})
                for app, entry in sorted(
                    app_durations.items(), key=lambda item: item[1]["duration"], reverse=True
                )[:LOCAL_AGGREGATION_LIMIT]
            ],
            "title_events": [],
            "cat_events": [
                _build_event_json(
                    entry["timestamp_ms"],
                    entry["duration"],
                    {"$category": entry["category"]},
                )
                for entry in sorted(
                    category_durations.values(),
                    key=lambda item: item["duration"],
                    reverse=True,
                )[:LOCAL_AGGREGATION_LIMIT]
            ],
            "active_events": [],
            "duration": total_duration,
        },
        "by_period": by_period,
        "uncategorized_rows": [
            {
                "key": app,
                "app": app,
                "title": app,
                "subtitle": "",
                "duration": entry["duration"],
                "matchText": app,
            }
            for app, entry in sorted(
                uncategorized_apps.items(), key=lambda item: item[1]["duration"], reverse=True
            )[:LOCAL_AGGREGATION_LIMIT]
        ],
    }


def _expand_range_to_cover_periods(
    range_start: datetime,
    range_end: datetime,
    periods: Sequence[str],
) -> Tuple[datetime, datetime]:
    period_bounds = _build_period_bounds(periods)
    if not period_bounds:
        return range_start, range_end

    range_start_ms = _datetime_to_ms(range_start)
    range_end_ms = _datetime_to_ms(range_end)
    periods_start_ms = min(period.start_ms for period in period_bounds)
    periods_end_ms = max(period.end_ms for period in period_bounds)

    effective_start_ms = min(range_start_ms, periods_start_ms)
    effective_end_ms = max(range_end_ms, periods_end_ms)

    return (
        datetime.fromtimestamp(effective_start_ms / 1000, tz=timezone.utc),
        datetime.fromtimestamp(effective_end_ms / 1000, tz=timezone.utc),
    )


def _fetch_events(
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


def _event_to_interval(event: Event) -> Optional[NumericInterval]:
    start_ms = _datetime_to_ms(event.timestamp)
    end_ms = start_ms + _duration_seconds(event) * 1000
    if end_ms <= start_ms:
        return None
    return NumericInterval(start_ms, end_ms)


def _merge_intervals(intervals: Iterable[NumericInterval]) -> List[NumericInterval]:
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


def _subtract_intervals(
    base_intervals: Sequence[NumericInterval],
    blocked_intervals: Sequence[NumericInterval],
) -> List[NumericInterval]:
    merged_base = _merge_intervals(base_intervals)
    if not merged_base:
        return []

    merged_blocked = _merge_intervals(blocked_intervals)
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


def _build_active_intervals(
    afk_events: Sequence[Event],
    window_events: Sequence[Event],
    *,
    always_active_pattern: str,
) -> List[NumericInterval]:
    base_intervals = [
        interval
        for interval in (
            _event_to_interval(event)
            for event in afk_events
            if isinstance(event.data, dict) and event.data.get("status") == "not-afk"
        )
        if interval
    ]

    if not always_active_pattern:
        return _merge_intervals(base_intervals)

    try:
        regex = re.compile(always_active_pattern)
    except re.error:
        return _merge_intervals(base_intervals)

    forced_intervals = [
        interval
        for interval in (
            _event_to_interval(event)
            for event in window_events
            if _matches_always_active(regex, event.data or {})
        )
        if interval
    ]
    return _merge_intervals([*base_intervals, *forced_intervals])


def _matches_always_active(regex, data: Dict[str, Any]) -> bool:
    app = data.get("app") if isinstance(data.get("app"), str) else ""
    title = data.get("title") if isinstance(data.get("title"), str) else ""
    return bool(regex.search(app) or regex.search(title))


def _compile_category_rules(rules: Sequence[Any]) -> List[CompiledCategoryRule]:
    compiled_rules: List[CompiledCategoryRule] = []
    for rule in rules:
        if not isinstance(rule, list) or len(rule) != 2:
            continue
        category_name, definition = rule
        if not isinstance(definition, dict):
            continue
        if definition.get("type") != "regex" or not definition.get("regex"):
            continue

        flags = re.MULTILINE
        if definition.get("ignore_case"):
            flags |= re.IGNORECASE

        try:
            compiled_rules.append(
                CompiledCategoryRule(
                    category=_normalize_category_name(category_name),
                    regex=re.compile(str(definition["regex"]), flags),
                )
            )
        except re.error:
            continue
    return compiled_rules


def _normalize_category_name(category: Any) -> List[str]:
    if isinstance(category, list) and category:
        return [str(part) for part in category]
    if isinstance(category, str) and category.strip():
        return [category.strip()]
    return list(UNCATEGORIZED_CATEGORY_NAME)


def _resolve_category_for_data(
    data: Dict[str, Any], compiled_rules: Sequence[CompiledCategoryRule]
) -> List[str]:
    manual_category = _manual_away_category_from_data(data)
    if manual_category is not None:
        return manual_category

    app = data.get("app") if isinstance(data.get("app"), str) else ""
    title = data.get("title") if isinstance(data.get("title"), str) else ""

    matches = [
        rule.category
        for rule in compiled_rules
        if rule.regex.search(app) or rule.regex.search(title)
    ]
    if not matches:
        return list(UNCATEGORIZED_CATEGORY_NAME)
    return max(matches, key=len)


def _manual_away_category_from_data(data: Dict[str, Any]) -> Optional[List[str]]:
    explicit_category = data.get("$category")
    if isinstance(explicit_category, list) and explicit_category:
        return [str(part) for part in explicit_category]
    if isinstance(explicit_category, str) and explicit_category.strip():
        return [explicit_category.strip()]

    is_manual_away = data.get("$manual_away") is True or (
        isinstance(data.get("label"), str) and isinstance(data.get("running"), bool)
    )
    if not is_manual_away:
        return None

    label = data.get("label").strip() if isinstance(data.get("label"), str) else ""
    return [label] if label else list(UNCATEGORIZED_CATEGORY_NAME)


def _build_period_bounds(periods: Sequence[str]) -> List[PeriodBound]:
    period_bounds = []
    for period in periods:
        try:
            start_iso, end_iso = period.split("/")
            start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        start_ms = _datetime_to_ms(start)
        end_ms = _datetime_to_ms(end)
        if end_ms <= start_ms:
            continue
        period_bounds.append(PeriodBound(period, start_ms, end_ms))
    return period_bounds


def _find_first_overlapping_period(period_bounds: Sequence[PeriodBound], event_start_ms: float) -> int:
    low = 0
    high = len(period_bounds)
    while low < high:
        mid = (low + high) >> 1
        if period_bounds[mid].end_ms <= event_start_ms:
            low = mid + 1
        else:
            high = mid
    return low


def _accumulate_slice(
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
    category = _resolve_category_for_data(data, compiled_rules)
    category_key = json.dumps(category)
    app = data.get("app").strip() if isinstance(data.get("app"), str) else ""

    # Uncategorized management should ignore current category filters so the UI can
    # always show unresolved apps even when the active view is filtered.
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

    period_index = _find_first_overlapping_period(period_bounds, start_ms)
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


def _build_event_json(timestamp_ms: float, duration: float, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat(),
        "duration": duration,
        "data": data,
    }


def _duration_seconds(event: Event) -> float:
    duration = event.duration
    if hasattr(duration, "total_seconds"):
        return float(duration.total_seconds())
    return float(duration)


def _datetime_to_ms(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp() * 1000
