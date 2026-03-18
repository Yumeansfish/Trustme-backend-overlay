from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, TypedDict


EventData = TypedDict(
    "EventData",
    {
        "app": str,
        "title": str,
        "subtitle": str,
        "matchText": str,
        "key": str,
        "status": str,
        "running": bool,
        "value": int,
        "value_label": str,
        "emoji": str,
        "label": str,
        "progress": Optional[float],
        "question_id": str,
        "$category": List[str],
    },
    total=False,
)


class AggregatedEvent(TypedDict):
    timestamp: str
    duration: float
    data: EventData


class SummaryWindow(TypedDict):
    app_events: List[AggregatedEvent]
    title_events: List[AggregatedEvent]
    cat_events: List[AggregatedEvent]
    active_events: List[AggregatedEvent]
    duration: float


class SummaryByPeriodEntry(TypedDict):
    cat_events: List[AggregatedEvent]


class UncategorizedRow(TypedDict):
    key: str
    app: str
    title: str
    subtitle: str
    duration: float
    matchText: str


class SummarySnapshotResponse(TypedDict):
    window: SummaryWindow
    by_period: Dict[str, SummaryByPeriodEntry]
    uncategorized_rows: List[UncategorizedRow]


class CheckinAnswer(TypedDict):
    question_id: str
    emoji: str
    label: str
    status: str
    value: Optional[int]
    value_label: str
    progress: Optional[float]


class CheckinSession(TypedDict):
    id: str
    date: str
    started_at: str
    ended_at: str
    timeline_start: str
    timeline_end: str
    duration_seconds: int
    kind: str
    answered_count: int
    skipped_count: int
    answers: List[CheckinAnswer]


class CheckinsResponse(TypedDict):
    data_source: str
    available_dates: List[str]
    sessions: List[CheckinSession]


def _as_string(value: Any, *, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _as_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_string_list(values: Any) -> List[str]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, dict)):
        return []
    return [_as_string(value) for value in values]


def _as_list(values: Any) -> List[Any]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, dict)):
        return []
    return list(values)


def serialize_aggregated_event(payload: Any) -> AggregatedEvent:
    if not isinstance(payload, Mapping):
        payload = {}

    raw_data = payload.get("data")
    normalized_data: EventData = {}
    if isinstance(raw_data, Mapping):
        for key, value in raw_data.items():
            if key == "$category":
                normalized_data[key] = _as_string_list(value)
            elif key == "running":
                normalized_data[key] = bool(value)
            elif key == "value":
                normalized_data[key] = _as_int(value)
            elif key == "progress":
                normalized_data[key] = None if value is None else _as_float(value)
            else:
                normalized_data[key] = _as_string(value)

    return {
        "timestamp": _as_string(payload.get("timestamp")),
        "duration": _as_float(payload.get("duration")),
        "data": normalized_data,
    }


def serialize_summary_window(payload: Any) -> SummaryWindow:
    if not isinstance(payload, Mapping):
        payload = {}

    return {
        "app_events": [
            serialize_aggregated_event(event) for event in _as_list(payload.get("app_events"))
        ],
        "title_events": [
            serialize_aggregated_event(event) for event in _as_list(payload.get("title_events"))
        ],
        "cat_events": [
            serialize_aggregated_event(event) for event in _as_list(payload.get("cat_events"))
        ],
        "active_events": [
            serialize_aggregated_event(event) for event in _as_list(payload.get("active_events"))
        ],
        "duration": _as_float(payload.get("duration")),
    }


def serialize_summary_by_period_entry(payload: Any) -> SummaryByPeriodEntry:
    if not isinstance(payload, Mapping):
        payload = {}

    return {
        "cat_events": [serialize_aggregated_event(event) for event in _as_list(payload.get("cat_events"))]
    }


def serialize_uncategorized_row(payload: Any) -> UncategorizedRow:
    if not isinstance(payload, Mapping):
        payload = {}

    app = _as_string(payload.get("app"))
    title = _as_string(payload.get("title"), default=app)
    return {
        "key": _as_string(payload.get("key"), default=app or title),
        "app": app,
        "title": title,
        "subtitle": _as_string(payload.get("subtitle")),
        "duration": _as_float(payload.get("duration")),
        "matchText": _as_string(payload.get("matchText"), default=title or app),
    }


def serialize_summary_snapshot_response(
    payload: Any,
    *,
    category_periods: Optional[Sequence[str]] = None,
) -> SummarySnapshotResponse:
    if not isinstance(payload, Mapping):
        payload = {}

    raw_by_period = payload.get("by_period")
    normalized_by_period: Dict[str, SummaryByPeriodEntry] = {}
    if isinstance(raw_by_period, Mapping):
        for period_key, period_value in raw_by_period.items():
            normalized_by_period[_as_string(period_key)] = serialize_summary_by_period_entry(
                period_value
            )

    for period in category_periods or []:
        normalized_by_period.setdefault(period, {"cat_events": []})

    return {
        "window": serialize_summary_window(payload.get("window")),
        "by_period": normalized_by_period,
        "uncategorized_rows": [
            serialize_uncategorized_row(row) for row in _as_list(payload.get("uncategorized_rows"))
        ],
    }


def serialize_checkin_answer(payload: Any) -> CheckinAnswer:
    if not isinstance(payload, Mapping):
        payload = {}

    value = payload.get("value")
    progress = payload.get("progress")
    return {
        "question_id": _as_string(payload.get("question_id")),
        "emoji": _as_string(payload.get("emoji")),
        "label": _as_string(payload.get("label")),
        "status": _as_string(payload.get("status")),
        "value": None if value is None else _as_int(value),
        "value_label": _as_string(payload.get("value_label")),
        "progress": None if progress is None else _as_float(progress),
    }


def serialize_checkin_session(payload: Any) -> CheckinSession:
    if not isinstance(payload, Mapping):
        payload = {}

    answers = [serialize_checkin_answer(answer) for answer in _as_list(payload.get("answers"))]
    answered_count = sum(1 for answer in answers if answer["status"] == "answered")
    skipped_count = sum(1 for answer in answers if answer["status"] == "skipped")

    return {
        "id": _as_string(payload.get("id")),
        "date": _as_string(payload.get("date")),
        "started_at": _as_string(payload.get("started_at")),
        "ended_at": _as_string(payload.get("ended_at")),
        "timeline_start": _as_string(payload.get("timeline_start")),
        "timeline_end": _as_string(payload.get("timeline_end")),
        "duration_seconds": _as_int(payload.get("duration_seconds")),
        "kind": _as_string(payload.get("kind")),
        "answered_count": answered_count
        if payload.get("answered_count") is None
        else _as_int(payload.get("answered_count")),
        "skipped_count": skipped_count
        if payload.get("skipped_count") is None
        else _as_int(payload.get("skipped_count")),
        "answers": answers,
    }


def serialize_checkins_response(payload: Any) -> CheckinsResponse:
    if not isinstance(payload, Mapping):
        payload = {}

    return {
        "data_source": _as_string(payload.get("data_source")),
        "available_dates": _as_string_list(payload.get("available_dates")),
        "sessions": [serialize_checkin_session(session) for session in _as_list(payload.get("sessions"))],
    }
