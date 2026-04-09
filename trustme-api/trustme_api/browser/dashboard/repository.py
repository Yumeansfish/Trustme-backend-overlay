import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from trustme_api.shared.dirs import get_data_dir
except ModuleNotFoundError:  # pragma: no cover - overlay-only fallback
    def get_data_dir(appname: str) -> str:
        fallback = Path.home() / ".local" / "share" / appname
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)


DASHBOARD_AVAILABILITY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DashboardAvailabilityCoverage:
    group_name: str
    hosts_signature: str
    start_day: str
    end_day: str


class DashboardAvailabilityRepository:
    def __init__(self, *, testing: bool, path: Optional[Path] = None) -> None:
        filename = f"dashboard-availability-v{DASHBOARD_AVAILABILITY_SCHEMA_VERSION}"
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
                CREATE TABLE IF NOT EXISTS availability_days (
                    group_name TEXT NOT NULL,
                    logical_day TEXT NOT NULL,
                    PRIMARY KEY (group_name, logical_day)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS availability_coverage (
                    group_name TEXT PRIMARY KEY,
                    hosts_signature TEXT NOT NULL,
                    start_day TEXT NOT NULL,
                    end_day TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def get_coverage(self, group_name: str) -> Optional[DashboardAvailabilityCoverage]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT group_name, hosts_signature, start_day, end_day
                FROM availability_coverage
                WHERE group_name = ?
                """,
                (group_name,),
            ).fetchone()

        if row is None:
            return None

        return DashboardAvailabilityCoverage(
            group_name=str(row["group_name"]),
            hosts_signature=str(row["hosts_signature"]),
            start_day=str(row["start_day"]),
            end_day=str(row["end_day"]),
        )

    def list_available_days(self, group_name: str) -> List[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT logical_day
                FROM availability_days
                WHERE group_name = ?
                ORDER BY logical_day ASC
                """,
                (group_name,),
            ).fetchall()

        return [str(row["logical_day"]) for row in rows]

    def replace_group_days(
        self,
        *,
        group_name: str,
        hosts_signature: str,
        start_day: str,
        end_day: str,
        available_days: Iterable[str],
    ) -> None:
        normalized_days = sorted(dict.fromkeys(day for day in available_days if isinstance(day, str) and day))
        stored_at = datetime.now(timezone.utc).isoformat()

        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM availability_days WHERE group_name = ?",
                (group_name,),
            )
            if normalized_days:
                connection.executemany(
                    """
                    INSERT INTO availability_days(group_name, logical_day)
                    VALUES (?, ?)
                    """,
                    [(group_name, day) for day in normalized_days],
                )
            connection.execute(
                """
                INSERT INTO availability_coverage(group_name, hosts_signature, start_day, end_day, stored_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(group_name)
                DO UPDATE SET
                    hosts_signature = excluded.hosts_signature,
                    start_day = excluded.start_day,
                    end_day = excluded.end_day,
                    stored_at = excluded.stored_at
                """,
                (group_name, hosts_signature, start_day, end_day, stored_at),
            )
            connection.commit()

    def mark_days_available(
        self,
        *,
        group_name: str,
        logical_days: Iterable[str],
    ) -> None:
        normalized_days = sorted(dict.fromkeys(day for day in logical_days if isinstance(day, str) and day))
        if not normalized_days:
            return

        with closing(self._connect()) as connection:
            connection.executemany(
                """
                INSERT INTO availability_days(group_name, logical_day)
                VALUES (?, ?)
                ON CONFLICT(group_name, logical_day) DO NOTHING
                """,
                [(group_name, day) for day in normalized_days],
            )
            connection.commit()

    def clear_group(self, group_name: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM availability_days WHERE group_name = ?", (group_name,))
            connection.execute(
                "DELETE FROM availability_coverage WHERE group_name = ?",
                (group_name,),
            )
            connection.commit()

    def clear(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM availability_days")
            connection.execute("DELETE FROM availability_coverage")
            connection.commit()
