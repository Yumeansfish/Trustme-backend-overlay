#!/usr/bin/env python3

import argparse
import json
import time
from pathlib import Path

from _repo_bootstrap import ensure_repo_import_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
ensure_repo_import_paths(repo_root=REPO_ROOT)

from trustme_api.api import ServerAPI  # noqa: E402
from trustme_api.app.config import config  # noqa: E402
from trustme_api.browser.canonical.repository import SqliteCanonicalUnitRepository  # noqa: E402
from trustme_api.browser.canonical.strategy import PERSISTED_UNIT_KINDS  # noqa: E402
from trustme_api.browser.canonical.units import (  # noqa: E402
    ExperimentalCanonicalQueryEngine,
    SCENARIO_NAMES,
    build_benchmark_queries,
    summarize_stats,
)
from trustme_api.browser.dashboard.scope_service import (  # noqa: E402
    build_bucket_records,
    build_dashboard_summary_scopes,
)
from trustme_api.storage import Datastore, get_storage_methods  # noqa: E402


def build_server_api(testing: bool, storage_name: str = "") -> ServerAPI:
    config_section = "server-testing" if testing else "server"
    resolved_storage = storage_name or config[config_section]["storage"]
    storage_method = get_storage_methods()[resolved_storage]
    db = Datastore(storage_method, testing=testing)
    return ServerAPI(db=db, testing=testing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark experimental canonical time-unit strategies."
    )
    parser.add_argument("--testing", action="store_true", help="Use testing storage paths")
    parser.add_argument(
        "--storage",
        default="",
        help="Override configured storage backend (defaults to browser backend config)",
    )
    parser.add_argument(
        "--group",
        action="append",
        dest="groups",
        default=[],
        help="Restrict benchmark to one or more configured device groups",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCENARIO_NAMES,
        dest="scenarios",
        default=[],
        help="Restrict benchmark to specific scenarios",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="Number of cold/warm benchmark cycles to execute per scenario",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write the benchmark JSON payload",
    )
    parser.add_argument(
        "--store-path",
        default="",
        help="Optional path to the canonical unit SQLite store used by the benchmark",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")

    server_api = build_server_api(testing=args.testing, storage_name=args.storage)
    server_api.settings.load()
    settings_data = server_api.settings.get("")
    bucket_records = build_bucket_records(server_api.get_buckets())
    scopes = build_dashboard_summary_scopes(
        settings_data=settings_data,
        bucket_records=bucket_records,
    )
    if args.groups:
        allowed_groups = set(args.groups)
        scopes = [scope for scope in scopes if scope.group_name in allowed_groups]
    if not scopes:
        raise ValueError("No dashboard scopes available for the requested benchmark filters")

    shared_store = SqliteCanonicalUnitRepository(
        testing=args.testing,
        path=Path(args.store_path) if args.store_path else None,
    )
    engines = [
        ExperimentalCanonicalQueryEngine(
            db=server_api.db,
            scope=scope,
            settings_data=settings_data,
            store=shared_store,
            persisted_unit_kinds=PERSISTED_UNIT_KINDS,
        )
        for scope in scopes
    ]
    queries = build_benchmark_queries(
        settings_data,
        scenario_names=args.scenarios or None,
    )

    results = []
    for query in queries:
        cold_durations = []
        warm_durations = []
        cold_stats = []
        warm_stats = []
        cold_store_counts = []
        warm_store_counts = []

        for _ in range(args.repeat):
            shared_store.clear()

            started = time.perf_counter()
            cycle_cold_stats = []
            for engine in engines:
                result = engine.execute_query(
                    range_start=query.range_start,
                    range_end=query.range_end,
                    bucket_kind=query.bucket_kind,
                )
                cycle_cold_stats.append(result["stats"])
            cold_durations.append(time.perf_counter() - started)
            cold_stats.append(summarize_stats(cycle_cold_stats))
            cold_store_counts.append(shared_store.count_by_kind())

            started = time.perf_counter()
            cycle_warm_stats = []
            for engine in engines:
                result = engine.execute_query(
                    range_start=query.range_start,
                    range_end=query.range_end,
                    bucket_kind=query.bucket_kind,
                )
                cycle_warm_stats.append(result["stats"])
            warm_durations.append(time.perf_counter() - started)
            warm_stats.append(summarize_stats(cycle_warm_stats))
            warm_store_counts.append(shared_store.count_by_kind())

        results.append(
            {
                "scenario": query.name,
                "range_start": query.range_start.isoformat(),
                "range_end": query.range_end.isoformat(),
                "bucket_kind": query.bucket_kind,
                "cold_durations_seconds": cold_durations,
                "warm_durations_seconds": warm_durations,
                "avg_cold_duration_seconds": sum(cold_durations) / len(cold_durations),
                "avg_warm_duration_seconds": sum(warm_durations) / len(warm_durations),
                "cold_stats_last_run": cold_stats[-1],
                "warm_stats_last_run": warm_stats[-1],
                "cold_store_counts_last_run": cold_store_counts[-1],
                "warm_store_counts_last_run": warm_store_counts[-1],
            }
        )

    payload = {
        "strategy": list(PERSISTED_UNIT_KINDS),
        "repeat": args.repeat,
        "groups": args.groups,
        "scope_names": [scope.group_name for scope in scopes],
        "store_path": str(shared_store.path),
        "results": results,
    }
    encoded = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
