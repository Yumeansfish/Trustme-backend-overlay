import sys
import types
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

from trustme_api.browser.canonical.repository import SqliteCanonicalUnitRepository
from trustme_api.browser.canonical.store import SqliteCanonicalUnitStore
from trustme_api.browser.snapshots.models import SummarySegment, datetime_to_ms


def test_store_shim_reexports_repository():
    assert SqliteCanonicalUnitStore is SqliteCanonicalUnitRepository


def test_repository_round_trips_summary_segment(tmp_path):
    repository = SqliteCanonicalUnitRepository(
        testing=True,
        path=tmp_path / "canonical.sqlite",
    )
    unit_start = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
    unit_end = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    segment = SummarySegment(
        logical_period=f"hour:{unit_start.isoformat()}/{unit_end.isoformat()}",
        computed_end_ms=datetime_to_ms(unit_end),
        duration=1800.0,
        apps={"Code": {"duration": 1800.0, "timestamp_ms": datetime_to_ms(unit_start)}},
        categories={
            "dev": {
                "category": ["Work", "Coding"],
                "duration": 1800.0,
                "timestamp_ms": datetime_to_ms(unit_start),
            }
        },
        uncategorized_apps={},
    )

    repository.put(
        scope_key="scope-a",
        calendar_key="calendar-a",
        unit_kind="hour",
        unit_start=unit_start,
        unit_end=unit_end,
        segment=segment,
    )

    stored = repository.get(
        scope_key="scope-a",
        calendar_key="calendar-a",
        unit_kind="hour",
        unit_start=unit_start,
        unit_end=unit_end,
    )

    assert stored is not None
    assert stored.logical_period == segment.logical_period
    assert stored.computed_end_ms == segment.computed_end_ms
    assert stored.duration == segment.duration
    assert stored.apps == segment.apps
    assert stored.categories == segment.categories
    assert repository.count_units(scope_key="scope-a") == 1
