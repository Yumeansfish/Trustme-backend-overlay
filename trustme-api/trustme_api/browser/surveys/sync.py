from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence


ALLOWED_VIDEO_SUFFIXES = (".mov", ".mp4")

REMOTE_DELETE_SCRIPT = r"""
import json
import os
import sys

remote_dir = os.path.expanduser(sys.argv[1])
names = json.loads(sys.stdin.read() or "[]")

for name in names:
    if not isinstance(name, str):
        continue
    normalized_name = os.path.basename(name)
    if not normalized_name:
        continue
    try:
        os.remove(os.path.join(remote_dir, normalized_name))
    except FileNotFoundError:
        pass
"""


def default_survey_video_cache_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path.home() / ".cache"
    return base / "trust-me" / "surveys" / "videos"


def default_survey_video_remote_host() -> str:
    return os.getenv("TRUSTME_SURVEY_VIDEO_REMOTE_HOST", "uc-workstation")


def default_survey_video_remote_dir() -> str:
    return os.getenv("TRUSTME_SURVEY_VIDEO_REMOTE_DIR", "~/highlights")


@dataclass(frozen=True)
class RemoteSurveyVideo:
    name: str
    remote_path: str


@dataclass(frozen=True)
class SurveyVideoSyncResult:
    remote_host: str
    remote_dir: str
    local_dir: str
    copied: List[str]
    skipped_existing: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _build_remote_find_command(remote_dir: str) -> str:
    if remote_dir == "~":
        normalized_dir = "$HOME"
    elif remote_dir.startswith("~/"):
        normalized_dir = "$HOME/" + shlex.quote(remote_dir[2:])
    else:
        normalized_dir = shlex.quote(remote_dir)
    return (
        f"find {normalized_dir} -maxdepth 1 -type f "
        "\\( -name '*.mov' -o -name '*.mp4' \\) | sort"
    )


def list_remote_survey_videos(
    remote_host: str,
    remote_dir: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> List[RemoteSurveyVideo]:
    command = _build_remote_find_command(remote_dir)
    completed = runner(
        ["ssh", remote_host, command],
        check=True,
        capture_output=True,
        text=True,
    )
    videos: List[RemoteSurveyVideo] = []
    for line in completed.stdout.splitlines():
        remote_path = line.strip()
        if not remote_path:
            continue
        name = Path(remote_path).name
        if Path(name).suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
            continue
        videos.append(RemoteSurveyVideo(name=name, remote_path=remote_path))
    return videos


def copy_remote_survey_video(
    remote_host: str,
    remote_path: str,
    local_path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    runner(
        ["scp", f"{remote_host}:{remote_path}", str(local_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def _normalize_video_names(video_names: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for name in video_names:
        if not isinstance(name, str):
            continue
        basename = Path(name).name
        if not basename:
            continue
        if Path(basename).suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
            continue
        normalized.append(basename)
    return normalized


def delete_local_survey_videos(
    video_names: Iterable[str],
    *,
    local_dir: Path | None = None,
) -> List[str]:
    resolved_local_dir = (local_dir or default_survey_video_cache_dir()).expanduser().resolve()
    deleted: List[str] = []
    for name in _normalize_video_names(video_names):
        target = resolved_local_dir / name
        try:
            target.unlink()
        except FileNotFoundError:
            continue
        deleted.append(name)
    return deleted


def delete_remote_survey_videos(
    video_names: Iterable[str],
    *,
    remote_host: str | None = None,
    remote_dir: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> List[str]:
    normalized_names = _normalize_video_names(video_names)
    if not normalized_names:
        return []
    resolved_remote_host = remote_host or default_survey_video_remote_host()
    resolved_remote_dir = remote_dir or default_survey_video_remote_dir()
    remote_command = (
        "python3 -c "
        + shlex.quote(REMOTE_DELETE_SCRIPT)
        + " "
        + shlex.quote(resolved_remote_dir)
    )
    try:
        runner(
            ["ssh", resolved_remote_host, remote_command],
            input=json.dumps(normalized_names),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - exercised via integration
        stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else str(exc)
        raise RuntimeError(
            f"Failed to delete survey videos from {resolved_remote_host}:{resolved_remote_dir}: {stderr}"
        ) from exc
    return normalized_names


def cleanup_submitted_survey_videos(
    video_names: Iterable[str],
    *,
    local_dir: Path | None = None,
    remote_host: str | None = None,
    remote_dir: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> List[str]:
    normalized_names = _normalize_video_names(video_names)
    if not normalized_names:
        return []
    delete_remote_survey_videos(
        normalized_names,
        remote_host=remote_host,
        remote_dir=remote_dir,
        runner=runner,
    )
    delete_local_survey_videos(
        normalized_names,
        local_dir=local_dir,
    )
    return normalized_names


def sync_missing_remote_videos(
    *,
    remote_host: str,
    remote_dir: str,
    local_dir: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SurveyVideoSyncResult:
    resolved_local_dir = (local_dir or default_survey_video_cache_dir()).expanduser().resolve()
    resolved_local_dir.mkdir(parents=True, exist_ok=True)

    remote_videos = list_remote_survey_videos(remote_host, remote_dir, runner=runner)
    copied: List[str] = []
    skipped_existing: List[str] = []

    for video in remote_videos:
        local_path = resolved_local_dir / video.name
        if local_path.exists():
            skipped_existing.append(video.name)
            continue
        copy_remote_survey_video(
            remote_host,
            video.remote_path,
            local_path,
            runner=runner,
        )
        copied.append(video.name)

    return SurveyVideoSyncResult(
        remote_host=remote_host,
        remote_dir=remote_dir,
        local_dir=str(resolved_local_dir),
        copied=copied,
        skipped_existing=skipped_existing,
    )
