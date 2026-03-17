import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from aw_core.dirs import get_data_dir


SNAPSHOT_STORE_SCHEMA_VERSION = 2


class SummarySnapshotStore:
    def __init__(self, *, testing: bool, path: Optional[Path] = None) -> None:
        filename = f"dashboard-summary-snapshot-v{SNAPSHOT_STORE_SCHEMA_VERSION}"
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
                CREATE TABLE IF NOT EXISTS summary_segments (
                    scope_key TEXT NOT NULL,
                    logical_period TEXT NOT NULL,
                    computed_end TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (scope_key, logical_period)
                )
                """
            )
            connection.commit()

    def get_segments(
        self,
        scope_key: str,
        logical_periods: Iterable[str],
    ) -> Dict[str, Dict[str, Any]]:
        periods = list(dict.fromkeys(logical_periods))
        if not periods:
            return {}

        placeholders = ",".join("?" for _ in periods)
        query = (
            "SELECT logical_period, computed_end, stored_at, payload "
            "FROM summary_segments "
            f"WHERE scope_key = ? AND logical_period IN ({placeholders})"
        )
        params = [scope_key, *periods]

        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()

        return {
            row["logical_period"]: {
                "computed_end": row["computed_end"],
                "stored_at": row["stored_at"],
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        }

    def list_segments(
        self,
        *,
        scope_key: Optional[str] = None,
        logical_periods: Optional[Iterable[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        where_sql, params = self._build_where(scope_key, logical_periods)
        query = (
            "SELECT scope_key, logical_period, computed_end, stored_at "
            "FROM summary_segments "
            f"{where_sql} "
            "ORDER BY stored_at DESC, logical_period ASC "
            "LIMIT ?"
        )

        with closing(self._connect()) as connection:
            rows = connection.execute(query, [*params, int(limit)]).fetchall()

        return [
            {
                "scope_key": row["scope_key"],
                "logical_period": row["logical_period"],
                "computed_end": row["computed_end"],
                "stored_at": row["stored_at"],
            }
            for row in rows
        ]

    def count_segments(
        self,
        *,
        scope_key: Optional[str] = None,
        logical_periods: Optional[Iterable[str]] = None,
    ) -> int:
        where_sql, params = self._build_where(scope_key, logical_periods)
        query = f"SELECT COUNT(*) AS count FROM summary_segments {where_sql}"

        with closing(self._connect()) as connection:
            row = connection.execute(query, params).fetchone()

        return int(row["count"] if row else 0)

    def put_segment(
        self,
        scope_key: str,
        logical_period: str,
        *,
        computed_end: str,
        stored_at: str,
        payload: Dict[str, Any],
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO summary_segments(scope_key, logical_period, computed_end, stored_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scope_key, logical_period)
                DO UPDATE SET
                    computed_end = excluded.computed_end,
                    stored_at = excluded.stored_at,
                    payload = excluded.payload
                """,
                (
                    scope_key,
                    logical_period,
                    computed_end,
                    stored_at,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )
            connection.commit()

    def clear(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM summary_segments")
            connection.commit()

    def delete_segments(
        self,
        *,
        scope_key: Optional[str] = None,
        logical_periods: Optional[Iterable[str]] = None,
    ) -> int:
        where_sql, params = self._build_where(scope_key, logical_periods)
        query = f"DELETE FROM summary_segments {where_sql}"

        with closing(self._connect()) as connection:
            cursor = connection.execute(query, params)
            connection.commit()
            return int(cursor.rowcount or 0)

    def _build_where(
        self,
        scope_key: Optional[str],
        logical_periods: Optional[Iterable[str]],
    ) -> Tuple[str, List[Any]]:
        filters = []
        params: List[Any] = []

        if scope_key:
            filters.append("scope_key = ?")
            params.append(scope_key)

        periods = list(dict.fromkeys(logical_periods or []))
        if periods:
            placeholders = ",".join("?" for _ in periods)
            filters.append(f"logical_period IN ({placeholders})")
            params.extend(periods)

        if not filters:
            return "", params

        return "WHERE " + " AND ".join(filters), params
