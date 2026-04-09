#!/usr/bin/env python3

import argparse
import cProfile
import io
import json
import time
from pathlib import Path
import pstats

from _repo_bootstrap import ensure_repo_import_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
ensure_repo_import_paths(repo_root=REPO_ROOT)

from backend_overlay.api import ServerAPI  # noqa: E402
from backend_overlay.app.config import config  # noqa: E402
from backend_overlay.browser.dashboard.scope_service import build_bucket_records  # noqa: E402
from backend_overlay.browser.snapshots.invalidation_service import (  # noqa: E402
    build_snapshot_targets_from_jobs,
    invalidate_summary_snapshots_for_targets,
)
from backend_overlay.browser.snapshots.warmup_service import (  # noqa: E402
    SUMMARY_WARMUP_PERIOD_ORDER,
    build_dashboard_summary_warmup_jobs,
    warm_dashboard_summary_snapshots,
)
from backend_overlay.storage import Datastore, get_storage_methods  # noqa: E402


def build_server_api(testing: bool, storage_name: str = "") -> ServerAPI:
    config_section = "server-testing" if testing else "server"
    resolved_storage = storage_name or config[config_section]["storage"]
    storage_method = get_storage_methods()[resolved_storage]
    db = Datastore(storage_method, testing=testing)
    return ServerAPI(db=db, testing=testing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect, clear, and rebuild dashboard summary snapshots."
    )
    parser.add_argument("--testing", action="store_true", help="Use testing storage paths")
    parser.add_argument(
        "--storage",
        default="",
        help="Override configured storage backend (defaults to browser backend config)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect stored snapshot segments")
    inspect_parser.add_argument("--scope-key", default="", help="Filter by exact snapshot scope key")
    inspect_parser.add_argument(
        "--period",
        action="append",
        dest="periods",
        default=[],
        help="Filter by logical period (repeatable)",
    )
    inspect_parser.add_argument("--limit", type=int, default=25, help="Maximum rows to show")

    clear_parser = subparsers.add_parser("clear", help="Delete snapshot segments")
    clear_parser.add_argument("--scope-key", default="", help="Filter by exact snapshot scope key")
    clear_parser.add_argument(
        "--period",
        action="append",
        dest="periods",
        default=[],
        help="Delete only matching logical periods (repeatable)",
    )

    warmup_parser = subparsers.add_parser("warmup", help="Build summary snapshots using configured warmup jobs")
    warmup_parser.add_argument(
        "--period",
        action="append",
        choices=SUMMARY_WARMUP_PERIOD_ORDER,
        dest="periods",
        default=[],
        help="Restrict warmup to one or more standard logical periods",
    )
    warmup_parser.add_argument(
        "--group",
        action="append",
        dest="groups",
        default=[],
        help="Restrict warmup to one or more configured device groups",
    )

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark snapshot warmup with optional cold clears and profiling",
    )
    benchmark_parser.add_argument(
        "--period",
        action="append",
        choices=SUMMARY_WARMUP_PERIOD_ORDER,
        dest="periods",
        default=[],
        help="Restrict benchmark to one or more standard logical periods",
    )
    benchmark_parser.add_argument(
        "--group",
        action="append",
        dest="groups",
        default=[],
        help="Restrict benchmark to one or more configured device groups",
    )
    benchmark_parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of benchmark runs to execute",
    )
    benchmark_parser.add_argument(
        "--cold",
        action="store_true",
        help="Clear the targeted snapshot segments before each run",
    )
    benchmark_parser.add_argument(
        "--profile-out",
        default="",
        help="Optional path to write a cProfile stats file for the first run",
    )

    rebuild_parser = subparsers.add_parser(
        "rebuild",
        help="Clear snapshot segments and then run warmup",
    )
    rebuild_parser.add_argument("--scope-key", default="", help="Filter clear step by exact snapshot scope key")
    rebuild_parser.add_argument(
        "--period",
        action="append",
        choices=SUMMARY_WARMUP_PERIOD_ORDER,
        dest="periods",
        default=[],
        help="Restrict clear/warmup to one or more standard logical periods",
    )
    rebuild_parser.add_argument(
        "--group",
        action="append",
        dest="groups",
        default=[],
        help="Restrict warmup to one or more configured device groups",
    )

    return parser.parse_args()


def resolve_warmup_jobs(
    server_api: ServerAPI,
    *,
    groups=None,
    periods=None,
):
    server_api.settings.load()
    settings_data = server_api.settings.get("")
    bucket_records = build_bucket_records(server_api.get_buckets())
    jobs = build_dashboard_summary_warmup_jobs(
        settings_data=settings_data,
        bucket_records=bucket_records,
    )

    allowed_groups = set(groups or [])
    allowed_periods = set(periods or [])
    if allowed_groups:
        jobs = [job for job in jobs if job.group_name in allowed_groups]
    if allowed_periods:
        jobs = [job for job in jobs if job.period_name in allowed_periods]

    return jobs


