from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release" / "render_overlay_aw_server.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("test_render_overlay_aw_server", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load release script from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_overlay_maps_from_repo_root():
    script = load_script_module()

    file_map = script.resolve_overlay_file_map(REPO_ROOT)
    dir_map = script.resolve_overlay_dir_map(REPO_ROOT)

    assert file_map["aw_server/main.py"].name == "main.py"
    assert file_map["aw_server/main.py"].exists()
    assert file_map["aw_server/dashboard_dto.py"].name == "dashboard_dto.py"
    assert dir_map["aw_server/dashboard"].name == "dashboard"
    assert dir_map["aw_server/dashboard"].is_dir()
    assert (dir_map["aw_server/settings"] / "settings_seed_knowledgebase.v1.json").exists()
    assert (dir_map["aw_server/surveys"] / "fixed_questionnaire.v1.json").exists()


def test_patch_aw_server_spec_skips_optional_demo_assets_when_missing(tmp_path):
    script = load_script_module()
    spec_path = tmp_path / "aw-server.spec"
    spec_path.write_text(script.SPEC_NEEDLE, encoding="utf-8")

    script.patch_aw_server_spec(spec_path, optional_overlay_dirs={})

    patched = spec_path.read_text(encoding="utf-8")
    assert '"aw_server/settings/settings_seed_knowledgebase.v1.json"' in patched
    assert '"aw_server/surveys/fixed_questionnaire.v1.json"' in patched
    assert '"aw_server/checkins_data"' not in patched


def test_patch_aw_server_spec_includes_optional_demo_assets_when_present(tmp_path):
    script = load_script_module()
    spec_path = tmp_path / "aw-server.spec"
    spec_path.write_text(script.SPEC_NEEDLE, encoding="utf-8")

    script.patch_aw_server_spec(
        spec_path,
        optional_overlay_dirs={"aw_server/checkins_data": tmp_path / "checkins_data"},
    )

    patched = spec_path.read_text(encoding="utf-8")
    assert '"aw_server/checkins_data"' in patched
