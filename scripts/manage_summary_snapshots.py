#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "aw-server"))
sys.path.insert(0, str(REPO_ROOT / "aw-core"))

from aw_datastore import Datastore, get_storage_methods  # noqa: E402
from aw_server.api import ServerAPI  # noqa: E402
from aw_server.config import config  # noqa: E402
from aw_server.dashboard_summary_warmup import (  # noqa: E402
    SUMMARY_WARMUP_PERIOD_ORDER,
    warm_dashboard_summary_snapshots,
)


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
        help="Override configured storage backend (defaults to aw-server config)",
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


def command_rebuild(server_api: ServerAPI, args: argparse.Namespace) -> None:
    deleted = server_api.summary_snapshot_store.delete_segments(
        scope_key=args.scope_key or None,
        logical_periods=args.periods or None,
    )
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
    elif args.command == "rebuild":
        command_rebuild(server_api, args)
    else:  # pragma: no cover
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
