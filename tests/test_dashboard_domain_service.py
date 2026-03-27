import unittest

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

        self.assertEqual(scope.requested_hosts, ["alpha.local"])
        self.assertEqual(scope.resolved_hosts, [])
        self.assertEqual(scope.window_buckets, [])
        self.assertEqual(scope.afk_buckets, [])
        self.assertEqual(scope.browser_buckets, [])
        self.assertEqual(scope.stopwatch_buckets, [])

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


if __name__ == "__main__":
    unittest.main()
