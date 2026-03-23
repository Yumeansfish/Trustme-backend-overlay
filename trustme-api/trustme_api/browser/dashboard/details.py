import re
from datetime import datetime
from typing import Dict, List, Mapping, Sequence
from urllib.parse import urlparse

from aw_core.models import Event

from .summary_snapshot_models import LOCAL_AGGREGATION_LIMIT, NumericInterval, duration_seconds
from .summary_snapshot_response import build_event_json
from .summary_snapshot_segments import event_to_interval, fetch_events, merge_intervals


BROWSER_APPNAME_REGEX = {
    "chrome": r"^(google[-_ ]?chrome|chrome|chromium)",
    "firefox": r"(firefox|librewolf|waterfox|nightly)",
    "opera": r"(opera)",
    "brave": r"(brave)",
    "edge": r"^(microsoft[-_ ]?edge|msedge)",
    "arc": r"^arc(\.exe)?$",
    "vivaldi": r"(vivaldi)",
    "orion": r"(orion)",
    "yandex": r"(yandex)",
    "zen": r"(zen)",
    "floorp": r"(floorp)",
    "helium": r"(helium)",
}


def build_dashboard_details(
    db,
    *,
    range_start: datetime,
    range_end: datetime,
    window_buckets: Sequence[str],
    browser_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
) -> Dict[str, object]:
    if range_end <= range_start:
        return {
            "browser": empty_browser_summary(),
            "stopwatch": empty_stopwatch_summary(),
        }

    return {
        "browser": build_browser_summary(
            db,
            range_start=range_start,
            range_end=range_end,
            window_buckets=window_buckets,
            browser_buckets=browser_buckets,
        ),
        "stopwatch": build_stopwatch_summary(
            db,
            range_start=range_start,
            range_end=range_end,
            stopwatch_buckets=stopwatch_buckets,
        ),
    }


def build_browser_summary(
    db,
    *,
    range_start: datetime,
    range_end: datetime,
    window_buckets: Sequence[str],
    browser_buckets: Sequence[str],
) -> Dict[str, object]:
    if not window_buckets or not browser_buckets or range_end <= range_start:
        return empty_browser_summary()

    window_events = fetch_events(db, window_buckets, range_start, range_end)
    browser_events = fetch_events(db, browser_buckets, range_start, range_end)
    focus_intervals = _build_browser_focus_intervals(window_events, browser_buckets)
    if not browser_events or not focus_intervals:
        return empty_browser_summary()

    domain_groups: Dict[str, Dict[str, object]] = {}
    url_groups: Dict[str, Dict[str, object]] = {}
    title_groups: Dict[str, Dict[str, object]] = {}
    total_duration = 0.0

    for raw_data, timestamp_ms, duration in _iter_browser_overlaps(browser_events, focus_intervals):
        total_duration += duration
        _accumulate_browser_slice(
            raw_data,
            timestamp_ms,
            duration,
            domain_groups,
            url_groups,
            title_groups,
        )

    return {
        "domains": _serialize_grouped_events(domain_groups, "$domain"),
        "urls": _serialize_grouped_events(url_groups, "url"),
        "titles": _serialize_grouped_events(title_groups, "title"),
        "duration": total_duration,
    }


def build_stopwatch_summary(
    db,
    *,
    range_start: datetime,
    range_end: datetime,
    stopwatch_buckets: Sequence[str],
) -> Dict[str, object]:
    if not stopwatch_buckets or range_end <= range_start:
        return empty_stopwatch_summary()

    grouped: Dict[str, Dict[str, object]] = {}
    for event in fetch_events(db, stopwatch_buckets, range_start, range_end):
        data = event.data if isinstance(event.data, Mapping) else {}
        if data.get("running") is not False:
            continue

        label = data.get("label")
        if not isinstance(label, str) or not label.strip():
            continue

        _accumulate_grouped_event(
            grouped,
            label.strip(),
            label.strip(),
            event.timestamp.timestamp() * 1000,
            duration_seconds(event),
        )

    return {"stopwatch_events": _serialize_grouped_events(grouped, "label")}


def empty_browser_summary() -> Dict[str, object]:
    return {"domains": [], "urls": [], "titles": [], "duration": 0.0}


def empty_stopwatch_summary() -> Dict[str, object]:
    return {"stopwatch_events": []}


