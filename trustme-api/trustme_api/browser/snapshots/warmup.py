import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence
from zoneinfo import ZoneInfo

from .dashboard_domain_service import (
    DashboardSummaryScope,
    build_bucket_records,
    build_dashboard_summary_scopes,
)
from .summary_snapshot import build_summary_snapshot_from_scope


logger = logging.getLogger(__name__)

SUMMARY_WARMUP_PERIOD_ORDER = ("year", "month", "week")
SUMMARY_WARMUP_INTERVAL_SECONDS = 60
LOCALTIME_PATH = Path("/etc/localtime")


@dataclass(frozen=True)
class SummaryWarmupPeriod:
    name: str
    range_start: datetime
    full_end: datetime
    query_end: datetime
    logical_periods: List[str]


@dataclass(frozen=True)
class SummaryWarmupJob:
    group_name: str
    period_name: str
    range_start: datetime
    range_end: datetime
    logical_periods: List[str]
    scope: DashboardSummaryScope

    @property
    def window_buckets(self) -> List[str]:
        return self.scope.window_buckets

    @property
    def afk_buckets(self) -> List[str]:
        return self.scope.afk_buckets

    @property
    def stopwatch_buckets(self) -> List[str]:
        return self.scope.stopwatch_buckets

    @property
    def categories(self) -> List[object]:
        return self.scope.categories

    @property
    def filter_categories(self) -> List[List[str]]:
        return self.scope.filter_categories

    @property
    def filter_afk(self) -> bool:
        return self.scope.filter_afk

    @property
    def always_active_pattern(self) -> str:
        return self.scope.always_active_pattern


def start_dashboard_summary_warmup(server_api) -> threading.Thread:
    worker = threading.Thread(
        target=_warmup_loop,
        args=(server_api,),
        name="dashboard-summary-warmup",
        daemon=True,
    )
    worker.start()
    return worker


def warm_dashboard_summary_snapshots(
    server_api,
    *,
    now: Optional[datetime] = None,
    group_names: Optional[Sequence[str]] = None,
    period_names: Optional[Sequence[str]] = None,
) -> int:
    server_api.settings.load()
    settings_data = server_api.settings.get("")
    bucket_records = build_bucket_records(server_api.get_buckets())
    jobs = build_dashboard_summary_warmup_jobs(
        settings_data=settings_data,
        bucket_records=bucket_records,
        now=now,
    )
    allowed_groups = set(group_names or [])
    allowed_periods = set(period_names or [])
    if allowed_groups:
        jobs = [job for job in jobs if job.group_name in allowed_groups]
    if allowed_periods:
        jobs = [job for job in jobs if job.period_name in allowed_periods]

    for job in jobs:
        build_summary_snapshot_from_scope(
            server_api.db,
            range_start=job.range_start,
            range_end=job.range_end,
            category_periods=job.logical_periods,
            scope=job.scope,
            store=server_api.summary_snapshot_store,
        )

    return len(jobs)


def build_dashboard_summary_warmup_jobs(
    *,
    settings_data,
    bucket_records,
    now: Optional[datetime] = None,
    local_timezone: Optional[ZoneInfo] = None,
) -> List[SummaryWarmupJob]:
    tz = local_timezone or _resolve_local_timezone()
    now_local = _normalize_now(now, tz)
    from .settings_schema import normalize_settings_data
    settings_data, _ = normalize_settings_data(settings_data)
    start_of_day = str(settings_data["startOfDay"])
    start_of_week = str(settings_data["startOfWeek"])
    periods = _build_current_summary_warmup_periods(
        now_local=now_local,
        start_of_day=start_of_day,
        start_of_week=start_of_week,
    )

    jobs: List[SummaryWarmupJob] = []
    for period in periods:
        scopes = build_dashboard_summary_scopes(
            settings_data=settings_data,
            bucket_records=bucket_records,
            overlap_start_ms=_datetime_to_ms(period.range_start),
            overlap_end_ms=_datetime_to_ms(period.full_end),
        )
        for scope in scopes:
            if not period.logical_periods:
                continue
            jobs.append(
                SummaryWarmupJob(
                    group_name=scope.group_name,
                    period_name=period.name,
                    range_start=period.range_start,
                    range_end=period.query_end,
                    logical_periods=period.logical_periods,
                    scope=scope,
                )
            )

    return jobs


