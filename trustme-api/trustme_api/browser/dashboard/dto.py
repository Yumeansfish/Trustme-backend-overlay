from typing import Dict, List, Optional, TypedDict


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
