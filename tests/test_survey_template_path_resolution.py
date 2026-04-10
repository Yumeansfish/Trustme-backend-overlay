from pathlib import Path

from trustme_api.browser.surveys import survey_template


def _patch_get_data_dir(monkeypatch, provider) -> None:
    monkeypatch.setattr(survey_template, "get_data_dir", provider)
    overlay_module = getattr(survey_template, "_overlay_module", None)
    if overlay_module is not None:
        monkeypatch.setattr(overlay_module, "get_data_dir", provider)


def _module_path(tmp_path: Path) -> Path:
    return tmp_path / "pkg" / "trustme_api" / "browser" / "surveys" / "survey_template.py"


def test_survey_template_candidates_follow_env_package_runtime_order(tmp_path: Path, monkeypatch) -> None:
    module_path = _module_path(tmp_path)
    override_path = tmp_path / "override.json"
    runtime_dir = tmp_path / "runtime-data"

    monkeypatch.setenv("TRUSTME_SURVEY_TEMPLATE_PATH", str(override_path))
    _patch_get_data_dir(monkeypatch, lambda _: str(runtime_dir))

    candidates = survey_template._survey_template_path_candidates(module_path)

    assert candidates == [
        override_path,
        module_path.with_name("fixed_questionnaire.v1.json"),
        module_path.parents[2] / "Resources" / "aw_server" / "surveys" / "fixed_questionnaire.v1.json",
        runtime_dir / "surveys" / "fixed_questionnaire.v1.json",
    ]
    assert all("Desktop/trust-me" not in str(path) for path in candidates)


def test_questionnaire_path_prefers_bundled_file_over_runtime_dir(tmp_path: Path, monkeypatch) -> None:
    module_path = _module_path(tmp_path)
    bundled_path = module_path.with_name("fixed_questionnaire.v1.json")
    runtime_path = tmp_path / "runtime-data" / "surveys" / "fixed_questionnaire.v1.json"

    bundled_path.parent.mkdir(parents=True, exist_ok=True)
    bundled_path.write_text("{}", encoding="utf-8")
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text('{"questions": []}', encoding="utf-8")

    monkeypatch.delenv("TRUSTME_SURVEY_TEMPLATE_PATH", raising=False)
    _patch_get_data_dir(monkeypatch, lambda _: str(tmp_path / "runtime-data"))

    assert survey_template._questionnaire_path(module_path) == bundled_path
