from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

from trustme_api.browser.dashboard.repository import DashboardAvailabilityRepository
from trustme_api.browser.settings.schema import normalize_settings_data


DEFAULT_DEVICE_GROUP_NAME = "My macbook"
AD_HOC_DASHBOARD_GROUP_NAME = "ad-hoc"
LOCALTIME_PATH = Path("/etc/localtime")


@dataclass(frozen=True)
class DashboardSummaryScope:
    group_name: str
    hosts: List[str]
    window_buckets: List[str]
    afk_buckets: List[str]
    stopwatch_buckets: List[str]
    categories: List[Any]
    filter_categories: List[List[str]]
    filter_afk: bool
    always_active_pattern: str


@dataclass(frozen=True)
class DashboardResolvedScope:
    group_name: str
    requested_hosts: List[str]
    resolved_hosts: List[str]
    window_buckets: List[str]
    afk_buckets: List[str]
    browser_buckets: List[str]
    stopwatch_buckets: List[str]
    available_dates: List[str]
    earliest_available_date: str
    latest_available_date: str


@dataclass(frozen=True)
class DashboardDefaultScope:
    group_name: str
    resolved_hosts: List[str]


def build_bucket_records(raw_buckets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    records = []
    for bucket_id, bucket in raw_buckets.items():
        record = dict(bucket)
        record["id"] = bucket_id
        records.append(record)
    return records


def build_ad_hoc_summary_scope(
    *,
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    categories: Sequence[Any],
    filter_categories: Sequence[Sequence[str]],
    always_active_pattern: str,
    group_name: str = "ad-hoc",
) -> DashboardSummaryScope:
    return DashboardSummaryScope(
        group_name=group_name,
        hosts=[],
        window_buckets=_dedupe_strings(window_buckets),
        afk_buckets=_dedupe_strings(afk_buckets),
        stopwatch_buckets=_dedupe_strings(stopwatch_buckets),
        categories=_settings_to_query_categories(categories),
        filter_categories=_normalize_filter_categories(filter_categories),
        filter_afk=bool(filter_afk),
        always_active_pattern=always_active_pattern or "",
    )


def build_settings_backed_summary_scope(
    *,
    settings_data: Dict[str, Any],
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    filter_categories: Sequence[Sequence[str]],
    group_name: str = "dashboard",
) -> DashboardSummaryScope:
    settings_data, _ = normalize_settings_data(settings_data)
    return DashboardSummaryScope(
        group_name=group_name,
        hosts=[],
        window_buckets=_dedupe_strings(window_buckets),
        afk_buckets=_dedupe_strings(afk_buckets),
        stopwatch_buckets=_dedupe_strings(stopwatch_buckets),
        categories=_settings_to_query_categories(settings_data["classes"]),
        filter_categories=_normalize_filter_categories(filter_categories),
        filter_afk=bool(filter_afk),
        always_active_pattern=str(settings_data["always_active_pattern"]),
    )


def build_dashboard_summary_scopes(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    overlap_start_ms: Optional[float] = None,
    overlap_end_ms: Optional[float] = None,
) -> List[DashboardSummaryScope]:
    settings_data, _ = normalize_settings_data(settings_data)
    known_hosts = _extract_known_hosts(bucket_records)
    if not known_hosts:
        return []

    effective_mappings = _get_effective_device_mappings(
        settings_data["deviceMappings"],
        known_hosts,
    )
    if not effective_mappings:
        return []

    categories = _settings_to_query_categories(settings_data["classes"])
    always_active_pattern = str(settings_data["always_active_pattern"])
    scopes: List[DashboardSummaryScope] = []

    for group_name, group_hosts in effective_mappings.items():
        resolved_hosts = list(group_hosts)
        if overlap_start_ms is not None and overlap_end_ms is not None:
            resolved_hosts = [
                host
                for host in group_hosts
                if _host_has_bucket_overlap(
                    bucket_records,
                    host,
                    overlap_start_ms,
                    overlap_end_ms,
                )
            ]
            if not resolved_hosts:
                continue

        window_buckets = _select_window_buckets(bucket_records, resolved_hosts)
        afk_buckets = _select_buckets_by_type(bucket_records, resolved_hosts, "afkstatus")
        stopwatch_buckets = _select_stopwatch_buckets(bucket_records, resolved_hosts)
        if not window_buckets or not afk_buckets:
            continue

        scopes.append(
            DashboardSummaryScope(
                group_name=group_name,
                hosts=resolved_hosts,
                window_buckets=window_buckets,
                afk_buckets=afk_buckets,
                stopwatch_buckets=stopwatch_buckets,
                categories=categories,
                filter_categories=[],
                filter_afk=True,
                always_active_pattern=always_active_pattern,
            )
        )

    return scopes


def resolve_dashboard_scope(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    requested_hosts: Sequence[str],
    requested_group_name: Optional[str] = None,
    overlap_start_ms: Optional[float] = None,
    overlap_end_ms: Optional[float] = None,
    db=None,
    availability_store: Optional[DashboardAvailabilityRepository] = None,
) -> DashboardResolvedScope:
    settings_data, _ = normalize_settings_data(settings_data)
    known_hosts = _extract_known_hosts(bucket_records)
    normalized_requested_hosts = _normalize_hosts(requested_hosts, known_hosts)
    effective_mappings = _get_effective_device_mappings(
        settings_data["deviceMappings"],
        known_hosts,
    )
    group_name = _resolve_requested_group_name(requested_group_name, effective_mappings)
    if group_name:
        group_hosts = list(effective_mappings.get(group_name, []))
        resolved_hosts = list(group_hosts)
        if not normalized_requested_hosts:
            normalized_requested_hosts = list(resolved_hosts)
    else:
        expanded_hosts = _expand_requested_hosts_to_effective_groups(
            normalized_requested_hosts,
            effective_mappings,
        )
        group_hosts = list(expanded_hosts)
        resolved_hosts = list(group_hosts)
        group_name = _infer_group_name_from_hosts(group_hosts, effective_mappings)

    if not group_name:
        group_name = _normalize_group_name(requested_group_name) or AD_HOC_DASHBOARD_GROUP_NAME

    availability_hosts = list(group_hosts)

    if (
        resolved_hosts
        and overlap_start_ms is not None
        and overlap_end_ms is not None
    ):
        resolved_hosts = [
            host
            for host in resolved_hosts
            if _host_has_bucket_overlap(
                bucket_records,
                host,
                overlap_start_ms,
                overlap_end_ms,
            )
        ]

    window_buckets = _select_window_buckets(bucket_records, resolved_hosts)
    afk_buckets = _select_buckets_by_type(bucket_records, resolved_hosts, "afkstatus")
    browser_buckets = _select_browser_buckets(bucket_records, resolved_hosts)
    stopwatch_buckets = _select_stopwatch_buckets(bucket_records, resolved_hosts)
    availability_window_buckets = _select_window_buckets(bucket_records, availability_hosts)
    availability_afk_buckets = _select_buckets_by_type(
        bucket_records, availability_hosts, "afkstatus"
    )
    available_dates, earliest_available_date, latest_available_date = (
        _resolve_dashboard_availability(
            settings_data=settings_data,
            bucket_records=bucket_records,
            group_name=group_name,
            resolved_hosts=availability_hosts,
            window_buckets=availability_window_buckets,
            afk_buckets=availability_afk_buckets,
            db=db,
            availability_store=availability_store,
        )
        if availability_store is not None and db is not None
        else ([], "", "")
    )

    return DashboardResolvedScope(
        group_name=group_name,
        requested_hosts=normalized_requested_hosts,
        resolved_hosts=resolved_hosts,
        window_buckets=window_buckets,
        afk_buckets=afk_buckets,
        browser_buckets=browser_buckets,
        stopwatch_buckets=stopwatch_buckets,
        available_dates=available_dates,
        earliest_available_date=earliest_available_date,
        latest_available_date=latest_available_date,
    )


def resolve_default_dashboard_scope(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
) -> DashboardDefaultScope:
    settings_data, _ = normalize_settings_data(settings_data)
    known_hosts = _extract_known_hosts(bucket_records)
    if not known_hosts:
        return DashboardDefaultScope(group_name="", resolved_hosts=[])

    effective_mappings = _get_effective_device_mappings(
        settings_data["deviceMappings"],
        known_hosts,
    )

    for group_name, group_hosts in effective_mappings.items():
        valid_hosts = [
            host
            for host in group_hosts
            if _host_supports_activity(bucket_records, host)
        ]
        if valid_hosts:
            return DashboardDefaultScope(group_name=group_name, resolved_hosts=valid_hosts)

    fallback_host = next(
        (
            host
            for host in known_hosts
            if _host_supports_activity(bucket_records, host)
        ),
        None,
    )
    if fallback_host:
        return DashboardDefaultScope(
            group_name=_infer_group_name_from_hosts([fallback_host], effective_mappings)
            or DEFAULT_DEVICE_GROUP_NAME,
            resolved_hosts=[fallback_host],
        )

    fallback_hosts = known_hosts[:1]
    return DashboardDefaultScope(
        group_name=_infer_group_name_from_hosts(fallback_hosts, effective_mappings)
        or DEFAULT_DEVICE_GROUP_NAME,
        resolved_hosts=fallback_hosts,
    )


def resolve_default_dashboard_hosts(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
) -> List[str]:
    return resolve_default_dashboard_scope(
        settings_data=settings_data,
        bucket_records=bucket_records,
    ).resolved_hosts


def resolve_group_names_for_host(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    host: str,
) -> List[str]:
    settings_data, _ = normalize_settings_data(settings_data)
    known_hosts = _extract_known_hosts(bucket_records)
    effective_mappings = _get_effective_device_mappings(
        settings_data["deviceMappings"],
        known_hosts,
    )
    return [
        group_name
        for group_name, group_hosts in effective_mappings.items()
        if host in group_hosts
    ]


def resolve_logical_days_for_range(
    *,
    settings_data: Dict[str, Any],
    range_start: datetime,
    range_end: datetime,
) -> List[str]:
    if range_end <= range_start:
        return []

    local_timezone = _resolve_local_timezone()
    start_day = _logical_date(range_start, local_timezone)
    end_reference = range_end - timedelta(milliseconds=1)
    end_day = _logical_date(end_reference, local_timezone)

    days: List[str] = []
    cursor = start_day
    while cursor <= end_day:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _normalize_group_name(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _resolve_requested_group_name(
    requested_group_name: Any,
    effective_mappings: Dict[str, List[str]],
) -> str:
    normalized = _normalize_group_name(requested_group_name)
    return normalized if normalized in effective_mappings else ""


def _infer_group_name_from_hosts(
    hosts: Sequence[str],
    effective_mappings: Dict[str, List[str]],
) -> str:
    host_set = {host for host in hosts if isinstance(host, str) and host}
    if not host_set:
        return ""

    for group_name, group_hosts in effective_mappings.items():
        if host_set.issubset(set(group_hosts)):
            return group_name

    return ""


def _resolve_dashboard_availability(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    group_name: str,
    resolved_hosts: Sequence[str],
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    db,
    availability_store: DashboardAvailabilityRepository,
) -> tuple[List[str], str, str]:
    if not group_name or not resolved_hosts or not window_buckets or not afk_buckets:
        if group_name:
            availability_store.clear_group(group_name)
        return [], "", ""

    day_bounds = _resolve_availability_day_bounds(
        settings_data=settings_data,
        bucket_records=bucket_records,
        bucket_ids=[*window_buckets, *afk_buckets],
    )
    if day_bounds is None:
        availability_store.clear_group(group_name)
        return [], "", ""

    start_day, end_day = day_bounds
    hosts_signature = ",".join(sorted(dict.fromkeys(resolved_hosts)))
    coverage = availability_store.get_coverage(group_name)
    if (
        coverage is None
        or coverage.hosts_signature != hosts_signature
        or coverage.start_day != start_day
        or coverage.end_day != end_day
    ):
        available_dates = _rebuild_dashboard_availability_days(
            settings_data=settings_data,
            group_name=group_name,
            hosts_signature=hosts_signature,
            start_day=start_day,
            end_day=end_day,
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            db=db,
            availability_store=availability_store,
        )
    else:
        available_dates = availability_store.list_available_days(group_name)

    earliest = available_dates[0] if available_dates else ""
    latest = available_dates[-1] if available_dates else ""
    return available_dates, earliest, latest


def _resolve_availability_day_bounds(
    *,
    settings_data: Dict[str, Any],
    bucket_records: Sequence[Dict[str, Any]],
    bucket_ids: Sequence[str],
) -> Optional[tuple[str, str]]:
    bucket_ids_set = {bucket_id for bucket_id in bucket_ids if isinstance(bucket_id, str) and bucket_id}
    if not bucket_ids_set:
        return None

    starts = []
    ends = []
    for bucket in bucket_records:
        bucket_id = bucket.get("id")
        if not isinstance(bucket_id, str) or bucket_id not in bucket_ids_set:
            continue
        start_ms = _bucket_start_ms(bucket)
        end_ms = _bucket_end_ms(bucket)
        if start_ms is not None:
            starts.append(start_ms)
        if end_ms is not None:
            ends.append(end_ms)

    if not starts or not ends:
        return None

    local_timezone = _resolve_local_timezone()
    start_dt = datetime.fromtimestamp(min(starts) / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(max(ends) / 1000, tz=timezone.utc) - timedelta(milliseconds=1)
    return (
        _logical_date(start_dt, local_timezone).isoformat(),
        _logical_date(end_dt, local_timezone).isoformat(),
    )


def _rebuild_dashboard_availability_days(
    *,
    settings_data: Dict[str, Any],
    group_name: str,
    hosts_signature: str,
    start_day: str,
    end_day: str,
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    db,
    availability_store: DashboardAvailabilityRepository,
) -> List[str]:
    local_timezone = _resolve_local_timezone()
    range_start, _ = _logical_day_bounds(
        date.fromisoformat(start_day),
        local_timezone=local_timezone,
    )
    _, range_end = _logical_day_bounds(
        date.fromisoformat(end_day),
        local_timezone=local_timezone,
    )

    window_days = _collect_bucket_logical_days(
        db,
        window_buckets,
        range_start=range_start,
        range_end=range_end,
        local_timezone=local_timezone,
    )
    afk_days = _collect_bucket_logical_days(
        db,
        afk_buckets,
        range_start=range_start,
        range_end=range_end,
        local_timezone=local_timezone,
    )
    available_days = sorted(window_days & afk_days)

    availability_store.replace_group_days(
        group_name=group_name,
        hosts_signature=hosts_signature,
        start_day=start_day,
        end_day=end_day,
        available_days=available_days,
    )
    return available_days


def _collect_bucket_logical_days(
    db,
    bucket_ids: Sequence[str],
    range_start: datetime,
    range_end: datetime,
    *,
    local_timezone,
) -> set[str]:
    logical_days: set[str] = set()
    for bucket_id in _dedupe_strings(bucket_ids):
        if not isinstance(bucket_id, str) or not bucket_id:
            continue
        try:
            events = db[bucket_id].get(-1, range_start, range_end)
        except KeyError:
            continue

        for event in events:
            logical_days.update(
                _event_logical_days(
                    event,
                    range_start=range_start,
                    range_end=range_end,
                    local_timezone=local_timezone,
                )
            )

    return logical_days


def _event_logical_days(
    event,
    *,
    range_start: datetime,
    range_end: datetime,
    local_timezone,
) -> List[str]:
    timestamp = getattr(event, "timestamp", None)
    duration = getattr(event, "duration", None)
    if timestamp is None:
        return []

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    if isinstance(duration, timedelta):
        duration_delta = duration
    elif isinstance(duration, (int, float)):
        duration_delta = timedelta(seconds=float(duration))
    else:
        duration_delta = timedelta(0)

    event_start = max(timestamp, range_start)
    raw_event_end = timestamp + duration_delta
    event_end = min(raw_event_end, range_end)
    if event_end <= event_start:
        event_end = min(range_end, event_start + timedelta(microseconds=1))

    start_day = _logical_date(event_start, local_timezone)
    end_day = _logical_date(
        event_end - timedelta(microseconds=1),
        local_timezone,
    )

    days: List[str] = []
    cursor = start_day
    while cursor <= end_day:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _logical_day_bounds(
    logical_day: date,
    *,
    local_timezone,
) -> tuple[datetime, datetime]:
    start = datetime.combine(logical_day, datetime.min.time(), tzinfo=local_timezone)
    return start, start + timedelta(days=1)


def _logical_date(value: datetime, local_timezone) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(local_timezone).date()


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
        pass

    return datetime.now().astimezone().tzinfo or timezone.utc

def _dedupe_strings(values: Sequence[str]) -> List[str]:
    seen = set()
    results: List[str] = []
    for value in values:
        if not isinstance(value, str) or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def _normalize_filter_categories(filter_categories: Sequence[Sequence[str]]) -> List[List[str]]:
    normalized: List[List[str]] = []
    seen = set()
    for category in filter_categories:
        if not isinstance(category, Sequence) or isinstance(category, (str, bytes)):
            continue
        parts = [str(part).strip() for part in category if isinstance(part, str) and part.strip()]
        if not parts:
            continue
        key = tuple(parts)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(parts)
    return normalized


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


def _expand_requested_hosts_to_effective_groups(
    requested_hosts: Sequence[str],
    effective_mappings: Dict[str, List[str]],
) -> List[str]:
    expanded_hosts: List[str] = []
    seen = set()

    for requested_host in requested_hosts:
        matching_group_hosts = next(
            (
                group_hosts
                for group_hosts in effective_mappings.values()
                if requested_host in group_hosts
            ),
            None,
        )
        hosts_to_add = matching_group_hosts or [requested_host]
        for host in hosts_to_add:
            if host in seen:
                continue
            seen.add(host)
            expanded_hosts.append(host)

    return expanded_hosts


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
    return parsed.timestamp() * 1000


def _host_has_bucket_overlap(
    bucket_records: Sequence[Dict[str, Any]],
    host: str,
    period_start_ms: float,
    period_end_ms: float,
) -> bool:
    for bucket in bucket_records:
        if _bucket_matches_host_overlap(bucket, host, period_start_ms, period_end_ms):
            return True

    return False


def _bucket_matches_host_overlap(
    bucket: Dict[str, Any],
    host: str,
    period_start_ms: float,
    period_end_ms: float,
) -> bool:
    if _bucket_host(bucket) != host:
        return False
    return _bucket_time_overlaps(
        _bucket_start_ms(bucket),
        _bucket_end_ms(bucket),
        period_start_ms,
        period_end_ms,
    )


def _bucket_time_overlaps(
    start_ms: Optional[float],
    end_ms: Optional[float],
    period_start_ms: float,
    period_end_ms: float,
) -> bool:
    if start_ms is not None and end_ms is not None:
        return start_ms < period_end_ms and end_ms > period_start_ms
    if end_ms is not None:
        return end_ms > period_start_ms
    if start_ms is not None:
        return start_ms < period_end_ms
    return True


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


def _select_android_buckets(
    bucket_records: Sequence[Dict[str, Any]],
    hosts: Sequence[str],
) -> List[str]:
    return [
        bucket_id
        for bucket_id in _select_buckets_by_type(bucket_records, hosts, "currentwindow")
        if bucket_id.startswith("aw-watcher-android")
    ]


def _host_supports_activity(bucket_records: Sequence[Dict[str, Any]], host: str) -> bool:
    return bool(
        (
            _select_window_buckets(bucket_records, [host])
            and _select_buckets_by_type(bucket_records, [host], "afkstatus")
        )
        or _select_android_buckets(bucket_records, [host])
    )


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


def _select_browser_buckets(
    bucket_records: Sequence[Dict[str, Any]],
    hosts: Sequence[str],
) -> List[str]:
    bucket_ids: List[str] = []
    seen = set()
    unknown_fallback = _select_buckets_by_type(bucket_records, ["unknown"], "web.tab.current")

    for host in hosts:
        preferred = _select_buckets_by_type(bucket_records, [host], "web.tab.current")
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
        if (
            isinstance(category, list)
            and len(category) == 2
            and isinstance(category[0], list)
            and isinstance(category[1], dict)
        ):
            rule_type = category[1].get("type")
            if rule_type is None:
                continue
            categories.append([[str(part) for part in category[0]], dict(category[1])])
            continue
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
