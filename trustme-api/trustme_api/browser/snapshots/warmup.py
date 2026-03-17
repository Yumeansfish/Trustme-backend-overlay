import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

from .summary_snapshot import build_summary_snapshot


logger = logging.getLogger(__name__)

DEFAULT_DEVICE_GROUP_NAME = "My macbook"
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
    window_buckets: List[str]
    afk_buckets: List[str]
    stopwatch_buckets: List[str]
    categories: List[Any]
    filter_categories: List[List[str]]
    filter_afk: bool
    always_active_pattern: str


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
    bucket_records = _build_bucket_records(server_api.get_buckets())
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
        build_summary_snapshot(
            server_api.db,
            range_start=job.range_start,
            range_end=job.range_end,
            category_periods=job.logical_periods,
            window_buckets=job.window_buckets,
            afk_buckets=job.afk_buckets,
            stopwatch_buckets=job.stopwatch_buckets,
            filter_afk=job.filter_afk,
            categories=job.categories,
            filter_categories=job.filter_categories,
            always_active_pattern=job.always_active_pattern,
            store=server_api.summary_snapshot_store,
        )

    return len(jobs)


def build_dashboard_summary_warmup_jobs(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    now: Optional[datetime] = None,
    local_timezone: Optional[ZoneInfo] = None,
) -> List[SummaryWarmupJob]:
    tz = local_timezone or _resolve_local_timezone()
    now_local = _normalize_now(now, tz)
    known_hosts = _extract_known_hosts(bucket_records)
    if not known_hosts:
        return []

    effective_mappings = _get_effective_device_mappings(
        settings_data.get("deviceMappings"),
        known_hosts,
    )
    if not effective_mappings:
        return []

    start_of_day = str(settings_data.get("startOfDay") or "09:00")
    start_of_week = str(settings_data.get("startOfWeek") or "Monday")
    categories = _settings_to_query_categories(settings_data.get("classes") or [])
    always_active_pattern = str(
        settings_data.get("always_active_pattern")
        or settings_data.get("alwaysActivePattern")
        or ""
    )
    periods = _build_current_summary_warmup_periods(
        now_local=now_local,
        start_of_day=start_of_day,
        start_of_week=start_of_week,
    )

    jobs: List[SummaryWarmupJob] = []
    for group_name, group_hosts in effective_mappings.items():
        for period in periods:
            relevant_hosts = [
                host
                for host in group_hosts
                if _host_has_bucket_overlap(
                    bucket_records,
                    host,
                    _datetime_to_ms(period.range_start),
                    _datetime_to_ms(period.full_end),
                )
            ]
            resolved_hosts = relevant_hosts or group_hosts
            window_buckets = _select_window_buckets(bucket_records, resolved_hosts)
            afk_buckets = _select_buckets_by_type(bucket_records, resolved_hosts, "afkstatus")
            stopwatch_buckets = _select_stopwatch_buckets(bucket_records, resolved_hosts)

            if not window_buckets or not afk_buckets or not period.logical_periods:
                continue

            jobs.append(
                SummaryWarmupJob(
                    group_name=group_name,
                    period_name=period.name,
                    range_start=period.range_start,
                    range_end=period.query_end,
                    logical_periods=period.logical_periods,
                    window_buckets=window_buckets,
                    afk_buckets=afk_buckets,
                    stopwatch_buckets=stopwatch_buckets,
                    categories=categories,
                    filter_categories=[],
                    filter_afk=True,
                    always_active_pattern=always_active_pattern,
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


def _build_bucket_records(raw_buckets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    records = []
    for bucket_id, bucket in raw_buckets.items():
        record = dict(bucket)
        record["id"] = bucket_id
        records.append(record)
    return records


def _extract_known_hosts(bucket_records: Sequence[Dict[str, Any]]) -> List[str]:
    seen = set()
    hosts: List[str] = []
    for bucket in bucket_records:
        host = _bucket_host(bucket)
        if not host or host == "unknown" or host in seen:
            continue
        seen.add(host)
        hosts.append(host)
    return hosts


def _normalize_hosts(hosts: Iterable[str], known_hosts: Sequence[str]) -> List[str]:
    known_host_set = {host for host in known_hosts if host and host != "unknown"}
    normalized: List[str] = []
    seen = set()

    for host in hosts:
        if not host or host == "unknown" or host not in known_host_set or host in seen:
            continue
        seen.add(host)
        normalized.append(host)

    return normalized


def _get_effective_device_mappings(
    device_mappings: Optional[Dict[str, List[str]]],
    known_hosts: Sequence[str],
) -> Dict[str, List[str]]:
    mappings = device_mappings or {}
    valid_hosts = [host for host in known_hosts if host and host != "unknown"]
    assigned_hosts = set()
    custom_mappings: Dict[str, List[str]] = {}

    for group_name, hosts in mappings.items():
        if group_name == DEFAULT_DEVICE_GROUP_NAME:
            continue

        normalized_hosts = [
            host
            for host in _normalize_hosts(hosts if isinstance(hosts, list) else [], valid_hosts)
            if host not in assigned_hosts
        ]
        if not normalized_hosts:
            continue

        assigned_hosts.update(normalized_hosts)
        custom_mappings[group_name] = normalized_hosts

    default_hosts = [host for host in valid_hosts if host not in assigned_hosts]
    if default_hosts:
        return {DEFAULT_DEVICE_GROUP_NAME: default_hosts, **custom_mappings}

    return custom_mappings


def _bucket_host(bucket: Dict[str, Any]) -> Optional[str]:
    host = bucket.get("hostname")
    if isinstance(host, str) and host:
        return host

    data = bucket.get("data")
    if isinstance(data, dict):
        data_host = data.get("hostname")
        if isinstance(data_host, str) and data_host:
            return data_host

    return None


def _bucket_start_ms(bucket: Dict[str, Any]) -> Optional[float]:
    start = (
        bucket.get("first_seen")
        or _bucket_metadata(bucket).get("start")
        or bucket.get("created")
        or None
    )
    return _iso_to_ms(start)


def _bucket_end_ms(bucket: Dict[str, Any]) -> Optional[float]:
    end = (
        bucket.get("last_updated")
        or _bucket_metadata(bucket).get("end")
        or bucket.get("first_seen")
        or None
    )
    return _iso_to_ms(end)


def _bucket_metadata(bucket: Dict[str, Any]) -> Dict[str, Any]:
    metadata = bucket.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _iso_to_ms(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _datetime_to_ms(parsed)


def _host_has_bucket_overlap(
    bucket_records: Sequence[Dict[str, Any]],
    host: str,
    period_start_ms: float,
    period_end_ms: float,
) -> bool:
    for bucket in bucket_records:
        bucket_host = _bucket_host(bucket)
        if bucket_host != host:
            continue

        start_ms = _bucket_start_ms(bucket)
        end_ms = _bucket_end_ms(bucket)

        if start_ms is not None and end_ms is not None:
            if start_ms < period_end_ms and end_ms > period_start_ms:
                return True
            continue

        if end_ms is not None and end_ms > period_start_ms:
            return True
        if start_ms is not None and start_ms < period_end_ms:
            return True
        return True

    return False


def _select_buckets_by_type(
    bucket_records: Sequence[Dict[str, Any]],
    hosts: Sequence[str],
    bucket_type: str,
) -> List[str]:
    host_set = set(hosts)
    bucket_ids: List[str] = []
    seen = set()
    for bucket in bucket_records:
        if bucket.get("type") != bucket_type:
            continue
        bucket_host = _bucket_host(bucket)
        bucket_id = bucket.get("id")
        if bucket_host not in host_set or not isinstance(bucket_id, str) or bucket_id in seen:
            continue
        seen.add(bucket_id)
        bucket_ids.append(bucket_id)
    return bucket_ids


def _select_window_buckets(
    bucket_records: Sequence[Dict[str, Any]],
    hosts: Sequence[str],
) -> List[str]:
    return [
        bucket_id
        for bucket_id in _select_buckets_by_type(bucket_records, hosts, "currentwindow")
        if not bucket_id.startswith("aw-watcher-android")
    ]


def _select_stopwatch_buckets(
    bucket_records: Sequence[Dict[str, Any]],
    hosts: Sequence[str],
) -> List[str]:
    bucket_ids: List[str] = []
    seen = set()
    unknown_fallback = _select_buckets_by_type(bucket_records, ["unknown"], "general.stopwatch")

    for host in hosts:
        preferred = _select_buckets_by_type(bucket_records, [host], "general.stopwatch")
        selected = preferred or unknown_fallback
        for bucket_id in selected:
            if bucket_id in seen:
                continue
            seen.add(bucket_id)
            bucket_ids.append(bucket_id)

    return bucket_ids


def _settings_to_query_categories(classes: Sequence[Any]) -> List[Any]:
    categories: List[Any] = []
    for category in classes:
        if not isinstance(category, dict):
            continue
        rule = category.get("rule")
        name = category.get("name")
        if not isinstance(rule, dict) or not isinstance(name, list):
            continue
        if rule.get("type") is None:
            continue
        categories.append([[str(part) for part in name], dict(rule)])
    return categories


def _datetime_to_ms(value: datetime) -> float:
    return value.timestamp() * 1000
