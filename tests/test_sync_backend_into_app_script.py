from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release" / "sync_backend_into_app.sh"


def make_app_bundle(root: Path) -> Path:
    app_path = root / "trust-me.app"
    (app_path / "Contents" / "MacOS").mkdir(parents=True)
    (app_path / "Contents" / "Frameworks").mkdir(parents=True)
    return app_path


def make_dist_bundle(root: Path, *, executable_name: str) -> Path:
    dist_dir = root / "dist"
    dist_dir.mkdir()

    executable_path = dist_dir / executable_name
    executable_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    executable_path.chmod(0o755)

    framework_dir = dist_dir / "aw-core"
    framework_dir.mkdir()
    (framework_dir / "README.txt").write_text("framework payload\n", encoding="utf-8")

    return dist_dir


def run_sync_script(app_path: Path, dist_dir: Path) -> None:
    subprocess.run(
        ["bash", str(SCRIPT_PATH), str(app_path), str(dist_dir)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_sync_backend_into_app_accepts_aw_server_binary(tmp_path) -> None:
    app_path = make_app_bundle(tmp_path)
    dist_dir = make_dist_bundle(tmp_path, executable_name="aw-server")

    run_sync_script(app_path, dist_dir)

    assert (app_path / "Contents" / "MacOS" / "aw-server").exists()
    assert (app_path / "Contents" / "Frameworks" / "aw-core" / "README.txt").exists()
    assert not (app_path / "Contents" / "Frameworks" / "aw-server").exists()


def test_sync_backend_into_app_accepts_legacy_trustme_api_binary(tmp_path) -> None:
    app_path = make_app_bundle(tmp_path)
    dist_dir = make_dist_bundle(tmp_path, executable_name="trustme-api")

    run_sync_script(app_path, dist_dir)

    assert (app_path / "Contents" / "MacOS" / "aw-server").exists()
    assert (app_path / "Contents" / "Frameworks" / "aw-core" / "README.txt").exists()
    assert not (app_path / "Contents" / "Frameworks" / "trustme-api").exists()
