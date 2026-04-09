from __future__ import annotations

import json
import shlex
import subprocess
from typing import Callable, Dict, Iterable, List, Sequence

from .remote_config import (
    default_result_csv_remote_host,
    default_result_csv_remote_path,
    resolve_survey_result_remote_config,
)


RESULT_CSV_HEADER = ["Timestamp", "Video Name", "Question", "Answer"]

REMOTE_APPEND_SCRIPT = r"""
import csv
import json
import os
import sys

target_path = os.path.expanduser(sys.argv[1])
payload = json.loads(sys.stdin.read() or "[]")

directory = os.path.dirname(target_path)
if directory:
    os.makedirs(directory, exist_ok=True)

file_exists = os.path.exists(target_path) and os.path.getsize(target_path) > 0
with open(target_path, "a", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    if not file_exists:
        writer.writerow(["Timestamp", "Video Name", "Question", "Answer"])
    writer.writerows(payload)
"""
def _build_question_text_lookup(questions: Sequence[Dict]) -> Dict[str, str]:
    return {
        question["id"]: question["text"]
        for question in questions
        if isinstance(question, dict)
        and isinstance(question.get("id"), str)
        and isinstance(question.get("text"), str)
    }


def _build_option_label_lookup(questions: Sequence[Dict]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for question in questions:
        if not isinstance(question, dict):
            continue
        for option in question.get("options", []):
            if not isinstance(option, dict):
                continue
            option_id = option.get("id")
            label = option.get("label")
            if isinstance(option_id, str) and isinstance(label, str):
                labels[option_id] = label
    return labels


def build_result_csv_rows(
    *,
    submitted_at: str,
    survey_template: Dict,
    videos: Sequence[Dict],
    global_answers: Iterable[Dict[str, str]],
    video_answers: Iterable[Dict],
) -> List[List[str]]:
    global_questions = survey_template.get("global_questions") or []
    video_questions = survey_template.get("video_questions") or survey_template.get("questions") or []
    global_question_lookup = _build_question_text_lookup(global_questions)
    video_question_lookup = _build_question_text_lookup(video_questions)
    global_option_lookup = _build_option_label_lookup(global_questions)
    video_option_lookup = _build_option_label_lookup(video_questions)
    video_name_lookup = {
        video["video_id"]: video.get("filename") or video["video_id"]
        for video in videos
        if isinstance(video, dict) and isinstance(video.get("video_id"), str)
    }

    rows: List[List[str]] = []
    for answer in global_answers:
        if not isinstance(answer, dict):
            continue
        question_id = answer.get("question_id")
        option_id = answer.get("option_id")
        if not isinstance(question_id, str) or not isinstance(option_id, str):
            continue
        rows.append(
            [
                submitted_at,
                "",
                global_question_lookup.get(question_id, question_id),
                global_option_lookup.get(option_id, option_id),
            ]
        )

    for section in video_answers:
        if not isinstance(section, dict):
            continue
        video_id = section.get("video_id")
        answers = section.get("answers")
        if not isinstance(video_id, str) or not isinstance(answers, list):
            continue
        video_name = video_name_lookup.get(video_id, video_id)
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            question_id = answer.get("question_id")
            option_id = answer.get("option_id")
            if not isinstance(question_id, str) or not isinstance(option_id, str):
                continue
            rows.append(
                [
                    submitted_at,
                    video_name,
                    video_question_lookup.get(question_id, question_id),
                    video_option_lookup.get(option_id, option_id),
                ]
            )

    return rows


def append_rows_to_remote_result_csv(
    rows: Sequence[Sequence[str]],
    *,
    remote_host: str | None = None,
    remote_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    remote_config = resolve_survey_result_remote_config(
        remote_host=remote_host,
        remote_path=remote_path,
    )
    remote_command = (
        "python3 -c "
        + shlex.quote(REMOTE_APPEND_SCRIPT)
        + " "
        + shlex.quote(remote_config.remote_path)
    )

    try:
        runner(
            ["ssh", remote_config.remote_host, remote_command],
            input=json.dumps([list(row) for row in rows]),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - exercised via integration
        stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else str(exc)
        raise RuntimeError(
            f"Failed to append survey results to {remote_config.remote_host}:{remote_config.remote_path}: {stderr}"
        ) from exc
