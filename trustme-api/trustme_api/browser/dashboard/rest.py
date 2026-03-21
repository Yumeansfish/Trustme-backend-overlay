from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import iso8601
from flask import current_app, jsonify, request
from flask_restx import Namespace, Resource, fields

from .exceptions import BadRequest

dashboard_api = Namespace(
    "dashboard",
    path="/0/dashboard",
    description="Dashboard contract endpoints.",
)

summary_snapshot_query = dashboard_api.model(
    "SummarySnapshotQuery",
    {
        "range": fields.Raw(required=True, description="ISO start/end execution range"),
        "category_periods": fields.List(
            fields.String,
            required=True,
            description="Logical periods for by_period aggregation",
        ),
        "window_buckets": fields.List(fields.String, required=True),
        "afk_buckets": fields.List(fields.String, required=True),
        "stopwatch_buckets": fields.List(fields.String, required=False),
        "filter_afk": fields.Boolean(required=False),
        "categories": fields.Raw(required=False),
        "filter_categories": fields.Raw(required=False),
        "always_active_pattern": fields.String(required=False),
    },
)

dashboard_details_query = dashboard_api.model(
    "DashboardDetailsQuery",
    {
        "range": fields.Raw(required=True, description="ISO start/end execution range"),
        "window_buckets": fields.List(fields.String, required=True),
        "browser_buckets": fields.List(fields.String, required=False),
        "stopwatch_buckets": fields.List(fields.String, required=False),
    },
)


def _parse_required_range(data: Dict[str, Any], *, error_type: str) -> Tuple[datetime, datetime]:
    range_payload = data.get("range")
    if not isinstance(range_payload, dict):
        raise BadRequest(error_type, "Missing or invalid dashboard range payload")
    try:
        return (
            iso8601.parse_date(range_payload["start"]),
            iso8601.parse_date(range_payload["end"]),
        )
    except Exception as exc:
        raise BadRequest(error_type, "Missing or invalid dashboard range payload") from exc


def _parse_optional_range(
    data: Dict[str, Any],
    *,
    error_type: str,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    range_payload = data.get("range")
    if range_payload is None:
        return None, None
    if not isinstance(range_payload, dict):
        raise BadRequest(error_type, "Missing or invalid dashboard range payload")
    try:
        return (
            iso8601.parse_date(range_payload["start"]),
            iso8601.parse_date(range_payload["end"]),
        )
    except Exception as exc:
        raise BadRequest(error_type, "Missing or invalid dashboard range payload") from exc


def _parse_string_list(
    data: Dict[str, Any],
    key: str,
    *,
    error_type: str,
    field_name: Optional[str] = None,
) -> List[str]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        label = field_name or key
        raise BadRequest(error_type, f"{label} must be a list of strings")
    return value


def _parse_raw_list(
    data: Dict[str, Any],
    key: str,
    *,
    error_type: str,
    field_name: Optional[str] = None,
) -> List[Any]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        label = field_name or key
        raise BadRequest(error_type, f"{label} must be a list")
    return value


def _parse_optional_string(
    data: Dict[str, Any],
    key: str,
    *,
    error_type: str,
    field_name: Optional[str] = None,
) -> Optional[str]:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        label = field_name or key
        raise BadRequest(error_type, f"{label} must be a string")
    return value


def _parse_optional_bool(data: Dict[str, Any], key: str, *, error_type: str) -> bool:
    value = data.get(key)
    if value is None:
        return True
    if not isinstance(value, bool):
        raise BadRequest(error_type, f"{key} must be a boolean")
    return value


@dashboard_api.route("/summary-snapshot")
class SummarySnapshotResource(Resource):
    @dashboard_api.expect(summary_snapshot_query, validate=False)
    def post(self):
        data = request.get_json() or {}
        range_start, range_end = _parse_required_range(
            data,
            error_type="InvalidSummarySnapshotRange",
        )
        categories = data.get("categories")
        if categories is not None and not isinstance(categories, list):
            raise BadRequest(
                "InvalidSummarySnapshotCategories",
                "categories must be a list",
            )

        result = current_app.api.dashboard.summary_snapshot(
            range_start=range_start,
            range_end=range_end,
            category_periods=_parse_string_list(
                data,
                "category_periods",
                error_type="InvalidSummarySnapshotCategoryPeriods",
            ),
            window_buckets=_parse_string_list(
                data,
                "window_buckets",
                error_type="InvalidSummarySnapshotWindowBuckets",
            ),
            afk_buckets=_parse_string_list(
                data,
                "afk_buckets",
                error_type="InvalidSummarySnapshotAfkBuckets",
            ),
            stopwatch_buckets=_parse_string_list(
                data,
                "stopwatch_buckets",
                error_type="InvalidSummarySnapshotStopwatchBuckets",
            ),
            filter_afk=_parse_optional_bool(
                data,
                "filter_afk",
                error_type="InvalidSummarySnapshotFilterAfk",
            ),
            filter_categories=_parse_raw_list(
                data,
                "filter_categories",
                error_type="InvalidSummarySnapshotFilterCategories",
            ),
            categories=categories,
            always_active_pattern=_parse_optional_string(
                data,
                "always_active_pattern",
                error_type="InvalidSummarySnapshotAlwaysActivePattern",
            ),
        )
        return jsonify(result)


@dashboard_api.route("/resolve-scope")
class DashboardScopeResource(Resource):
    def post(self):
        data = request.get_json() or {}
        range_start, range_end = _parse_optional_range(
            data,
            error_type="InvalidDashboardScopeRange",
        )
        result = current_app.api.dashboard.resolve_scope(
            requested_hosts=_parse_string_list(
                data,
                "hosts",
                error_type="InvalidDashboardScopeHosts",
                field_name="hosts",
            ),
            range_start=range_start,
            range_end=range_end,
        )
        return jsonify(result)


@dashboard_api.route("/default-hosts")
class DashboardDefaultHostsResource(Resource):
    def get(self):
        return jsonify(current_app.api.dashboard.default_hosts())


@dashboard_api.route("/details")
class DashboardDetailsResource(Resource):
    @dashboard_api.expect(dashboard_details_query, validate=False)
    def post(self):
        data = request.get_json() or {}
        range_start, range_end = _parse_required_range(
            data,
            error_type="InvalidDashboardDetailsRange",
        )
        result = current_app.api.dashboard.details(
            range_start=range_start,
            range_end=range_end,
            window_buckets=_parse_string_list(
                data,
                "window_buckets",
                error_type="InvalidDashboardDetailsWindowBuckets",
            ),
            browser_buckets=_parse_string_list(
                data,
                "browser_buckets",
                error_type="InvalidDashboardDetailsBrowserBuckets",
            ),
            stopwatch_buckets=_parse_string_list(
                data,
                "stopwatch_buckets",
                error_type="InvalidDashboardDetailsStopwatchBuckets",
            ),
        )
        return jsonify(result)


@dashboard_api.route("/checkins")
class CheckinsResource(Resource):
    def get(self):
        date_filter = request.args.get("date", None)
        return jsonify(current_app.api.dashboard.checkins(date_filter=date_filter))
