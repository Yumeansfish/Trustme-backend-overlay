import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from aw_core.dirs import get_data_dir

from .dashboard_dto import CheckinsResponse, serialize_checkins_response


CHECKIN_SESSION_GAP = timedelta(minutes=10)
LOCAL_TZ = datetime.now().astimezone().tzinfo
FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<event>CURRENT QUESTION: .+|FEEDBACK LEVEL: -?\d+|QUESTION SKIPPED|GAME FINISHED)$"
)


QUESTION_META: Dict[str, Dict[str, str]] = {
    "SLEEP": {"emoji": "🌙", "label": "Sleep"},
    "1": {"emoji": "🎯", "label": "Focus"},
    "2": {"emoji": "⚡", "label": "Energy"},
    "3": {"emoji": "🙂", "label": "Mood"},
    "4": {"emoji": "🧠", "label": "Clarity"},
    "5": {"emoji": "🚀", "label": "Momentum"},
    "6": {"emoji": "🧘", "label": "Stress"},
    "7": {"emoji": "🤝", "label": "Connection"},
    "8": {"emoji": "🌿", "label": "Balance"},
    "9": {"emoji": "📈", "label": "Progress"},
}


@dataclass(frozen=True)
class CheckinPair:
    question_id: str
    prompted_at: datetime
    answered_at: datetime
    kind: str
    score: Optional[int]


def resolve_checkins_data_dir() -> Path:
    bundled_dir = Path(__file__).resolve().parent / "checkins_data"
    candidates = [
        os.getenv("TRUSTME_CHECKINS_DIR"),
        Path(get_data_dir("aw-server")) / "checkins",
        bundled_dir,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and any(path.iterdir()):
            return path
    return bundled_dir


def build_checkins_payload(*, date_filter: Optional[str] = None) -> CheckinsResponse:
    data_dir = resolve_checkins_data_dir()
    all_files = _list_checkin_files(data_dir, date_filter=None)
    files = _list_checkin_files(data_dir, date_filter=date_filter)
    sessions: List[Dict[str, Any]] = []
    for file_path in files:
        sessions.extend(_parse_sessions_from_file(file_path))

    sessions.sort(key=lambda session: session["started_at"], reverse=True)
    return serialize_checkins_response(
        {
            "data_source": str(data_dir),
            "available_dates": [file_path.name for file_path in all_files],
            "sessions": sessions,
        }
    )


def _list_checkin_files(data_dir: Path, *, date_filter: Optional[str]) -> List[Path]:
    if not data_dir.exists():
        return []
    files = sorted(
        [
            path
            for path in data_dir.iterdir()
            if path.is_file() and FILENAME_PATTERN.match(path.name)
        ]
    )
    if date_filter:
        return [path for path in files if path.name == date_filter]
    return files


def _parse_sessions_from_file(path: Path) -> List[Dict[str, Any]]:
    pairs: List[CheckinPair] = []
    pending_question: Optional[Dict[str, Any]] = None

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = LINE_PATTERN.match(line)
        if not match:
            continue

        timestamp = _parse_local_timestamp(match.group("timestamp"))
        event = match.group("event")

        if event.startswith("CURRENT QUESTION: "):
            pending_question = {
                "question_id": event.split(": ", 1)[1].strip(),
                "prompted_at": timestamp,
            }
            continue

        if event == "GAME FINISHED":
            pending_question = None
            continue

        if pending_question is None:
            continue

        if event.startswith("FEEDBACK LEVEL: "):
            score = int(event.split(": ", 1)[1].strip())
            pairs.append(
                CheckinPair(
                    question_id=pending_question["question_id"],
                    prompted_at=pending_question["prompted_at"],
                    answered_at=timestamp,
                    kind="score",
                    score=score,
                )
            )
            pending_question = None
            continue

        if event == "QUESTION SKIPPED":
            pairs.append(
                CheckinPair(
                    question_id=pending_question["question_id"],
                    prompted_at=pending_question["prompted_at"],
                    answered_at=timestamp,
                    kind="skipped",
                    score=None,
                )
            )
            pending_question = None

    sessions: List[Dict[str, Any]] = []
    current_pairs: List[CheckinPair] = []
    for pair in pairs:
        if not current_pairs:
            current_pairs = [pair]
            continue

        if _starts_new_session(current_pairs[-1], pair):
            sessions.append(_build_session(path.name, len(sessions), current_pairs))
            current_pairs = [pair]
        else:
            current_pairs.append(pair)

    if current_pairs:
        sessions.append(_build_session(path.name, len(sessions), current_pairs))

    return sessions


def _starts_new_session(previous: CheckinPair, current: CheckinPair) -> bool:
    if current.question_id == "SLEEP":
        return True

    gap = current.prompted_at - previous.answered_at
    if gap > CHECKIN_SESSION_GAP:
        return True

    if previous.question_id == "SLEEP":
        return False

    return _question_rank(current.question_id) <= _question_rank(previous.question_id)


def _build_session(file_date: str, index: int, pairs: Sequence[CheckinPair]) -> Dict[str, Any]:
    started_at = min(pair.prompted_at for pair in pairs)
    ended_at = max(pair.answered_at for pair in pairs)
    timeline_end = max(ended_at, started_at + timedelta(minutes=1))
    answers = [_build_answer(pair) for pair in pairs]
    answered_count = sum(1 for answer in answers if answer["status"] == "answered")
    skipped_count = sum(1 for answer in answers if answer["status"] == "skipped")

    return {
        "id": f"{file_date}-{index + 1:02d}",
        "date": file_date,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "timeline_start": started_at.isoformat(),
        "timeline_end": timeline_end.isoformat(),
        "duration_seconds": max(int((ended_at - started_at).total_seconds()), 1),
        "kind": "sleep" if len(pairs) == 1 and pairs[0].question_id == "SLEEP" else "session",
        "answered_count": answered_count,
        "skipped_count": skipped_count,
        "answers": answers,
    }


def _build_answer(pair: CheckinPair) -> Dict[str, Any]:
    meta = QUESTION_META.get(pair.question_id, {"emoji": "📝", "label": f"Prompt {pair.question_id}"})
    if pair.kind == "skipped":
        value_label = "Skipped"
        progress = None
        status = "skipped"
    elif pair.score is None or pair.score < 0:
        value_label = "No Response"
        progress = None
        status = "muted"
    else:
        value_label = f"{pair.score}/5"
        progress = round(max(0, min(pair.score, 5)) / 5 * 100, 1)
        status = "answered"

    return {
        "question_id": pair.question_id,
        "emoji": meta["emoji"],
        "label": meta["label"],
        "status": status,
        "value": pair.score,
        "value_label": value_label,
        "progress": progress,
    }


def _parse_local_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)


def _question_rank(question_id: str) -> int:
    if question_id == "SLEEP":
        return 0
    try:
        return int(question_id)
    except (TypeError, ValueError):
        return 999