def resolve_warmup_targets(
    server_api: ServerAPI,
    *,
    groups=None,
    periods=None,
    scope_key: str | None = None,
):
    targets = build_snapshot_targets_from_jobs(
        resolve_warmup_jobs(server_api, groups=groups, periods=periods)
    )
    if scope_key:
        targets = [target for target in targets if target["scope_key"] == scope_key]
    return targets


def delete_warmup_targets(server_api: ServerAPI, *, groups=None, periods=None, scope_key: str | None = None) -> int:
    targets = resolve_warmup_targets(
        server_api,
        groups=groups,
        periods=periods,
        scope_key=scope_key,
    )
    return invalidate_summary_snapshots_for_targets(
        store=server_api.summary_snapshot_store,
        targets=targets,
    )


def command_inspect(server_api: ServerAPI, args: argparse.Namespace) -> None:
    periods = args.periods or None
    count = server_api.summary_snapshot_store.count_segments(
        scope_key=args.scope_key or None,
        logical_periods=periods,
    )
    rows = server_api.summary_snapshot_store.list_segments(
        scope_key=args.scope_key or None,
        logical_periods=periods,
        limit=args.limit,
    )
    payload = {"count": count, "rows": rows}
    print(json.dumps(payload, indent=2))


def command_clear(server_api: ServerAPI, args: argparse.Namespace) -> None:
    deleted = server_api.summary_snapshot_store.delete_segments(
        scope_key=args.scope_key or None,
        logical_periods=args.periods or None,
    )
    print(json.dumps({"deleted": deleted}, indent=2))


def command_warmup(server_api: ServerAPI, args: argparse.Namespace) -> None:
    jobs = warm_dashboard_summary_snapshots(
        server_api,
        group_names=args.groups or None,
        period_names=args.periods or None,
    )
    print(json.dumps({"warmed_jobs": jobs}, indent=2))


def command_benchmark(server_api: ServerAPI, args: argparse.Namespace) -> None:
    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")

    targets = resolve_warmup_targets(
        server_api,
        groups=args.groups or None,
        periods=args.periods or None,
    )

    durations = []
    deleted_per_run = []
    warmed_jobs = 0
    profile_top = None

    for index in range(args.repeat):
        deleted = 0
        if args.cold:
            deleted = delete_warmup_targets(
                server_api,
                groups=args.groups or None,
                periods=args.periods or None,
            )

        profiler = cProfile.Profile() if index == 0 and args.profile_out else None
        started_at = time.perf_counter()
        if profiler is not None:
            profiler.enable()
        warmed_jobs = warm_dashboard_summary_snapshots(
            server_api,
            group_names=args.groups or None,
            period_names=args.periods or None,
        )
        if profiler is not None:
            profiler.disable()
        duration = time.perf_counter() - started_at

        if profiler is not None:
            profiler.dump_stats(args.profile_out)
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
            stats.print_stats(20)
            profile_top = stream.getvalue()

        durations.append(duration)
        deleted_per_run.append(deleted)

    payload = {
        "cold": bool(args.cold),
        "repeat": args.repeat,
        "targets": targets,
        "warmed_jobs": warmed_jobs,
        "deleted_per_run": deleted_per_run,
        "durations_seconds": durations,
        "min_duration_seconds": min(durations),
        "max_duration_seconds": max(durations),
        "avg_duration_seconds": sum(durations) / len(durations),
    }
    if args.profile_out:
        payload["profile_out"] = args.profile_out
        payload["profile_top"] = profile_top
    print(json.dumps(payload, indent=2))


def command_rebuild(server_api: ServerAPI, args: argparse.Namespace) -> None:
    if args.scope_key or args.periods or args.groups:
        deleted = delete_warmup_targets(
            server_api,
            groups=args.groups or None,
            periods=args.periods or None,
            scope_key=args.scope_key or None,
        )
    else:
        deleted = server_api.summary_snapshot_store.delete_segments()
    jobs = warm_dashboard_summary_snapshots(
        server_api,
        group_names=args.groups or None,
        period_names=args.periods or None,
    )
    print(json.dumps({"deleted": deleted, "warmed_jobs": jobs}, indent=2))


def main() -> None:
    args = parse_args()
    server_api = build_server_api(testing=args.testing, storage_name=args.storage)

    if args.command == "inspect":
        command_inspect(server_api, args)
    elif args.command == "clear":
        command_clear(server_api, args)
    elif args.command == "warmup":
        command_warmup(server_api, args)
    elif args.command == "benchmark":
        command_benchmark(server_api, args)
    elif args.command == "rebuild":
        command_rebuild(server_api, args)
    else:  # pragma: no cover
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
