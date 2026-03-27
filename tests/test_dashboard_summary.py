import sys
import types
import unittest
from datetime import datetime, timezone

shared_module = types.ModuleType("trustme_api.shared")
shared_dirs_module = types.ModuleType("trustme_api.shared.dirs")
shared_models_module = types.ModuleType("trustme_api.shared.models")


class Event(dict):
    pass


shared_models_module.Event = Event
shared_dirs_module.get_data_dir = lambda appname: "/tmp"
sys.modules.setdefault("trustme_api.shared", shared_module)
sys.modules["trustme_api.shared.dirs"] = shared_dirs_module
sys.modules["trustme_api.shared.models"] = shared_models_module

from trustme_api.browser.dashboard.domain_service import build_ad_hoc_summary_scope
from trustme_api.browser.snapshots.summary import build_summary_snapshot_from_scope


class FakeBucket:
    def __init__(self, count: int) -> None:
        self.count = count

    def get_eventcount(self, starttime=None, endtime=None):
        return self.count


class FakeDB(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key)


class DashboardSummarySnapshotTest(unittest.TestCase):
    def test_empty_scope_short_circuits_before_canonical_backfill(self):
        db = FakeDB(
            {
                "aw-watcher-window_alpha.local": FakeBucket(0),
                "aw-watcher-afk_alpha.local": FakeBucket(0),
            }
        )
        scope = build_ad_hoc_summary_scope(
            group_name="My macbook",
            window_buckets=["aw-watcher-window_alpha.local"],
            afk_buckets=["aw-watcher-afk_alpha.local"],
            stopwatch_buckets=[],
            filter_afk=True,
            categories=[],
            filter_categories=[],
            always_active_pattern="",
        )

        response = build_summary_snapshot_from_scope(
            db,
            range_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2021, 1, 1, tzinfo=timezone.utc),
            category_periods=["2020-01-01T00:00:00+00:00/2021-01-01T00:00:00+00:00"],
            scope=scope,
            calendar_settings={"startOfDay": "00:00", "startOfWeek": "Monday", "classes": []},
            canonical_unit_store=object(),
        )

        self.assertEqual(response["window"]["duration"], 0.0)
        self.assertEqual(response["window"]["app_events"], [])
        self.assertEqual(response["by_period"], {
            "2020-01-01T00:00:00+00:00/2021-01-01T00:00:00+00:00": {"cat_events": []}
        })
        self.assertEqual(response["uncategorized_rows"], [])


if __name__ == "__main__":
    unittest.main()
