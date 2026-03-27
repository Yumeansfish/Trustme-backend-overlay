import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trustme_api.browser.dashboard.availability_store import DashboardAvailabilityStore
from trustme_api.browser.dashboard.domain_service import (
    build_dashboard_summary_scopes,
    resolve_dashboard_scope,
)


def make_bucket(
    bucket_id: str,
    bucket_type: str,
    host: str,
    *,
    start: str = "2025-05-01T00:00:00+00:00",
    end: str = "2025-05-02T00:00:00+00:00",
):
    return {
        "id": bucket_id,
        "type": bucket_type,
        "hostname": host,
        "first_seen": start,
        "last_updated": end,
    }


class DashboardDomainServiceTest(unittest.TestCase):
    def setUp(self):
        self.settings_data = {}
        self.bucket_records = [
            make_bucket("aw-watcher-window_alpha.local", "currentwindow", "alpha.local"),
            make_bucket("aw-watcher-afk_alpha.local", "afkstatus", "alpha.local"),
            make_bucket(
                "aw-watcher-window_beta.local",
                "currentwindow",
                "beta.local",
                start="2025-06-01T00:00:00+00:00",
                end="2025-06-02T00:00:00+00:00",
            ),
            make_bucket(
                "aw-watcher-afk_beta.local",
                "afkstatus",
                "beta.local",
                start="2025-06-01T00:00:00+00:00",
                end="2025-06-02T00:00:00+00:00",
            ),
        ]

    def test_resolve_dashboard_scope_returns_empty_scope_for_no_overlap(self):
        scope = resolve_dashboard_scope(
            settings_data=self.settings_data,
            bucket_records=self.bucket_records,
            requested_hosts=["alpha.local"],
            overlap_start_ms=1577836800000,
            overlap_end_ms=1609459200000,
        )

        self.assertEqual(scope.group_name, "My macbook")
        self.assertEqual(scope.requested_hosts, ["alpha.local"])
        self.assertEqual(scope.resolved_hosts, [])
        self.assertEqual(scope.window_buckets, [])
        self.assertEqual(scope.afk_buckets, [])
        self.assertEqual(scope.browser_buckets, [])
        self.assertEqual(scope.stopwatch_buckets, [])
        self.assertEqual(scope.available_dates, [])
        self.assertEqual(scope.earliest_available_date, "")
        self.assertEqual(scope.latest_available_date, "")

    def test_build_dashboard_summary_scopes_skips_groups_without_overlap(self):
        scopes = build_dashboard_summary_scopes(
            settings_data=self.settings_data,
            bucket_records=self.bucket_records,
            overlap_start_ms=1577836800000,
            overlap_end_ms=1609459200000,
        )

        self.assertEqual(scopes, [])

    def test_build_dashboard_summary_scopes_keeps_overlapping_groups(self):
        scopes = build_dashboard_summary_scopes(
            settings_data=self.settings_data,
            bucket_records=self.bucket_records,
            overlap_start_ms=1746057600000,
            overlap_end_ms=1746230400000,
        )

        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0].hosts, ["alpha.local"])
        self.assertEqual(scopes[0].window_buckets, ["aw-watcher-window_alpha.local"])
        self.assertEqual(scopes[0].afk_buckets, ["aw-watcher-afk_alpha.local"])

    def test_resolve_dashboard_scope_returns_group_availability(self):
        class FakeBucket:
            def __init__(self, logical_days):
                self.logical_days = set(logical_days)

            def get(self, limit=-1, starttime=None, endtime=None):
                events = []
                for logical_day in sorted(self.logical_days):
                    events.append(
                        type(
                            "FakeEvent",
                            (),
                            {
                                "timestamp": datetime.fromisoformat(logical_day).replace(
                                    tzinfo=timezone.utc
                                ),
                                "duration": timedelta(minutes=1),
                            },
                        )()
                    )
                return events

        class FakeDB(dict):
            def __getitem__(self, key):
                return dict.__getitem__(self, key)

        with tempfile.TemporaryDirectory() as tmpdir:
            availability_store = DashboardAvailabilityStore(
                testing=True,
                path=Path(tmpdir) / "availability.sqlite",
            )
            db = FakeDB(
                {
                    "aw-watcher-window_alpha.local": FakeBucket({"2025-05-01"}),
                    "aw-watcher-afk_alpha.local": FakeBucket({"2025-05-01"}),
                }
            )
            scope = resolve_dashboard_scope(
                settings_data={"startOfDay": "00:00", "deviceMappings": {}},
                bucket_records=self.bucket_records,
                requested_hosts=[],
                requested_group_name="My macbook",
                db=db,
                availability_store=availability_store,
            )

        self.assertEqual(scope.group_name, "My macbook")
        self.assertEqual(scope.resolved_hosts, ["alpha.local", "beta.local"])
        self.assertEqual(scope.available_dates, ["2025-05-01"])
        self.assertEqual(scope.earliest_available_date, "2025-05-01")
        self.assertEqual(scope.latest_available_date, "2025-05-01")


if __name__ == "__main__":
    unittest.main()
