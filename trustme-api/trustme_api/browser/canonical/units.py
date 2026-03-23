import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time as daytime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from .dashboard_domain_service import DashboardSummaryScope
from .dashboard_summary_warmup import _resolve_local_timezone
from .experimental_canonical_strategy import PERSISTED_UNIT_KINDS
from .settings_schema import normalize_settings_data
from .summary_snapshot import build_summary_snapshot_scope_key
from .summary_snapshot_categories import compile_category_rules, normalize_category_name
from .summary_snapshot_models import PeriodBound, SummarySegment, datetime_to_ms
from .summary_snapshot_response import (
    build_snapshot_response,
    merge_summary_segments,
)
from .summary_snapshot_segments import build_summary_segment, empty_summary_segment


UNIT_RANK = {"hour": 0, "day": 1, "month": 2}
SCENARIO_NAMES = (
    "preset_week",
    "preset_month",
    "preset_year",
    "custom_6h",
    "custom_36h",
    "custom_7d_partial",
    "custom_30d_partial",
)


@dataclass(frozen=True)
class CalendarProfile:
    timezone_name: str
    timezone_obj: Any
    start_of_day: str
    start_of_week: str
    offset: timedelta

    @property
    def key(self) -> str:
        payload = {
            "timezone": self.timezone_name,
            "start_of_day": self.start_of_day,
            "start_of_week": self.start_of_week,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        return digest.hexdigest()

    def normalize(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=self.timezone_obj)
        return value.astimezone(self.timezone_obj)


@dataclass(frozen=True)
class TimeRange:
    kind: str
    start: datetime
    end: datetime

    @property
    def key(self) -> str:
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


@dataclass(frozen=True)
class BenchmarkQuery:
    name: str
    range_start: datetime
    range_end: datetime
    bucket_kind: str


@dataclass
class QueryStats:
    bucket_count: int = 0
    store_hits: int = 0
    store_misses: int = 0
    raw_unit_builds: Dict[str, int] = field(default_factory=dict)
    derived_unit_builds: Dict[str, int] = field(default_factory=dict)
    planned_units: Dict[str, int] = field(default_factory=dict)

    def note_planned(self, kind: str) -> None:
        self.planned_units[kind] = self.planned_units.get(kind, 0) + 1

    def note_raw_build(self, kind: str) -> None:
        self.raw_unit_builds[kind] = self.raw_unit_builds.get(kind, 0) + 1

    def note_derived_build(self, kind: str) -> None:
        self.derived_unit_builds[kind] = self.derived_unit_builds.get(kind, 0) + 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "bucket_count": self.bucket_count,
            "store_hits": self.store_hits,
            "store_misses": self.store_misses,
            "raw_unit_builds": dict(sorted(self.raw_unit_builds.items())),
            "derived_unit_builds": dict(sorted(self.derived_unit_builds.items())),
            "planned_units": dict(sorted(self.planned_units.items())),
        }


