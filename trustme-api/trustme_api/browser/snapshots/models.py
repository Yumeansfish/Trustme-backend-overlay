from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

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
    depth: int


@dataclass(frozen=True)
class CompiledCategoryTermRule:
    category: List[str]
    terms: Tuple[str, ...]
    depth: int
    ignore_case: bool = False


@dataclass(frozen=True)
class CompiledCategoryMatcher:
    exact_apps_case_sensitive: Dict[str, List[str]] = field(default_factory=dict)
    exact_apps_casefolded: Dict[str, List[str]] = field(default_factory=dict)
    domains_case_sensitive: Dict[str, Tuple[int, List[str]]] = field(default_factory=dict)
    domains_casefolded: Dict[str, Tuple[int, List[str]]] = field(default_factory=dict)
    alias_rules: Tuple[CompiledCategoryTermRule, ...] = ()
    title_rules: Tuple[CompiledCategoryTermRule, ...] = ()
    regex_rules: Tuple[CompiledCategoryRule, ...] = ()

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
