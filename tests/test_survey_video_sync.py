from pathlib import Path

from trustme_api.browser.surveys.sync import (
    SurveyVideoSyncResult,
    _build_remote_find_command,
    cleanup_submitted_survey_videos,
    delete_local_survey_videos,
    delete_remote_survey_videos,
    sync_missing_remote_videos,
)


class FakeCompletedProcess:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout


def test_build_remote_find_command_quotes_remote_dir() -> None:
    command = _build_remote_find_command("~/survey clips")
    assert "find $HOME/'survey clips'" in command
    assert "-name '*.mov'" in command
    assert "-name '*.mp4'" in command


def test_sync_missing_remote_videos_only_copies_absent_files(tmp_path: Path) -> None:
    existing = tmp_path / "2025-06-17T09-02-20.mov"
    existing.write_bytes(b"existing")

    commands = []

    def fake_runner(cmd, check, capture_output, text):
        commands.append(cmd)
        if cmd[0] == "ssh":
            return FakeCompletedProcess(
                stdout=(
                    "/home/chengyu/highlights/2025-06-17T09-02-20.mov\n"
                    "/home/chengyu/highlights/2025-06-17T20-15-45.mov\n"
                )
            )
        if cmd[0] == "scp":
            Path(cmd[-1]).write_bytes(b"copied")
            return FakeCompletedProcess()
        raise AssertionError(f"unexpected command: {cmd}")

    result = sync_missing_remote_videos(
        remote_host="uc-workstation",
        remote_dir="~/highlights",
        local_dir=tmp_path,
        runner=fake_runner,
    )

    assert result == SurveyVideoSyncResult(
        remote_host="uc-workstation",
        remote_dir="~/highlights",
        local_dir=str(tmp_path.resolve()),
        copied=["2025-06-17T20-15-45.mov"],
        skipped_existing=["2025-06-17T09-02-20.mov"],
    )
    assert (tmp_path / "2025-06-17T20-15-45.mov").read_bytes() == b"copied"
    assert commands[0][0] == "ssh"
    assert commands[1][0] == "scp"


def test_delete_local_survey_videos_ignores_missing_files(tmp_path: Path) -> None:
    existing = tmp_path / "2025-06-17T09-02-20.mov"
    existing.write_bytes(b"existing")

    deleted = delete_local_survey_videos(
        ["2025-06-17T09-02-20.mov", "2025-06-17T20-15-45.mov"],
        local_dir=tmp_path,
    )

    assert deleted == ["2025-06-17T09-02-20.mov"]
    assert not existing.exists()


def test_delete_remote_survey_videos_uses_remote_cleanup_script() -> None:
    calls = []

    def fake_runner(cmd, input, check, capture_output, text):
        calls.append((cmd, input))
        return FakeCompletedProcess()

    deleted = delete_remote_survey_videos(
        ["2025-06-17T09-02-20.mov", "2025-06-17T20-15-45.mov"],
        remote_host="uc-workstation",
        remote_dir="~/highlights",
        runner=fake_runner,
    )

    assert deleted == ["2025-06-17T09-02-20.mov", "2025-06-17T20-15-45.mov"]
    assert calls[0][0][0:2] == ["ssh", "uc-workstation"]
    assert calls[0][0][2].startswith("python3 -c ")
    assert "~/highlights" in calls[0][0][2]
    assert "2025-06-17T09-02-20.mov" in calls[0][1]


def test_cleanup_submitted_survey_videos_deletes_remote_then_local(tmp_path: Path) -> None:
    local_file = tmp_path / "2025-06-17T09-02-20.mov"
    local_file.write_bytes(b"video")
    commands = []

    def fake_runner(cmd, input, check, capture_output, text):
        commands.append(cmd)
        return FakeCompletedProcess()

    cleaned = cleanup_submitted_survey_videos(
        ["2025-06-17T09-02-20.mov"],
        local_dir=tmp_path,
        remote_host="uc-workstation",
        remote_dir="~/highlights",
        runner=fake_runner,
    )

    assert cleaned == ["2025-06-17T09-02-20.mov"]
    assert commands[0][0] == "ssh"
    assert not local_file.exists()