class InMemoryCanonicalUnitStore:
    def __init__(self) -> None:
        self._segments: Dict[Tuple[str, str, str, str, str], SummarySegment] = {}

    def get(
        self,
        *,
        scope_key: str,
        calendar_key: str,
        unit_kind: str,
        unit_start: datetime,
        unit_end: datetime,
    ) -> Optional[SummarySegment]:
        return self._segments.get(
            (
                scope_key,
                calendar_key,
                unit_kind,
                unit_start.isoformat(),
                unit_end.isoformat(),
            )
        )

    def put(
        self,
        *,
        scope_key: str,
        calendar_key: str,
        unit_kind: str,
        unit_start: datetime,
        unit_end: datetime,
        segment: SummarySegment,
    ) -> None:
        self._segments[
            (
                scope_key,
                calendar_key,
                unit_kind,
                unit_start.isoformat(),
                unit_end.isoformat(),
            )
        ] = segment

    def clear(self) -> None:
        self._segments.clear()

    def count_by_kind(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for _, _, kind, _, _ in self._segments:
            counts[kind] = counts.get(kind, 0) + 1
        return dict(sorted(counts.items()))


class CanonicalUnitStoreProtocol(Protocol):
    def get(
        self,
        *,
        scope_key: str,
        calendar_key: str,
        unit_kind: str,
        unit_start: datetime,
        unit_end: datetime,
    ) -> Optional[SummarySegment]: ...

    def put(
        self,
        *,
        scope_key: str,
        calendar_key: str,
        unit_kind: str,
        unit_start: datetime,
        unit_end: datetime,
        segment: SummarySegment,
    ) -> None: ...

    def clear(self) -> None: ...

    def count_by_kind(self) -> Dict[str, int]: ...


def build_calendar_profile(
    settings_data: Dict[str, Any],
    *,
    local_timezone=None,
) -> CalendarProfile:
    normalized, _ = normalize_settings_data(settings_data)
    timezone_obj = local_timezone or _resolve_local_timezone() or timezone.utc
    timezone_name = getattr(timezone_obj, "key", None) or str(timezone_obj)
    start_of_day = str(normalized["startOfDay"])
    return CalendarProfile(
        timezone_name=timezone_name,
        timezone_obj=timezone_obj,
        start_of_day=start_of_day,
        start_of_week=str(normalized["startOfWeek"]),
        offset=_offset_duration(start_of_day),
    )


def build_benchmark_queries(
    settings_data: Dict[str, Any],
    *,
    scenario_names: Optional[Sequence[str]] = None,
    now: Optional[datetime] = None,
    local_timezone=None,
) -> List[BenchmarkQuery]:
    profile = build_calendar_profile(settings_data, local_timezone=local_timezone)
    effective_now = profile.normalize(now or datetime.now(profile.timezone_obj))
    closed_hour = floor_to_hour(effective_now)
    if closed_hour <= effective_now - timedelta(hours=1):
        closed_hour = closed_hour + timedelta(hours=1)
    current_end = closed_hour
    partial_end = current_end - timedelta(hours=5)

    queries = {
        "preset_week": BenchmarkQuery(
            name="preset_week",
            range_start=week_start_for(current_end, profile),
            range_end=current_end,
            bucket_kind="day",
        ),
        "preset_month": BenchmarkQuery(
            name="preset_month",
            range_start=month_start_for(current_end, profile),
            range_end=current_end,
            bucket_kind="day",
        ),
        "preset_year": BenchmarkQuery(
            name="preset_year",
            range_start=year_start_for(current_end, profile),
            range_end=current_end,
            bucket_kind="month",
        ),
        "custom_6h": BenchmarkQuery(
            name="custom_6h",
            range_start=current_end - timedelta(hours=6),
            range_end=current_end,
            bucket_kind="hour",
        ),
        "custom_36h": BenchmarkQuery(
            name="custom_36h",
            range_start=current_end - timedelta(hours=36),
            range_end=current_end,
            bucket_kind="hour",
        ),
        "custom_7d_partial": BenchmarkQuery(
            name="custom_7d_partial",
            range_start=partial_end - timedelta(days=7),
            range_end=partial_end,
            bucket_kind="day",
        ),
        "custom_30d_partial": BenchmarkQuery(
            name="custom_30d_partial",
            range_start=partial_end - timedelta(days=30),
            range_end=partial_end,
            bucket_kind="day",
        ),
    }
    selected = scenario_names or SCENARIO_NAMES
    return [queries[name] for name in selected]


def build_bucket_ranges(
    range_start: datetime,
    range_end: datetime,
    *,
    bucket_kind: str,
    profile: CalendarProfile,
) -> List[TimeRange]:
    cursor = profile.normalize(range_start)
    limit = profile.normalize(range_end)
    buckets: List[TimeRange] = []

    while cursor < limit:
        if bucket_kind == "hour":
            next_cursor = min(next_hour_start(cursor), limit)
        elif bucket_kind == "day":
            next_cursor = min(next_day_start_for(cursor, profile), limit)
        elif bucket_kind == "month":
            next_cursor = min(next_month_start_for(cursor, profile), limit)
        else:  # pragma: no cover
            raise ValueError(f"Unsupported bucket kind: {bucket_kind}")
        buckets.append(TimeRange(bucket_kind, cursor, next_cursor))
        cursor = next_cursor

    return buckets


def plan_covering_units(
    range_start: datetime,
    range_end: datetime,
    *,
    bucket_kind: str,
    profile: CalendarProfile,
    persisted_unit_kinds: Sequence[str],
) -> List[TimeRange]:
    allowed_kinds = _allowed_unit_kinds(bucket_kind, persisted_unit_kinds)
    cursor = profile.normalize(range_start)
    limit = profile.normalize(range_end)
    plan: List[TimeRange] = []

    while cursor < limit:
        matched = False
        for kind in reversed(allowed_kinds):
            if not _is_unit_boundary(cursor, kind, profile):
                continue
            next_cursor = _next_unit_start(cursor, kind, profile)
            if next_cursor <= limit:
                plan.append(TimeRange(kind, cursor, next_cursor))
                cursor = next_cursor
                matched = True
                break

        if matched:
            continue

        if "hour" not in allowed_kinds:
            raise ValueError("Hour units are required to cover partial bucket edges")

        next_cursor = min(next_hour_start(cursor), limit)
        plan.append(TimeRange("hour", cursor, next_cursor))
        cursor = next_cursor

    return plan


class ExperimentalCanonicalQueryEngine:
    def __init__(
        self,
        *,
        db,
        scope: DashboardSummaryScope,
        settings_data: Dict[str, Any],
        store: Optional[CanonicalUnitStoreProtocol] = None,
        persisted_unit_kinds: Sequence[str] = PERSISTED_UNIT_KINDS,
        local_timezone=None,
    ) -> None:
        self.db = db
        self.scope = scope
        self.persisted_unit_kinds = tuple(
            kind for kind in ("hour", "day", "month") if kind in set(persisted_unit_kinds)
        )
        self.profile = build_calendar_profile(settings_data, local_timezone=local_timezone)
        self.scope_key = build_summary_snapshot_scope_key(
            window_buckets=scope.window_buckets,
            afk_buckets=scope.afk_buckets,
            stopwatch_buckets=scope.stopwatch_buckets,
            filter_afk=scope.filter_afk,
            categories=scope.categories,
            filter_categories=scope.filter_categories,
            always_active_pattern=scope.always_active_pattern,
        )
        self.allowed_categories = (
            {
                json.dumps(normalize_category_name(category), separators=(",", ":"))
                for category in scope.filter_categories
            }
            if scope.filter_categories
            else None
        )
        self.store = store or InMemoryCanonicalUnitStore()

    def execute_query(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        bucket_kind: str,
    ) -> Dict[str, Any]:
        if range_end <= range_start:
            return {
                "response": build_snapshot_response([], {}),
                "stats": QueryStats().as_dict(),
            }

        compiled_rules = compile_category_rules(self.scope.categories)
        category_cache: Dict[Tuple[str, str, str], List[str]] = {}
        stats = QueryStats()
        bucket_ranges = build_bucket_ranges(
            range_start,
            range_end,
            bucket_kind=bucket_kind,
            profile=self.profile,
        )
        stats.bucket_count = len(bucket_ranges)

        segments: Dict[str, SummarySegment] = {}
        period_bounds: List[PeriodBound] = []
        for bucket in bucket_ranges:
            bucket_segment = self._build_interval_segment(
                bucket,
                compiled_rules=compiled_rules,
                category_cache=category_cache,
                stats=stats,
            )
            segments[bucket.key] = bucket_segment
            period_bounds.append(
                PeriodBound(
                    bucket.key,
                    datetime_to_ms(bucket.start),
                    datetime_to_ms(bucket.end),
                )
            )

        return {
            "response": build_snapshot_response(period_bounds, segments),
            "stats": stats.as_dict(),
        }

    def _build_interval_segment(
        self,
        interval: TimeRange,
        *,
        compiled_rules,
        category_cache,
        stats: QueryStats,
    ) -> SummarySegment:
        if (
            interval.kind in self.persisted_unit_kinds
            and _is_full_unit_interval(interval.start, interval.end, interval.kind, self.profile)
        ):
            return self._get_or_build_persisted_unit(
                unit_kind=interval.kind,
                unit_start=interval.start,
                effective_end=interval.end,
                compiled_rules=compiled_rules,
                category_cache=category_cache,
                stats=stats,
            )

        plan = plan_covering_units(
            interval.start,
            interval.end,
            bucket_kind=interval.kind,
            profile=self.profile,
            persisted_unit_kinds=self.persisted_unit_kinds,
        )
        segment = empty_summary_segment(interval.key, datetime_to_ms(interval.start))
        for unit in plan:
            stats.note_planned(unit.kind)
            unit_segment = self._get_or_build_persisted_unit(
                unit_kind=unit.kind,
                unit_start=unit.start,
                effective_end=unit.end,
                compiled_rules=compiled_rules,
                category_cache=category_cache,
                stats=stats,
            )
            segment = merge_summary_segments(segment, unit_segment)
        return segment

    def _get_or_build_persisted_unit(
        self,
        *,
        unit_kind: str,
        unit_start: datetime,
        effective_end: datetime,
        compiled_rules,
        category_cache,
        stats: QueryStats,
    ) -> SummarySegment:
        if unit_kind not in self.persisted_unit_kinds:
            raise ValueError(f"Unsupported persisted unit kind: {unit_kind}")

        unit_start = self.profile.normalize(unit_start)
        effective_end = self.profile.normalize(effective_end)
        unit_end = _next_unit_start(unit_start, unit_kind, self.profile)
        unit_key = f"{unit_kind}:{unit_start.isoformat()}/{unit_end.isoformat()}"
        existing = self.store.get(
            scope_key=self.scope_key,
            calendar_key=self.profile.key,
            unit_kind=unit_kind,
            unit_start=unit_start,
            unit_end=unit_end,
        )
        effective_end_ms = datetime_to_ms(effective_end)
        if existing is not None and existing.computed_end_ms >= effective_end_ms:
            stats.store_hits += 1
            return existing

        stats.store_misses += 1
        working = existing or empty_summary_segment(unit_key, datetime_to_ms(unit_start))
        compute_start = unit_start
        if existing is not None and existing.computed_end_ms > datetime_to_ms(unit_start):
            compute_start = datetime.fromtimestamp(
                existing.computed_end_ms / 1000,
                tz=self.profile.timezone_obj,
            )
        if compute_start >= effective_end:
            return working

        if unit_kind in {"hour", "day"}:
            stats.note_raw_build(unit_kind)
            delta = self._build_raw_segment(
                logical_period=unit_key,
                segment_start=compute_start,
                segment_end=effective_end,
                compiled_rules=compiled_rules,
                category_cache=category_cache,
            )
        elif unit_kind == "month":
            stats.note_derived_build(unit_kind)
            delta = self._compose_month_segment(
                segment_start=compute_start,
                segment_end=effective_end,
                compiled_rules=compiled_rules,
                category_cache=category_cache,
                stats=stats,
            )
        else:  # pragma: no cover
            raise ValueError(f"Unsupported unit kind: {unit_kind}")

        merged = merge_summary_segments(working, delta)
        self.store.put(
            scope_key=self.scope_key,
            calendar_key=self.profile.key,
            unit_kind=unit_kind,
            unit_start=unit_start,
            unit_end=unit_end,
            segment=merged,
        )
        return merged

    def _build_raw_segment(
        self,
        *,
        logical_period: str,
        segment_start: datetime,
        segment_end: datetime,
        compiled_rules,
        category_cache,
    ) -> SummarySegment:
        return build_summary_segment(
            self.db,
            logical_period=logical_period,
            segment_start=segment_start,
            segment_end=segment_end,
            window_buckets=self.scope.window_buckets,
            afk_buckets=self.scope.afk_buckets,
            stopwatch_buckets=self.scope.stopwatch_buckets,
            filter_afk=self.scope.filter_afk,
            compiled_rules=compiled_rules,
            allowed_categories=self.allowed_categories,
            always_active_pattern=self.scope.always_active_pattern,
            category_cache=category_cache,
        )

    def _compose_month_segment(
        self,
        *,
        segment_start: datetime,
        segment_end: datetime,
        compiled_rules,
        category_cache,
        stats: QueryStats,
    ) -> SummarySegment:
        lower_plan = plan_covering_units(
            segment_start,
            segment_end,
            bucket_kind="month",
            profile=self.profile,
            persisted_unit_kinds=("hour", "day"),
        )
        segment = empty_summary_segment(
            f"month:{segment_start.isoformat()}/{segment_end.isoformat()}",
            datetime_to_ms(segment_start),
        )
        for unit in lower_plan:
            stats.note_planned(unit.kind)
            unit_segment = self._get_or_build_persisted_unit(
                unit_kind=unit.kind,
                unit_start=unit.start,
                effective_end=unit.end,
                compiled_rules=compiled_rules,
                category_cache=category_cache,
                stats=stats,
            )
            segment = merge_summary_segments(segment, unit_segment)
        return segment


def summarize_stats(stats_list: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    aggregate = QueryStats()
    for stats in stats_list:
        aggregate.bucket_count += int(stats.get("bucket_count", 0))
        aggregate.store_hits += int(stats.get("store_hits", 0))
        aggregate.store_misses += int(stats.get("store_misses", 0))
        for field_name in ("raw_unit_builds", "derived_unit_builds", "planned_units"):
            for key, value in (stats.get(field_name) or {}).items():
                target = getattr(aggregate, field_name)
                target[key] = target.get(key, 0) + int(value)
    return aggregate.as_dict()


def _allowed_unit_kinds(bucket_kind: str, persisted_unit_kinds: Sequence[str]) -> List[str]:
    bucket_rank = UNIT_RANK[bucket_kind]
    return [
        kind
        for kind in ("hour", "day", "month")
        if kind in set(persisted_unit_kinds) and UNIT_RANK[kind] <= bucket_rank
    ]


def _is_unit_boundary(value: datetime, unit_kind: str, profile: CalendarProfile) -> bool:
    if unit_kind == "hour":
        return value == floor_to_hour(value)
    if unit_kind == "day":
        return value == day_start_for(value, profile)
    if unit_kind == "month":
        return value == month_start_for(value, profile)
    raise ValueError(f"Unsupported unit kind: {unit_kind}")


def _is_full_unit_interval(
    start: datetime,
    end: datetime,
    unit_kind: str,
    profile: CalendarProfile,
) -> bool:
    return _is_unit_boundary(start, unit_kind, profile) and end == _next_unit_start(
        start, unit_kind, profile
    )


def _next_unit_start(value: datetime, unit_kind: str, profile: CalendarProfile) -> datetime:
    if unit_kind == "hour":
        return next_hour_start(value)
    if unit_kind == "day":
        return next_day_start_for(value, profile)
    if unit_kind == "month":
        return next_month_start_for(value, profile)
    raise ValueError(f"Unsupported unit kind: {unit_kind}")


def floor_to_hour(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def next_hour_start(value: datetime) -> datetime:
    return floor_to_hour(value) + timedelta(hours=1)


def day_start_for(value: datetime, profile: CalendarProfile) -> datetime:
    value = profile.normalize(value)
    logical = logical_date(value, profile)
    hours, minutes = _parse_start_of_day(profile.start_of_day)
    return datetime.combine(
        logical,
        daytime(hour=hours, minute=minutes),
        tzinfo=profile.timezone_obj,
    )


def next_day_start_for(value: datetime, profile: CalendarProfile) -> datetime:
    return day_start_for(value, profile) + timedelta(days=1)


def week_start_for(value: datetime, profile: CalendarProfile) -> datetime:
    anchor = day_start_for(value, profile)
    if profile.start_of_week == "Monday":
        distance = anchor.weekday()
    else:
        distance = (anchor.weekday() + 1) % 7
    return anchor - timedelta(days=distance)


def month_start_for(value: datetime, profile: CalendarProfile) -> datetime:
    value = profile.normalize(value)
    logical = logical_date(value, profile)
    hours, minutes = _parse_start_of_day(profile.start_of_day)
    return datetime.combine(
        logical.replace(day=1),
        daytime(hour=hours, minute=minutes),
        tzinfo=profile.timezone_obj,
    )


def next_month_start_for(value: datetime, profile: CalendarProfile) -> datetime:
    start = month_start_for(value, profile)
    return _add_months(start, 1)


def year_start_for(value: datetime, profile: CalendarProfile) -> datetime:
    value = profile.normalize(value)
    logical = logical_date(value, profile)
    hours, minutes = _parse_start_of_day(profile.start_of_day)
    return datetime.combine(
        date(logical.year, 1, 1),
        daytime(hour=hours, minute=minutes),
        tzinfo=profile.timezone_obj,
    )


def logical_date(value: datetime, profile: CalendarProfile) -> date:
    return (profile.normalize(value) - profile.offset).date()


def _add_months(value: datetime, count: int) -> datetime:
    month_index = (value.month - 1) + count
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month)


def _parse_start_of_day(value: str) -> Tuple[int, int]:
    parts = value.split(":")
    hours = int(parts[0]) if parts and parts[0] else 0
    minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return hours, minutes


def _offset_duration(start_of_day: str) -> timedelta:
    hours, minutes = _parse_start_of_day(start_of_day)
    return timedelta(hours=hours, minutes=minutes)
