import logging
import threading
import time


logger = logging.getLogger(__name__)

SUMMARY_WARMUP_INTERVAL_SECONDS = 60


def start_dashboard_summary_warmup(server_api) -> threading.Thread:
    worker = threading.Thread(
        target=_warmup_loop,
        args=(server_api,),
        name="dashboard-summary-warmup",
        daemon=True,
    )
    worker.start()
    return worker


def _warmup_loop(server_api) -> None:
    from backend_overlay.browser.snapshots.warmup_service import warm_dashboard_summary_snapshots

    while True:
        started_at = time.monotonic()
        try:
            job_count = warm_dashboard_summary_snapshots(server_api)
            duration = time.monotonic() - started_at
            logger.info(
                "Dashboard summary warmup completed",
                extra={"jobs": job_count, "duration_seconds": round(duration, 3)},
            )
        except Exception:
            logger.exception("Dashboard summary warmup failed")

        time.sleep(SUMMARY_WARMUP_INTERVAL_SECONDS)
