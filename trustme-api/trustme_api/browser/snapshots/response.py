from datetime import datetime, timezone
from typing import Any, Dict, Sequence

from .dashboard_dto import SummarySnapshotResponse
from .summary_snapshot_models import (
    LOCAL_AGGREGATION_LIMIT,
    PeriodBound,
    SummarySegment,
    datetime_to_ms,
)


def empty_summary_snapshot(category_periods: Sequence[str]) -> SummarySnapshotResponse:
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
                build_event_json(
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
                build_event_json(entry["timestamp_ms"], entry["duration"], {"app": app})
                for app, entry in sorted(
                    app_durations.items(), key=lambda item: item[1]["duration"], reverse=True
                )[:LOCAL_AGGREGATION_LIMIT]
            ],
            "title_events": [],
            "cat_events": [
                build_event_json(
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


def build_event_json(timestamp_ms: float, duration: float, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat(),
        "duration": duration,
        "data": data,
    }