def _iter_browser_overlaps(
    browser_events: Sequence[Event],
    focus_intervals: Sequence[NumericInterval],
):
    interval_index = 0
    for event in browser_events:
        event_interval = event_to_interval(event)
        if event_interval is None:
            continue

        interval_index = _advance_focus_interval_index(
            focus_intervals,
            interval_index,
            event_interval.start_ms,
        )
        for overlap_start, overlap_end in _iter_focus_interval_overlaps(
            event_interval,
            focus_intervals,
            interval_index,
        ):
            yield event.data, overlap_start, (overlap_end - overlap_start) / 1000


def _advance_focus_interval_index(
    focus_intervals: Sequence[NumericInterval],
    start_index: int,
    event_start_ms: float,
) -> int:
    index = start_index
    while index < len(focus_intervals) and focus_intervals[index].end_ms <= event_start_ms:
        index += 1
    return index


def _iter_focus_interval_overlaps(
    event_interval: NumericInterval,
    focus_intervals: Sequence[NumericInterval],
    start_index: int,
):
    index = start_index
    while index < len(focus_intervals):
        interval = focus_intervals[index]
        if interval.start_ms >= event_interval.end_ms:
            return

        overlap_start = max(event_interval.start_ms, interval.start_ms)
        overlap_end = min(event_interval.end_ms, interval.end_ms)
        if overlap_end > overlap_start:
            yield overlap_start, overlap_end

        if interval.end_ms >= event_interval.end_ms:
            return
        index += 1


def _build_browser_focus_intervals(
    window_events: Sequence[Event],
    browser_buckets: Sequence[str],
) -> List[NumericInterval]:
    bucket_keys = list(
        {
            key
            for bucket_id in browser_buckets
            for key in BROWSER_APPNAME_REGEX
            if key in bucket_id.lower()
        }
    )
    if not bucket_keys:
        return []

    intervals = [
        interval
        for interval in (
            event_to_interval(event)
            for event in window_events
            if _window_event_matches_browser(event, bucket_keys)
        )
        if interval is not None
    ]
    return merge_intervals(intervals)


def _window_event_matches_browser(event: Event, bucket_keys: Sequence[str]) -> bool:
    data = event.data if isinstance(event.data, Mapping) else {}
    app = data.get("app")
    if not isinstance(app, str) or not app:
        return False

    lowered = app.lower()
    for key in bucket_keys:
        pattern = BROWSER_APPNAME_REGEX.get(key)
        if pattern is None:
            continue
        try:
            if re.search(pattern, lowered, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _accumulate_browser_slice(
    raw_data,
    timestamp_ms: float,
    duration: float,
    domain_groups: Dict[str, Dict[str, object]],
    url_groups: Dict[str, Dict[str, object]],
    title_groups: Dict[str, Dict[str, object]],
) -> None:
    data = dict(raw_data) if isinstance(raw_data, Mapping) else {}
    url = data.get("url")
    title = data.get("title")
    domain = ""

    if isinstance(url, str) and url.strip():
        parsed = urlparse(url.strip())
        domain = parsed.netloc or parsed.hostname or ""
        _accumulate_grouped_event(url_groups, url.strip(), url.strip(), timestamp_ms, duration)

    if domain:
        _accumulate_grouped_event(domain_groups, domain, domain, timestamp_ms, duration)

    if isinstance(title, str) and title.strip():
        _accumulate_grouped_event(title_groups, title.strip(), title.strip(), timestamp_ms, duration)


def _accumulate_grouped_event(
    grouped: Dict[str, Dict[str, object]],
    key: str,
    value: str,
    timestamp_ms: float,
    duration: float,
) -> None:
    current = grouped.get(key)
    if current is None:
        grouped[key] = {
            "value": value,
            "timestamp_ms": timestamp_ms,
            "duration": duration,
        }
        return

    current["duration"] = float(current["duration"]) + duration
    current["timestamp_ms"] = min(float(current["timestamp_ms"]), timestamp_ms)


def _serialize_grouped_events(
    grouped: Dict[str, Dict[str, object]],
    field_name: str,
) -> List[Dict[str, object]]:
    ordered = sorted(grouped.values(), key=lambda item: float(item["duration"]), reverse=True)
    return [
        build_event_json(
            float(entry["timestamp_ms"]),
            float(entry["duration"]),
            {field_name: str(entry["value"])},
        )
        for entry in ordered[:LOCAL_AGGREGATION_LIMIT]
    ]
