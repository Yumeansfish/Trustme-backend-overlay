from trustme_api.browser.surveys.remote_config import (
    default_result_csv_remote_host,
    default_result_csv_remote_path,
    default_survey_remote_host,
    default_survey_video_remote_dir,
    default_survey_video_remote_host,
    resolve_survey_result_remote_config,
    resolve_survey_video_remote_config,
)


def test_shared_remote_host_is_used_when_specific_hosts_are_unset(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTME_SURVEY_REMOTE_HOST", "trust-me-server")
    monkeypatch.delenv("TRUSTME_SURVEY_VIDEO_REMOTE_HOST", raising=False)
    monkeypatch.delenv("TRUSTME_SURVEY_RESULT_REMOTE_HOST", raising=False)

    assert default_survey_remote_host() == "trust-me-server"
    assert default_survey_video_remote_host() == "trust-me-server"
    assert default_result_csv_remote_host() == "trust-me-server"


def test_specific_remote_hosts_override_shared_remote_host(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTME_SURVEY_REMOTE_HOST", "trust-me-server")
    monkeypatch.setenv("TRUSTME_SURVEY_VIDEO_REMOTE_HOST", "video-box")
    monkeypatch.setenv("TRUSTME_SURVEY_RESULT_REMOTE_HOST", "result-box")

    assert default_survey_video_remote_host() == "video-box"
    assert default_result_csv_remote_host() == "result-box"


def test_resolve_remote_configs_use_single_entrypoint(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTME_SURVEY_REMOTE_HOST", "trust-me-server")
    monkeypatch.setenv("TRUSTME_SURVEY_VIDEO_REMOTE_DIR", "~/videos")
    monkeypatch.setenv("TRUSTME_SURVEY_RESULT_REMOTE_PATH", "~/surveys/result.csv")

    video_config = resolve_survey_video_remote_config()
    result_config = resolve_survey_result_remote_config()

    assert video_config.remote_host == "trust-me-server"
    assert video_config.remote_dir == "~/videos"
    assert result_config.remote_host == "trust-me-server"
    assert result_config.remote_path == "~/surveys/result.csv"


def test_explicit_remote_config_arguments_override_environment(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTME_SURVEY_REMOTE_HOST", "trust-me-server")
    monkeypatch.setenv("TRUSTME_SURVEY_VIDEO_REMOTE_DIR", "~/videos")
    monkeypatch.setenv("TRUSTME_SURVEY_RESULT_REMOTE_PATH", "~/surveys/result.csv")

    video_config = resolve_survey_video_remote_config(
        remote_host="video-box",
        remote_dir="~/custom-videos",
    )
    result_config = resolve_survey_result_remote_config(
        remote_host="result-box",
        remote_path="~/custom-result.csv",
    )

    assert video_config.remote_host == "video-box"
    assert video_config.remote_dir == "~/custom-videos"
    assert result_config.remote_host == "result-box"
    assert result_config.remote_path == "~/custom-result.csv"


def test_default_remote_paths_remain_stable(monkeypatch) -> None:
    monkeypatch.delenv("TRUSTME_SURVEY_VIDEO_REMOTE_DIR", raising=False)
    monkeypatch.delenv("TRUSTME_SURVEY_RESULT_REMOTE_PATH", raising=False)

    assert default_survey_video_remote_dir() == "~/highlights"
    assert default_result_csv_remote_path() == "~/result.csv"
