import sys
import types

shared_module = types.ModuleType("trustme_api.shared")
shared_dirs_module = types.ModuleType("trustme_api.shared.dirs")

shared_dirs_module.get_data_dir = lambda appname: "/tmp"
sys.modules.setdefault("trustme_api.shared", shared_module)
sys.modules["trustme_api.shared.dirs"] = shared_dirs_module

from trustme_api.browser.snapshots.repository import SummarySnapshotRepository
from trustme_api.browser.snapshots.store import SummarySnapshotStore


def test_store_shim_reexports_repository():
    assert SummarySnapshotStore is SummarySnapshotRepository


def test_repository_round_trips_segments(tmp_path):
    repository = SummarySnapshotRepository(
        testing=True,
        path=tmp_path / "summary.sqlite",
    )

    repository.put_segment(
        "scope-a",
        "2026-04",
        computed_end="2026-04-09T10:00:00+00:00",
        stored_at="2026-04-09T10:00:05+00:00",
        payload={"duration": 120.0, "apps": {}, "categories": {}, "uncategorized_apps": {}},
    )

    segments = repository.get_segments("scope-a", ["2026-04"])

    assert segments["2026-04"]["computed_end"] == "2026-04-09T10:00:00+00:00"
    assert repository.count_segments(scope_key="scope-a") == 1
    assert repository.delete_segments(scope_key="scope-a", logical_periods=["2026-04"]) == 1
    assert repository.count_segments(scope_key="scope-a") == 0
