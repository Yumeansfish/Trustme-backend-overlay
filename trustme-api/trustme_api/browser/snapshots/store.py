import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from aw_core.dirs import get_data_dir


SNAPSHOT_STORE_SCHEMA_VERSION = 1


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
