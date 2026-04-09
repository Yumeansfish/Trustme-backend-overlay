import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from trustme_api.shared.dirs import get_data_dir

from trustme_api.browser.snapshots.models import SummarySegment, datetime_to_ms
from trustme_api.browser.snapshots.response_mapper import serialize_summary_segment


CANONICAL_UNIT_STORE_SCHEMA_VERSION = 2


class SqliteCanonicalUnitRepository:
    def __init__(self, *, testing: bool, path: Optional[Path] = None) -> None:
        filename = f"dashboard-canonical-units-v{CANONICAL_UNIT_STORE_SCHEMA_VERSION}"
        if testing:
            filename += "-testing"
        filename += ".sqlite"

        self.path = path or Path(get_data_dir("aw-server")) / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_units (
                    scope_key TEXT NOT NULL,
                    calendar_key TEXT NOT NULL,
                    unit_kind TEXT NOT NULL,
                    unit_start TEXT NOT NULL,
                    unit_end TEXT NOT NULL,
                    computed_end TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (scope_key, calendar_key, unit_kind, unit_start, unit_end)
                )
                """
            )
            connection.commit()

    def get(
        self,
        *,
        scope_key: str,
        calendar_key: str,
        unit_kind: str,
        unit_start: datetime,
        unit_end: datetime,
    ) -> Optional[SummarySegment]:
        params = (
            scope_key,
            calendar_key,
            unit_kind,
            _normalized_iso(unit_start),
            _normalized_iso(unit_end),
        )
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT computed_end, payload
                FROM canonical_units
                WHERE scope_key = ?
                  AND calendar_key = ?
                  AND unit_kind = ?
                  AND unit_start = ?
                  AND unit_end = ?
                """,
                params,
            ).fetchone()

        if row is None:
            return None

        payload = json.loads(row["payload"])
        return _deserialize_summary_segment(
            logical_period=f"{unit_kind}:{unit_start.isoformat()}/{unit_end.isoformat()}",
            computed_end=row["computed_end"],
            payload=payload,
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
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO canonical_units(
                    scope_key,
                    calendar_key,
                    unit_kind,
                    unit_start,
                    unit_end,
                    computed_end,
                    stored_at,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_key, calendar_key, unit_kind, unit_start, unit_end)
                DO UPDATE SET
                    computed_end = excluded.computed_end,
                    stored_at = excluded.stored_at,
                    payload = excluded.payload
                """,
                (
                    scope_key,
                    calendar_key,
                    unit_kind,
                    _normalized_iso(unit_start),
                    _normalized_iso(unit_end),
                    datetime.fromtimestamp(segment.computed_end_ms / 1000, tz=timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(
                        serialize_summary_segment(segment),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )
            connection.commit()

    def clear(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM canonical_units")
            connection.commit()

    def count_units(
        self,
        *,
        scope_key: Optional[str] = None,
        calendar_key: Optional[str] = None,
        unit_kinds: Optional[Iterable[str]] = None,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> int:
        where_sql, params = self._build_where(
            scope_key=scope_key,
            calendar_key=calendar_key,
            unit_kinds=unit_kinds,
            range_start=range_start,
            range_end=range_end,
        )
        query = f"SELECT COUNT(*) AS count FROM canonical_units {where_sql}"

        with closing(self._connect()) as connection:
            row = connection.execute(query, params).fetchone()

        return int(row["count"] if row else 0)

    def count_by_kind(self) -> Dict[str, int]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT unit_kind, COUNT(*) AS count
                FROM canonical_units
                GROUP BY unit_kind
                ORDER BY unit_kind ASC
                """
            ).fetchall()
        return {str(row["unit_kind"]): int(row["count"]) for row in rows}

    def delete_units(
        self,
        *,
        scope_key: Optional[str] = None,
        calendar_key: Optional[str] = None,
        unit_kinds: Optional[Iterable[str]] = None,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> int:
        where_sql, params = self._build_where(
            scope_key=scope_key,
            calendar_key=calendar_key,
            unit_kinds=unit_kinds,
            range_start=range_start,
            range_end=range_end,
        )
        query = f"DELETE FROM canonical_units {where_sql}"

        with closing(self._connect()) as connection:
            cursor = connection.execute(query, params)
            connection.commit()
            return int(cursor.rowcount or 0)

    def _build_where(
        self,
        *,
        scope_key: Optional[str],
        calendar_key: Optional[str],
        unit_kinds: Optional[Iterable[str]],
        range_start: Optional[datetime],
        range_end: Optional[datetime],
    ) -> Tuple[str, List[Any]]:
        filters = []
        params: List[Any] = []

        if scope_key:
            filters.append("scope_key = ?")
            params.append(scope_key)

        if calendar_key:
            filters.append("calendar_key = ?")
            params.append(calendar_key)

        kinds = list(dict.fromkeys(unit_kinds or []))
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            filters.append(f"unit_kind IN ({placeholders})")
            params.extend(kinds)

        if range_end is not None:
            filters.append("unit_start < ?")
            params.append(_normalized_iso(range_end))

        if range_start is not None:
            filters.append("unit_end > ?")
            params.append(_normalized_iso(range_start))

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params


def _deserialize_summary_segment(
    *,
    logical_period: str,
    computed_end: str,
    payload: Dict[str, Any],
) -> SummarySegment:
    return SummarySegment(
        logical_period=logical_period,
        computed_end_ms=datetime_to_ms(
            datetime.fromisoformat(str(computed_end).replace("Z", "+00:00"))
        ),
        duration=float(payload.get("duration", 0.0)),
        apps={
            app: {
                "duration": float(entry.get("duration", 0.0)),
                "timestamp_ms": float(entry.get("timestamp_ms", 0.0)),
            }
            for app, entry in (payload.get("apps") or {}).items()
        },
        categories={
            key: {
                "category": list(entry.get("category") or []),
                "duration": float(entry.get("duration", 0.0)),
                "timestamp_ms": float(entry.get("timestamp_ms", 0.0)),
            }
            for key, entry in (payload.get("categories") or {}).items()
        },
        uncategorized_apps={
            app: {
                "duration": float(entry.get("duration", 0.0)),
                "timestamp_ms": float(entry.get("timestamp_ms", 0.0)),
            }
            for app, entry in (payload.get("uncategorized_apps") or {}).items()
        },
    )


def _normalized_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


SqliteCanonicalUnitStore = SqliteCanonicalUnitRepository
