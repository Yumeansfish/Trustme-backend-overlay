import functools
import json
import logging
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from socket import gethostname
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from uuid import uuid4

import iso8601
from trustme_api.__about__ import __version__
from trustme_api.browser.canonical.repository import SqliteCanonicalUnitRepository
from trustme_api.browser.dashboard.repository import DashboardAvailabilityRepository
from trustme_api.browser.dashboard.scope_service import (
    resolve_group_names_for_host,
    resolve_logical_days_for_range,
)
from trustme_api.browser.dashboard.service import DashboardAPI
from trustme_api.browser.dashboard.dto import (
    DashboardDefaultHostsResponse,
    DashboardDetailsResponse,
    DashboardScopeResponse,
    CheckinsResponse,
    SummarySnapshotResponse,
)
from trustme_api.browser.dashboard.public_names import bucket_display_name
from trustme_api.browser.settings.schema import canonicalize_setting_key
from trustme_api.browser.settings.service import Settings
from trustme_api.browser.surveys.repository import SurveyAnswerRepository
from trustme_api.browser.surveys.api_facade import SurveyAPI
from trustme_api.browser.snapshots.invalidation_service import (
    invalidate_canonical_units_for_bucket_time_range,
    invalidate_canonical_units_for_settings,
    invalidate_summary_snapshots_for_settings,
)
from trustme_api.browser.snapshots.repository import SummarySnapshotRepository
from trustme_api.browser.snapshots.warmup import build_bucket_records
from trustme_api.exceptions import BadRequest, NotFound
from trustme_api.query import query2
from trustme_api.shared.dirs import get_data_dir
from trustme_api.shared.log import get_log_file_path
from trustme_api.shared.models import Event
from trustme_api.transform import heartbeat_merge

logger = logging.getLogger(__name__)

SUMMARY_SNAPSHOT_INVALIDATION_SETTINGS = {
    "startOfWeek",
    "classes",
    "deviceMappings",
    "always_active_pattern",
}


def get_device_id() -> str:
    path = Path(get_data_dir("aw-server")) / "device_id"
    if path.exists():
        with open(path) as f:
            return f.read()
    else:
        uuid = str(uuid4())
        with open(path, "w") as f:
            f.write(uuid)
        return uuid


def check_bucket_exists(f):
    @functools.wraps(f)
    def g(self, bucket_id, *args, **kwargs):
        if bucket_id not in self.db.buckets():
            raise NotFound("NoSuchBucket", f"There's no bucket named {bucket_id}")
        return f(self, bucket_id, *args, **kwargs)

    return g


