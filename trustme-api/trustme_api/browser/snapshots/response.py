from datetime import datetime, timezone
from typing import Any, Dict, Sequence

from .dashboard_dto import SummarySnapshotResponse, serialize_summary_snapshot_response
from .summary_snapshot_models import (
    LOCAL_AGGREGATION_LIMIT,
    PeriodBound,
    SummarySegment,
    datetime_to_ms,
)


def empty_summary_snapshot(category_periods: Sequence[str]) -> SummarySnapshotResponse:
    return serialize_summary_snapshot_response(
        {
            "window": {
                "app_events": [],
                "title_events": [],
                "cat_events": [],
                "active_events": [],
                "duration": 0,
            },
            "by_period": {period: {"cat_events": []} for period in category_periods},
            "uncategorized_rows": [],
        },
        category_periods=category_periods,
    )


def deserialize_segments(raw_segments: Dict[str, Dict[str, Any]]) -> Dict[str, SummarySegment]:
    segments = {}
    for logical_period, row in raw_segments.items():
        payload = row["payload"]
        segments[logical_period] = SummarySegment(
            logical_period=logical_period,
            computed_end_ms=datetime_to_ms(
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
                    "category": list(entry.get("category") or []),
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


def serialize_summary_segment(segment: SummarySegment) -> Dict[str, Any]:
    return {
        "duration": segment.duration,
        "apps": segment.apps,
        "categories": segment.categories,
        "uncategorized_apps": segment.uncategorized_apps,
    }


def merge_summary_segments(base: SummarySegment, delta: SummarySegment) -> SummarySegment:
    apps = _clone_duration_entries(base.apps)
    categories = _clone_category_entries(base.categories)
    uncategorized_apps = _clone_duration_entries(base.uncategorized_apps)

    _merge_duration_entries(apps, delta.apps)
    _merge_category_entries(categories, delta.categories)
    _merge_duration_entries(uncategorized_apps, delta.uncategorized_apps)

    return SummarySegment(
        logical_period=base.logical_period,
        computed_end_ms=max(base.computed_end_ms, delta.computed_end_ms),
        duration=base.duration + delta.duration,
        apps=apps,
        categories=categories,
        uncategorized_apps=uncategorized_apps,
    )


def build_snapshot_response(
    period_bounds: Sequence[PeriodBound],
    segments: Dict[str, SummarySegment],
) -> SummarySnapshotResponse:
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
        _merge_duration_entries(app_durations, segment.apps)
        _merge_category_entries(category_durations, segment.categories)
        _merge_duration_entries(uncategorized_apps, segment.uncategorized_apps)
        by_period[period.key] = _build_period_snapshot(period, segment)

    return serialize_summary_snapshot_response(
        {
            "window": {
                "app_events": _build_duration_window_events(app_durations, "app"),
                "title_events": [],
                "cat_events": _build_category_window_events(category_durations),
                "active_events": [],
                "duration": total_duration,
            },
            "by_period": by_period,
            "uncategorized_rows": _build_uncategorized_rows(uncategorized_apps),
        },
        category_periods=[period.key for period in period_bounds],
    )


def _clone_duration_entries(entries: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    return {
        key: {
            "duration": float(entry["duration"]),
            "timestamp_ms": float(entry["timestamp_ms"]),
        }
        for key, entry in entries.items()
    }


def _clone_category_entries(entries: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        key: {
            "category": list(entry["category"]),
            "duration": float(entry["duration"]),
            "timestamp_ms": float(entry["timestamp_ms"]),
        }
        for key, entry in entries.items()
    }


def _merge_duration_entries(
    aggregated: Dict[str, Dict[str, float]],
    incoming: Dict[str, Dict[str, Any]],
) -> None:
    for key, entry in incoming.items():
        existing = aggregated.get(key)
        if existing is None:
            aggregated[key] = {
                "duration": float(entry["duration"]),
                "timestamp_ms": float(entry["timestamp_ms"]),
            }
            continue

        existing["duration"] += float(entry["duration"])
        existing["timestamp_ms"] = min(existing["timestamp_ms"], float(entry["timestamp_ms"]))


def _merge_category_entries(
    aggregated: Dict[str, Dict[str, Any]],
    incoming: Dict[str, Dict[str, Any]],
) -> None:
    for key, entry in incoming.items():
        existing = aggregated.get(key)
        if existing is None:
            aggregated[key] = {
                "category": list(entry["category"]),
                "duration": float(entry["duration"]),
                "timestamp_ms": float(entry["timestamp_ms"]),
            }
            continue

        existing["duration"] += float(entry["duration"])
        existing["timestamp_ms"] = min(existing["timestamp_ms"], float(entry["timestamp_ms"]))


def _build_period_snapshot(period: PeriodBound, segment: SummarySegment) -> Dict[str, Any]:
    ordered_categories = sorted(
        segment.categories.values(),
        key=lambda item: item["duration"],
        reverse=True,
    )
    return {
        "cat_events": [
            build_event_json(
                period.start_ms,
                entry["duration"],
                {"$category": entry["category"]},
            )
            for entry in ordered_categories
        ]
    }


def _build_duration_window_events(
    aggregated: Dict[str, Dict[str, float]],
    field_name: str,
) -> list[Dict[str, Any]]:
    ordered_items = sorted(
        aggregated.items(),
        key=lambda item: item[1]["duration"],
        reverse=True,
    )
    return [
        build_event_json(entry["timestamp_ms"], entry["duration"], {field_name: key})
        for key, entry in ordered_items[:LOCAL_AGGREGATION_LIMIT]
    ]


def _build_category_window_events(
    aggregated: Dict[str, Dict[str, Any]],
) -> list[Dict[str, Any]]:
    ordered_categories = sorted(
        aggregated.values(),
        key=lambda item: item["duration"],
        reverse=True,
    )
    return [
        build_event_json(
            entry["timestamp_ms"],
            entry["duration"],
            {"$category": entry["category"]},
        )
        for entry in ordered_categories[:LOCAL_AGGREGATION_LIMIT]
    ]


def _build_uncategorized_rows(
    uncategorized_apps: Dict[str, Dict[str, float]],
) -> list[Dict[str, Any]]:
    ordered_items = sorted(
        uncategorized_apps.items(),
        key=lambda item: item[1]["duration"],
        reverse=True,
    )
    return [
        {
            "key": app,
            "app": app,
            "title": app,
            "subtitle": "",
            "duration": entry["duration"],
            "matchText": app,
        }
        for app, entry in ordered_items[:LOCAL_AGGREGATION_LIMIT]
    ]


def build_event_json(timestamp_ms: float, duration: float, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat(),
        "duration": duration,
        "data": data,
    }
