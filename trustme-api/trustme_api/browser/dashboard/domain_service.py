from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .settings_schema import normalize_settings_data


DEFAULT_DEVICE_GROUP_NAME = "My macbook"


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
            overlapping_hosts = [
                host
                for host in group_hosts
                if _host_has_bucket_overlap(
                    bucket_records,
                    host,
                    overlap_start_ms,
                    overlap_end_ms,
                )
            ]
            if overlapping_hosts:
                resolved_hosts = overlapping_hosts

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