def _warmup_loop(server_api) -> None:
    while True:
        started_at = time.monotonic()
        try:
            job_count = warm_dashboard_summary_snapshots(server_api)
            duration = time.monotonic() - started_at
            logger.info(
                "Dashboard summary warmup completed",
                extra={"jobs": job_count, "duration_seconds": round(duration, 3)},
            )
        except Exception:
            logger.exception("Dashboard summary warmup failed")

        time.sleep(SUMMARY_WARMUP_INTERVAL_SECONDS)


def _resolve_local_timezone():
    try:
        target = LOCALTIME_PATH.resolve()
        parts = target.parts
        if "zoneinfo" in parts:
            index = parts.index("zoneinfo")
            zone_name = "/".join(parts[index + 1 :])
            if zone_name:
                return ZoneInfo(zone_name)
    except Exception:
        logger.exception("Failed to resolve local timezone from /etc/localtime")

    return datetime.now().astimezone().tzinfo or timezone.utc


def _normalize_now(now: Optional[datetime], local_timezone) -> datetime:
    if now is None:
        return datetime.now(local_timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=local_timezone)
    return now.astimezone(local_timezone)


def _parse_start_of_day(value: str) -> tuple[int, int]:
    parts = value.split(":")
    hours = int(parts[0]) if parts and parts[0] else 0
    minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return hours, minutes


def _offset_duration(start_of_day: str) -> timedelta:
    hours, minutes = _parse_start_of_day(start_of_day)
    return timedelta(hours=hours, minutes=minutes)


def _latest_logical_date(now_local: datetime, start_of_day: str) -> date:
    return (now_local - _offset_duration(start_of_day)).date()


def _day_start(latest_date: date, now_local: datetime, start_of_day: str) -> datetime:
    hours, minutes = _parse_start_of_day(start_of_day)
    return datetime.combine(
        latest_date,
        daytime(hour=hours, minute=minutes),
        tzinfo=now_local.tzinfo,
    )


def _build_current_summary_warmup_periods(
    *,
    now_local: datetime,
    start_of_day: str,
    start_of_week: str,
) -> List[SummaryWarmupPeriod]:
    anchor = _day_start(_latest_logical_date(now_local, start_of_day), now_local, start_of_day)
    periods: List[SummaryWarmupPeriod] = []

    for period_name in SUMMARY_WARMUP_PERIOD_ORDER:
        period_start = _period_start(anchor, period_name, start_of_week)
        full_end = _add_period(period_start, period_name, 1)
        logical_periods = _build_logical_periods(period_start, period_name, now_local)
        if not logical_periods:
            continue

        periods.append(
            SummaryWarmupPeriod(
                name=period_name,
                range_start=period_start,
                full_end=full_end,
                query_end=now_local,
                logical_periods=logical_periods,
            )
        )

    return periods


def _period_start(anchor: datetime, period_name: str, start_of_week: str) -> datetime:
    if period_name == "week":
        days_since_week_start = (
            anchor.weekday() if start_of_week == "Monday" else (anchor.weekday() + 1) % 7
        )
        return anchor - timedelta(days=days_since_week_start)
    if period_name == "month":
        return anchor.replace(day=1)
    if period_name == "year":
        return anchor.replace(month=1, day=1)
    raise ValueError(f"Unsupported period name: {period_name}")


def _build_logical_periods(
    period_start: datetime,
    period_name: str,
    now_local: datetime,
) -> List[str]:
    logical_periods: List[str] = []
    cursor = period_start
    limit = _add_period(period_start, period_name, 1)

    while cursor < limit and cursor < now_local:
        next_cursor = _add_period(cursor, "month", 1) if period_name == "year" else cursor + timedelta(days=1)
        logical_periods.append(f"{cursor.isoformat()}/{next_cursor.isoformat()}")
        cursor = next_cursor

    return logical_periods


def _add_period(start: datetime, period_name: str, count: int) -> datetime:
    if period_name == "week":
        return start + timedelta(weeks=count)
    if period_name == "month":
        return _add_months(start, count)
    if period_name == "year":
        return _add_months(start, 12 * count)
    raise ValueError(f"Unsupported period name: {period_name}")


def _add_months(start: datetime, count: int) -> datetime:
    month_index = (start.month - 1) + count
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return start.replace(year=year, month=month)
def _datetime_to_ms(value: datetime) -> float:
    return value.timestamp() * 1000
