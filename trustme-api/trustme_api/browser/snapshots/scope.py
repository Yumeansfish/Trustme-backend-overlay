import hashlib
import json
from datetime import datetime, timezone
from typing import Any, List, Sequence, Tuple

from .summary_snapshot_categories import normalize_category_name
from .summary_snapshot_models import PeriodBound, datetime_to_ms


def build_summary_snapshot_scope_key(
    *,
    window_buckets: Sequence[str],
    afk_buckets: Sequence[str],
    stopwatch_buckets: Sequence[str],
    filter_afk: bool,
    categories: Sequence[Any],
    filter_categories: Sequence[Sequence[str]],
    always_active_pattern: str,
) -> str:
    normalized_window_buckets = sorted(dict.fromkeys(window_buckets))
    normalized_afk_buckets = sorted(dict.fromkeys(afk_buckets))
    normalized_stopwatch_buckets = sorted(dict.fromkeys(stopwatch_buckets))
    normalized_categories = sorted(
        json.dumps(category, sort_keys=True, separators=(",", ":")) for category in categories
    )
    normalized_filter_categories = sorted(
        json.dumps(normalize_category_name(category), separators=(",", ":"))
        for category in filter_categories
    )
    payload = {
        "version": 1,
        "window_buckets": normalized_window_buckets,
        "afk_buckets": normalized_afk_buckets,
        "stopwatch_buckets": normalized_stopwatch_buckets,
        "filter_afk": bool(filter_afk),
        "categories": normalized_categories,
        "filter_categories": normalized_filter_categories,
        "always_active_pattern": always_active_pattern or "",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest.hexdigest()


def build_period_bounds(periods: Sequence[str]) -> List[PeriodBound]:
    period_bounds = []
    for period in periods:
        try:
            start_iso, end_iso = period.split("/")
            start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        start_ms = datetime_to_ms(start)
        end_ms = datetime_to_ms(end)
        if end_ms <= start_ms:
            continue
        period_bounds.append(PeriodBound(period, start_ms, end_ms))
    return period_bounds


def expand_range_to_cover_periods(
    range_start: datetime,
    range_end: datetime,
    periods: Sequence[str],
) -> Tuple[datetime, datetime]:
    period_bounds = build_period_bounds(periods)
    if not period_bounds:
        return range_start, range_end

    range_start_ms = datetime_to_ms(range_start)
    range_end_ms = datetime_to_ms(range_end)
    periods_start_ms = min(period.start_ms for period in period_bounds)
    periods_end_ms = max(period.end_ms for period in period_bounds)

    effective_start_ms = min(range_start_ms, periods_start_ms)
    effective_end_ms = max(range_end_ms, periods_end_ms)

    return (
        datetime.fromtimestamp(effective_start_ms / 1000, tz=timezone.utc),
        datetime.fromtimestamp(effective_end_ms / 1000, tz=timezone.utc),
    )
