#!/usr/bin/env python3

from __future__ import annotations

import argparse
import collections.abc
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any, get_args, get_origin, is_typeddict


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT_DIR / "aw-server" / "aw_server" / "dashboard_dto.py"
DEFAULT_EXPORTS = [
    "EventData",
    "AggregatedEvent",
    "SummaryWindow",
    "SummaryByPeriodEntry",
    "UncategorizedRow",
    "SummarySnapshotResponse",
    "BrowserSummaryResponse",
    "StopwatchSummaryResponse",
    "DashboardDetailsResponse",
    "DashboardScopeResponse",
    "DashboardDefaultHostsResponse",
    "CheckinAnswer",
    "CheckinSession",
    "CheckinsResponse",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate TypeScript dashboard DTO contracts from backend TypedDicts."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Path to dashboard_dto.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the generated TypeScript to this file instead of stdout.",
    )
    return parser.parse_args()


def load_module(module_path: Path):
    spec = importlib.util.spec_from_file_location("dashboard_dto_codegen_source", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_none_type(annotation: Any) -> bool:
    return annotation is type(None)


def normalize_union_members(members: list[str]) -> list[str]:
    normalized: list[str] = []
    for member in members:
        if member not in normalized:
            normalized.append(member)
    return normalized


def render_ts_type(annotation: Any) -> str:
    if annotation is Any:
        return "any"
    if is_none_type(annotation):
        return "null"

    forward_arg = getattr(annotation, "__forward_arg__", None)
    if isinstance(forward_arg, str):
        return forward_arg

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (types.UnionType, getattr(types, "UnionType", object), None):
        pass

    if origin in (types.UnionType, getattr(sys.modules.get("typing"), "Union", object)):
        members = normalize_union_members([render_ts_type(arg) for arg in args])
        return " | ".join(members)

    if origin in (list, tuple, set, frozenset, collections.abc.Sequence, collections.abc.Iterable):
        inner = render_ts_type(args[0]) if args else "any"
        return f"{inner}[]"

    if origin in (dict, collections.abc.Mapping):
        key_type = render_ts_type(args[0]) if len(args) > 0 else "string"
        value_type = render_ts_type(args[1]) if len(args) > 1 else "any"
        return f"Record<{key_type}, {value_type}>"

    if annotation is str:
        return "string"
    if annotation in (int, float):
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is bytes:
        return "string"

    if is_typeddict(annotation):
        return annotation.__name__

    name = getattr(annotation, "__name__", None)
    if isinstance(name, str):
        return name

    return "any"


def render_property_name(name: str) -> str:
    if name.isidentifier():
        return name
    return json.dumps(name)


def render_typeddict(name: str, typed_dict: type) -> str:
    optional_keys = getattr(typed_dict, "__optional_keys__", set())
    annotations = getattr(typed_dict, "__annotations__", {})
    lines = [f"export interface {name} {{"]

    for field_name, annotation in annotations.items():
        optional_suffix = "?" if field_name in optional_keys else ""
        lines.append(
            f"  {render_property_name(field_name)}{optional_suffix}: {render_ts_type(annotation)};"
        )

    lines.append("}")
    return "\n".join(lines)


def generate_contract(module, source_path: Path) -> str:
    interfaces: list[str] = []
    for name in DEFAULT_EXPORTS:
        typed_dict = getattr(module, name, None)
        if typed_dict is None or not is_typeddict(typed_dict):
            raise RuntimeError(f"{name} is not a TypedDict in {source_path}")
        interfaces.append(render_typeddict(name, typed_dict))

    relative_source = source_path.relative_to(ROOT_DIR)
    header = [
        "// This file is generated. Do not edit it by hand.",
        (
            "// Source: "
            f"{relative_source.as_posix()} via scripts/contracts/export_dashboard_contract_ts.py"
        ),
        "",
    ]
    return "\n".join(header + interfaces) + "\n"


def main() -> int:
    args = parse_args()
    source_path = args.source.resolve()
    module = load_module(source_path)
    generated = generate_contract(module, source_path)

    if args.output is None:
        sys.stdout.write(generated)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
