import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from aw_core.dirs import get_data_dir

from .summary_snapshot_models import SummarySegment, datetime_to_ms
from .summary_snapshot_response import serialize_summary_segment


CANONICAL_UNIT_STORE_SCHEMA_VERSION = 1


class SqliteCanonicalUnitStore:
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
            unit_start.isoformat(),
            unit_end.isoformat(),
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
                    unit_start.isoformat(),
                    unit_end.isoformat(),
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
