#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from _repo_bootstrap import ensure_repo_import_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
ensure_repo_import_paths(repo_root=REPO_ROOT)

from backend_overlay.browser.surveys.sync import (  # noqa: E402
    default_survey_video_cache_dir,
    default_survey_video_remote_dir,
    default_survey_video_remote_host,
    sync_missing_remote_videos,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync remote survey videos into the local trust-me cache."
    )
    parser.add_argument(
        "--remote-host",
        default=default_survey_video_remote_host(),
        help="SSH host or alias to sync from.",
    )
    parser.add_argument(
        "--remote-dir",
        default=default_survey_video_remote_dir(),
        help="Remote directory containing survey videos.",
    )
    parser.add_argument(
        "--local-dir",
        default="",
        help="Optional local cache directory. Defaults to the trust-me survey cache.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = sync_missing_remote_videos(
        remote_host=args.remote_host,
        remote_dir=args.remote_dir,
        local_dir=Path(args.local_dir).expanduser() if args.local_dir else default_survey_video_cache_dir(),
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
