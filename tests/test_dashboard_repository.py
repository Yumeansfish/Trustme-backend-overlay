import unittest

from trustme_api.browser.dashboard.availability_store import DashboardAvailabilityStore
from trustme_api.browser.dashboard.repository import (
    DashboardAvailabilityCoverage,
    DashboardAvailabilityRepository,
)


class DashboardRepositoryTest(unittest.TestCase):
    def test_store_shim_reexports_repository(self):
        self.assertIs(DashboardAvailabilityStore, DashboardAvailabilityRepository)

    def test_repository_round_trips_group_coverage(self):
        repository = DashboardAvailabilityRepository(
            testing=True,
            path=self._tmp_path("availability.sqlite"),
        )

        repository.replace_group_days(
            group_name="My macbook",
            hosts_signature="alpha.local,beta.local",
            start_day="2025-05-01",
            end_day="2025-05-03",
            available_days=["2025-05-01", "2025-05-03", "2025-05-03"],
        )

        self.assertEqual(
            repository.get_coverage("My macbook"),
            DashboardAvailabilityCoverage(
                group_name="My macbook",
                hosts_signature="alpha.local,beta.local",
                start_day="2025-05-01",
                end_day="2025-05-03",
            ),
        )
        self.assertEqual(
            repository.list_available_days("My macbook"),
            ["2025-05-01", "2025-05-03"],
        )

        repository.mark_days_available(
            group_name="My macbook",
            logical_days=["2025-05-02", "2025-05-03"],
        )
        self.assertEqual(
            repository.list_available_days("My macbook"),
            ["2025-05-01", "2025-05-02", "2025-05-03"],
        )

    def _tmp_path(self, filename: str):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        if not hasattr(self, "_tmpdir"):
            self._tmpdir = TemporaryDirectory()
            self.addCleanup(self._tmpdir.cleanup)
        return Path(self._tmpdir.name) / filename


if __name__ == "__main__":
    unittest.main()
