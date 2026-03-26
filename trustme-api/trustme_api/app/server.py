import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import flask.json.provider
from flask import (
    Blueprint,
    Flask,
    current_app,
    send_from_directory,
)
from flask_cors import CORS
from trustme_api.api import ServerAPI
from trustme_api.app import rest
from trustme_api.app.custom_static import get_custom_static_blueprint
from trustme_api.app.log import FlaskLogHandler
from trustme_api.browser.snapshots.warmup import start_dashboard_summary_warmup
from trustme_api.storage import Datastore, get_storage_methods

logger = logging.getLogger(__name__)


def _resolve_static_folder() -> str:
    module_path = Path(__file__).resolve()
    candidates = [
        module_path.parent / "static",
        module_path.parents[1] / "static",
        module_path.parents[2] / "static",
        module_path.parents[2] / "aw_server" / "static",
    ]

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = Path(meipass).resolve()
        candidates.extend(
            [
                meipass_path / "static",
                meipass_path / "aw_server" / "static",
            ]
        )

    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)

    raise FileNotFoundError(
        "Unable to locate bundled static assets. Checked: "
        + ", ".join(str(path) for path in candidates)
    )


static_folder = _resolve_static_folder()

root = Blueprint("root", __name__, url_prefix="/")


class AWFlask(Flask):
    def __init__(
        self,
        host: str,
        testing: bool,
        storage_method=None,
        cors_origins: Optional[List[str]] = None,
        custom_static: Optional[Dict[str, str]] = None,
        static_folder=static_folder,
        static_url_path="",
    ):
        name = "aw-server"
        self.json_provider_class = CustomJSONProvider
        # only prettyprint JSON if testing (due to perf)
        self.json_provider_class.compact = not testing

        # Initialize Flask
        Flask.__init__(
            self,
            name,
            static_folder=static_folder,
            static_url_path=static_url_path,
        )
        self.config["HOST"] = host  # needed for host-header check
        resolved_cors_origins = list(cors_origins or [])
        with self.app_context():
            _config_cors(resolved_cors_origins, testing)

        # Initialize datastore and API
        if storage_method is None:
            storage_method = get_storage_methods()["memory"]
        db = Datastore(storage_method, testing=testing)
        self.api = ServerAPI(db=db, testing=testing)

        self.register_blueprint(root)
        self.register_blueprint(rest.blueprint)
        self.register_blueprint(get_custom_static_blueprint(custom_static or {}))


class CustomJSONProvider(flask.json.provider.DefaultJSONProvider):
    # encoding/decoding of datetime as iso8601 strings
    # encoding of timedelta as second floats
    def default(self, obj, *args, **kwargs):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        return super().default(obj)


@root.route("/")
def static_root():
    return current_app.send_static_file("index.html")


@root.route("/css/<path:path>")
def static_css(path):
    return send_from_directory(os.path.join(static_folder, "css"), path)


@root.route("/js/<path:path>")
def static_js(path):
    return send_from_directory(os.path.join(static_folder, "js"), path)


def _config_cors(cors_origins: List[str], testing: bool):
    if cors_origins:
        logger.warning(
            "Running with additional allowed CORS origins specified through config "
            "or CLI argument (could be a security risk): {}".format(cors_origins)
        )

    if testing:
        # Used for development against a custom frontend artifact
        cors_origins.append("http://127.0.0.1:27180/*")

    # TODO: This could probably be more specific
    #       See https://github.com/ActivityWatch/aw-server/pull/43#issuecomment-386888769
    cors_origins.append("moz-extension://*")

    # See: https://flask-cors.readthedocs.org/en/latest/
    CORS(current_app, resources={r"/api/*": {"origins": cors_origins}})


# Only to be called from trustme_api.main function!
def _start(
    storage_method,
    host: str,
    port: int,
    testing: bool = False,
    cors_origins: Optional[List[str]] = None,
    custom_static: Optional[Dict[str, str]] = None,
):
    app = AWFlask(
        host,
        testing=testing,
        storage_method=storage_method,
        cors_origins=cors_origins,
        custom_static=custom_static,
    )
    if not testing:
        start_dashboard_summary_warmup(app.api)
    try:
        app.run(
            debug=testing,
            host=host,
            port=port,
            request_handler=FlaskLogHandler,
            use_reloader=False,
            threaded=True,
        )
    except OSError as e:
        logger.exception(e)
        raise e