class ServerAPI:
    def __init__(self, db, testing) -> None:
        self.db = db
        self.settings = Settings(testing)
        self.testing = testing
        self.last_event = {}  # type: dict
        self.summary_snapshot_store = SummarySnapshotRepository(testing=testing)
        self.canonical_unit_store = SqliteCanonicalUnitRepository(testing=testing)
        self.dashboard_availability_store = DashboardAvailabilityRepository(testing=testing)
        self.survey_answer_store = SurveyAnswerRepository(testing=testing)
        self.dashboard = DashboardAPI(
            db=db,
            settings=self.settings,
            summary_snapshot_store=self.summary_snapshot_store,
            canonical_unit_store=self.canonical_unit_store,
            dashboard_availability_store=self.dashboard_availability_store,
            get_buckets=self.get_buckets,
        )
        self.surveys = SurveyAPI(answer_store=self.survey_answer_store)

    def _get_latest_bucket_event(self, bucket_id: str) -> Optional[Event]:
        if bucket_id in self.last_event:
            return self.last_event[bucket_id]

        last_events = self.db[bucket_id].get(limit=1)
        if not last_events:
            return None
        return last_events[0]

    def _invalidate_summary_snapshots_for_retroactive_write(
        self,
        bucket_id: str,
        *,
        write_start: datetime,
        write_end: Optional[datetime] = None,
        latest_event: Optional[Event] = None,
    ) -> int:
        latest_event = latest_event or self._get_latest_bucket_event(bucket_id)
        if latest_event is None:
            return 0

        latest_end = latest_event.timestamp + latest_event.duration
        if write_start >= latest_end:
            return 0

        snapshot_deleted = self.summary_snapshot_store.delete_segments()
        canonical_deleted = invalidate_canonical_units_for_bucket_time_range(
            store=self.canonical_unit_store,
            settings_data=self.settings.get(""),
            bucket_records=build_bucket_records(self.get_buckets()),
            bucket_id=bucket_id,
            range_start=write_start,
            range_end=write_end or write_start,
        )
        if snapshot_deleted or canonical_deleted:
            logger.info(
                "Invalidated snapshot caches after retroactive write in bucket '%s'",
                bucket_id,
                extra={
                    "deleted_summary_segments": snapshot_deleted,
                    "deleted_canonical_units": canonical_deleted,
                },
            )
        return snapshot_deleted + canonical_deleted

    def _invalidate_summary_snapshots_for_event_deletion(
        self,
        bucket_id: str,
        event: Optional[Event],
    ) -> int:
        if event is None:
            return 0

        snapshot_deleted = self.summary_snapshot_store.delete_segments()
        canonical_deleted = invalidate_canonical_units_for_bucket_time_range(
            store=self.canonical_unit_store,
            settings_data=self.settings.get(""),
            bucket_records=build_bucket_records(self.get_buckets()),
            bucket_id=bucket_id,
            range_start=event.timestamp,
            range_end=event.timestamp + event.duration,
        )
        if snapshot_deleted or canonical_deleted:
            logger.info(
                "Invalidated snapshot caches after deleting event %s from bucket '%s'",
                getattr(event, "id", None),
                bucket_id,
                extra={
                    "deleted_summary_segments": snapshot_deleted,
                    "deleted_canonical_units": canonical_deleted,
                },
            )
        return snapshot_deleted + canonical_deleted

    def _clear_dashboard_availability(self) -> None:
        self.dashboard_availability_store.clear()

    def _mark_dashboard_availability_for_write(
        self,
        bucket_id: str,
        *,
        write_start: datetime,
        write_end: Optional[datetime] = None,
        latest_event: Optional[Event] = None,
    ) -> None:
        bucket = self.get_buckets().get(bucket_id)
        if not bucket:
            return

        host = bucket.get("hostname") or bucket.get("data", {}).get("hostname")
        if not isinstance(host, str) or not host:
            return

        logical_days = resolve_logical_days_for_range(
            settings_data=self.settings.get(""),
            range_start=write_start,
            range_end=write_end or (write_start + timedelta(seconds=1)),
        )
        if not logical_days:
            return

        group_names = resolve_group_names_for_host(
            settings_data=self.settings.get(""),
            bucket_records=build_bucket_records(self.get_buckets()),
            host=host,
        )
        if not group_names:
            return

        for group_name in group_names:
            self.dashboard_availability_store.mark_days_available(
                group_name=group_name,
                logical_days=logical_days,
            )

    def get_info(self) -> Dict[str, Any]:
        """Get server info"""
        payload = {
            "hostname": gethostname(),
            "version": __version__,
            "testing": self.testing,
            "device_id": get_device_id(),
        }
        return payload

    def get_buckets(self) -> Dict[str, Dict]:
        """Get dict {bucket_name: Bucket} of all buckets"""
        logger.debug("Received get request for buckets")
        buckets = self.db.buckets()
        for b in buckets:
            # TODO: Move this code to aw-core?
            last_events = self.db[b].get(limit=1)
            if len(last_events) > 0:
                last_event = last_events[0]
                last_updated = last_event.timestamp + last_event.duration
                buckets[b]["last_updated"] = last_updated.isoformat()
            buckets[b]["display_name"] = bucket_display_name(
                b, buckets[b].get("hostname")
            )
        return buckets

    @check_bucket_exists
    def get_bucket_metadata(self, bucket_id: str) -> Dict[str, Any]:
        """Get metadata about bucket."""
        bucket = self.db[bucket_id]
        metadata = bucket.metadata()
        metadata["display_name"] = bucket_display_name(
            bucket_id, metadata.get("hostname")
        )
        return metadata

    @check_bucket_exists
    def export_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Export a bucket to a dataformat consistent across versions, including all events in it."""
        bucket = self.get_bucket_metadata(bucket_id)
        bucket["events"] = self.get_events(bucket_id, limit=-1)
        # Scrub event IDs
        for event in bucket["events"]:
            del event["id"]
        return bucket

    def export_all(self) -> Dict[str, Any]:
        """Exports all buckets and their events to a format consistent across versions"""
        buckets = self.get_buckets()
        exported_buckets = {}
        for bid in buckets.keys():
            exported_buckets[bid] = self.export_bucket(bid)
        return exported_buckets

    def import_bucket(self, bucket_data: Any):
        bucket_id = bucket_data["id"]
        logger.info(f"Importing bucket {bucket_id}")

        # TODO: Check that bucket doesn't already exist
        self.db.create_bucket(
            bucket_id,
            type=bucket_data["type"],
            client=bucket_data["client"],
            hostname=bucket_data["hostname"],
            created=(
                bucket_data["created"]
                if isinstance(bucket_data["created"], datetime)
                else iso8601.parse_date(bucket_data["created"])
            ),
        )

        # scrub IDs from events
        # (otherwise causes weird bugs with no events seemingly imported when importing events exported from aw-server-rust, which contains IDs)
        for event in bucket_data["events"]:
            if "id" in event:
                del event["id"]

        self.create_events(
            bucket_id,
            [Event(**e) if isinstance(e, dict) else e for e in bucket_data["events"]],
        )

    def import_all(self, buckets: Dict[str, Any]):
        for bid, bucket in buckets.items():
            self.import_bucket(bucket)

    def create_bucket(
        self,
        bucket_id: str,
        event_type: str,
        client: str,
        hostname: str,
        created: Optional[datetime] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a bucket.

        If hostname is "!local", the hostname and device_id will be set from the server info.
        This is useful for watchers which are known/assumed to run locally but might not know their hostname (like aw-watcher-web).

        Returns True if successful, otherwise false if a bucket with the given ID already existed.
        """
        if created is None:
            created = datetime.now()
        if bucket_id in self.db.buckets():
            return False
        if hostname == "!local":
            info = self.get_info()
            if data is None:
                data = {}
            hostname = info["hostname"]
            data["device_id"] = info["device_id"]
        self.db.create_bucket(
            bucket_id,
            type=event_type,
            client=client,
            hostname=hostname,
            created=created,
            data=data,
        )
        return True

    @check_bucket_exists
    def update_bucket(
        self,
        bucket_id: str,
        event_type: Optional[str] = None,
        client: Optional[str] = None,
        hostname: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update bucket metadata"""
        self.db.update_bucket(
            bucket_id,
            type=event_type,
            client=client,
            hostname=hostname,
            data=data,
        )
        return None

    @check_bucket_exists
    def delete_bucket(self, bucket_id: str) -> None:
        """Delete a bucket"""
        self.db.delete_bucket(bucket_id)
        logger.debug(f"Deleted bucket '{bucket_id}'")
        return None

    @check_bucket_exists
    def get_event(
        self,
        bucket_id: str,
        event_id: int,
    ) -> Optional[Event]:
        """Get a single event from a bucket"""
        logger.debug(
            f"Received get request for event {event_id} in bucket '{bucket_id}'"
        )
        event = self.db[bucket_id].get_by_id(event_id)
        return event.to_json_dict() if event else None

    @check_bucket_exists
    def get_events(
        self,
        bucket_id: str,
        limit: int = -1,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Event]:
        """Get events from a bucket"""
        logger.debug(f"Received get request for events in bucket '{bucket_id}'")
        if limit is None:  # Let limit = None also mean "no limit"
            limit = -1
        events = [
            event.to_json_dict() for event in self.db[bucket_id].get(limit, start, end)
        ]
        return events

    @check_bucket_exists
    def create_events(self, bucket_id: str, events: List[Event]) -> Optional[Event]:
        """Create events for a bucket. Can handle both single events and multiple ones.

        Returns the inserted event when a single event was inserted, otherwise None."""
        latest_event = self._get_latest_bucket_event(bucket_id)
        earliest_timestamp = min((event.timestamp for event in events), default=None)
        latest_written_end = max((event.timestamp + event.duration for event in events), default=None)
        inserted = self.db[bucket_id].insert(events)
        if earliest_timestamp is not None:
            self._invalidate_summary_snapshots_for_retroactive_write(
                bucket_id,
                write_start=earliest_timestamp,
                write_end=latest_written_end,
                latest_event=latest_event,
            )
            self._mark_dashboard_availability_for_write(
                bucket_id,
                write_start=earliest_timestamp,
                write_end=latest_written_end,
                latest_event=latest_event,
            )
        return inserted

    @check_bucket_exists
    def get_eventcount(
        self,
        bucket_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Get eventcount from a bucket"""
        logger.debug(f"Received get request for eventcount in bucket '{bucket_id}'")
        return self.db[bucket_id].get_eventcount(start, end)

    @check_bucket_exists
    def delete_event(self, bucket_id: str, event_id) -> bool:
        """Delete a single event from a bucket"""
        event = self.db[bucket_id].get_by_id(event_id)
        deleted = self.db[bucket_id].delete(event_id)
        if deleted:
            self._invalidate_summary_snapshots_for_event_deletion(bucket_id, event)
            self._clear_dashboard_availability()
        return deleted

    @check_bucket_exists
    def heartbeat(self, bucket_id: str, heartbeat: Event, pulsetime: float) -> Event:
        """
        Heartbeats are useful when implementing watchers that simply keep
        track of a state, how long it's in that state and when it changes.
        A single heartbeat always has a duration of zero.

        If the heartbeat was identical to the last (apart from timestamp), then the last event has its duration updated.
        If the heartbeat differed, then a new event is created.

        Such as:
         - Active application and window title
           - Example: window watcher
         - Currently open document/browser tab/playing song
           - Example: wakatime
           - Example: browser watcher
           - Example: media watcher
         - Is the user active/inactive?
           Send an event on some interval indicating if the user is active or not.
           - Example: presence watcher

        Inspired by: https://wakatime.com/developers#heartbeats
        """
        logger.debug(
            "Received heartbeat in bucket '{}'\n\ttimestamp: {}, duration: {}, pulsetime: {}\n\tdata: {}".format(
                bucket_id,
                heartbeat.timestamp,
                heartbeat.duration,
                pulsetime,
                heartbeat.data,
            )
        )

        # When an older heartbeat arrives, we still try to merge it with the latest stored event.
        # This path is limited by the datastore API because replace_last can only update the newest
        # event, not an arbitrary matching event deeper in the bucket history.

        last_event = None
        if bucket_id not in self.last_event:
            last_events = self.db[bucket_id].get(limit=1)
            if len(last_events) > 0:
                last_event = last_events[0]
        else:
            last_event = self.last_event[bucket_id]

        if last_event:
            if last_event.data == heartbeat.data:
                merged = heartbeat_merge(last_event, heartbeat, pulsetime)
                if merged is not None:
                    # Heartbeat was merged into last_event
                    logger.debug(
                        "Received valid heartbeat, merging. (bucket: {})".format(
                            bucket_id
                        )
                    )
                    self.last_event[bucket_id] = merged
                    self.db[bucket_id].replace_last(merged)
                    self._mark_dashboard_availability_for_write(
                        bucket_id,
                        write_start=heartbeat.timestamp,
                        write_end=heartbeat.timestamp + heartbeat.duration,
                        latest_event=last_event,
                    )
                    return merged
                else:
                    logger.info(
                        "Received heartbeat after pulse window, inserting as new event. (bucket: {})".format(
                            bucket_id
                        )
                    )
            else:
                logger.debug(
                    "Received heartbeat with differing data, inserting as new event. (bucket: {})".format(
                        bucket_id
                    )
                )
        else:
            logger.info(
                "Received heartbeat, but bucket was previously empty, inserting as new event. (bucket: {})".format(
                    bucket_id
                )
            )

        self.db[bucket_id].insert(heartbeat)
        self.last_event[bucket_id] = heartbeat
        self._invalidate_summary_snapshots_for_retroactive_write(
            bucket_id,
            write_start=heartbeat.timestamp,
            write_end=heartbeat.timestamp + heartbeat.duration,
            latest_event=last_event,
        )
        self._mark_dashboard_availability_for_write(
            bucket_id,
            write_start=heartbeat.timestamp,
            write_end=heartbeat.timestamp + heartbeat.duration,
            latest_event=last_event,
        )
        return heartbeat

    def query2(self, name, query, timeperiods, _cache):
        compiled_query = "".join(query)
        result = []
        for timeperiod in timeperiods:
            period = timeperiod.split("/")[
                :2
            ]  # iso8601 timeperiods are separated by a slash
            starttime = iso8601.parse_date(period[0])
            endtime = iso8601.parse_date(period[1])
            result.append(query2.query(name, compiled_query, starttime, endtime, self.db))
        return result

    def summary_snapshot(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        category_periods: List[str],
        window_buckets: List[str],
        afk_buckets: List[str],
        stopwatch_buckets: List[str],
        filter_afk: bool,
        filter_categories: List[List[str]],
        categories: Optional[List[Any]] = None,
        always_active_pattern: Optional[str] = None,
        group_name: Optional[str] = None,
    ) -> SummarySnapshotResponse:
        return self.dashboard.summary_snapshot(
            range_start=range_start,
            range_end=range_end,
            category_periods=category_periods,
            window_buckets=window_buckets,
            afk_buckets=afk_buckets,
            stopwatch_buckets=stopwatch_buckets,
            filter_afk=filter_afk,
            filter_categories=filter_categories,
            categories=categories,
            always_active_pattern=always_active_pattern,
            group_name=group_name,
        )

    def get_checkins(self, *, date_filter: Optional[str] = None) -> CheckinsResponse:
        return self.dashboard.checkins(date_filter=date_filter)

    def resolve_dashboard_scope(
        self,
        *,
        requested_hosts: List[str],
        requested_group_name: Optional[str] = None,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> DashboardScopeResponse:
        return self.dashboard.resolve_scope(
            requested_hosts=requested_hosts,
            requested_group_name=requested_group_name,
            range_start=range_start,
            range_end=range_end,
        )

    def default_dashboard_hosts(self) -> DashboardDefaultHostsResponse:
        return self.dashboard.default_hosts()

    def dashboard_details(
        self,
        *,
        range_start: datetime,
        range_end: datetime,
        window_buckets: List[str],
        browser_buckets: List[str],
        stopwatch_buckets: List[str],
    ) -> DashboardDetailsResponse:
        return self.dashboard.details(
            range_start=range_start,
            range_end=range_end,
            window_buckets=window_buckets,
            browser_buckets=browser_buckets,
            stopwatch_buckets=stopwatch_buckets,
        )

    # TODO: Right now the log format on disk has to be JSON, this is hard to read by humans...
    def get_log(self):
        """Get the server log in json format"""
        payload = []
        with open(get_log_file_path()) as log_file:
            for line in log_file.readlines()[::-1]:
                payload.append(json.loads(line))
        return payload, 200

    def get_setting(self, key):
        """Get a setting"""
        return self.settings.get(key, None)

    def set_setting(self, key, value):
        """Set a setting"""
        previous_settings = deepcopy(self.settings.get("", {}))
        try:
            normalized_key, normalized_value = self.settings.set(key, value)
        except ValueError as exc:
            raise BadRequest("InvalidSettingValue", str(exc)) from exc

        previous_value = previous_settings.get(canonicalize_setting_key(normalized_key), None)
        if (
            normalized_key in SUMMARY_SNAPSHOT_INVALIDATION_SETTINGS
            and previous_value != normalized_value
        ):
            current_settings = deepcopy(self.settings.get("", {}))
            deleted = invalidate_summary_snapshots_for_settings(
                store=self.summary_snapshot_store,
                previous_settings_data=previous_settings,
                settings_data=current_settings,
                bucket_records=build_bucket_records(self.get_buckets()),
            )
            canonical_deleted = invalidate_canonical_units_for_settings(
                store=self.canonical_unit_store,
                previous_settings_data=previous_settings,
                settings_data=current_settings,
                bucket_records=build_bucket_records(self.get_buckets()),
            )
            logger.info(
                "Invalidated dashboard summary caches after settings change: %s",
                normalized_key,
                extra={
                    "deleted_summary_segments": deleted,
                    "deleted_canonical_units": canonical_deleted,
                },
            )
            self._clear_dashboard_availability()
        return normalized_value
