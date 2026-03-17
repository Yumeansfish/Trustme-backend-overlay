from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from aw_core.models import Event


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


def datetime_to_ms(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp() * 1000


def duration_seconds(event: Event) -> float:
    duration = event.duration
    if hasattr(duration, "total_seconds"):
        return float(duration.total_seconds())
    return float(duration)
