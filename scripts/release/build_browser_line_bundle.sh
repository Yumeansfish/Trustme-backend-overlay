#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -d "$REPO_ROOT/../upstream/activitywatch" ]]; then
  DEFAULT_UPSTREAM_DIR="$REPO_ROOT/../upstream/activitywatch"
  DEFAULT_BUILD_ROOT="$REPO_ROOT/../upstream/build"
else
  DEFAULT_UPSTREAM_DIR="$REPO_ROOT/upstream/activitywatch"
  DEFAULT_BUILD_ROOT="$REPO_ROOT/upstream/build"
fi

if [[ -d "$REPO_ROOT/../frontend" ]]; then
  DEFAULT_FRONTEND_DIR="$REPO_ROOT/../frontend"
else
  DEFAULT_FRONTEND_DIR="$REPO_ROOT/frontend"
fi

UPSTREAM_DIR="${UPSTREAM_DIR:-$DEFAULT_UPSTREAM_DIR}"
FRONTEND_DIR="${FRONTEND_DIR:-$DEFAULT_FRONTEND_DIR}"
BUILD_ROOT="${BUILD_ROOT:-$DEFAULT_BUILD_ROOT}"
RELEASE_VERSION="${RELEASE_VERSION:-$(git -C "$REPO_ROOT" describe --tags --always --dirty)}"
BUILD_PYTHON_VERSION="${BUILD_PYTHON_VERSION:-3.11}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

ensure_build_tooling() {
  ensure_build_python
  if [[ -x "$TOOLS_VENV/bin/python" ]]; then
    current_version="$("$TOOLS_VENV/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
    if [[ "$current_version" != "$BUILD_PYTHON_VERSION" ]]; then
      rm -rf "$TOOLS_VENV"
    fi
  fi
  if [[ ! -x "$TOOLS_VENV/bin/poetry" || ! -x "$TOOLS_VENV/bin/pyinstaller" ]]; then
    echo "==> Bootstrapping build tool venv in $TOOLS_VENV"
    "$BUILD_PYTHON_BIN" -m venv "$TOOLS_VENV"
    "$TOOLS_VENV/bin/python" -m pip install --upgrade pip wheel
    "$TOOLS_VENV/bin/pip" install poetry pyinstaller pyinstaller-hooks-contrib 'setuptools>49.1.1'
  fi
  export PATH="$TOOLS_VENV/bin:$PATH"
  export POETRY_VIRTUALENVS_CREATE=false
}

ensure_build_python() {
  if [[ -n "${BUILD_PYTHON:-}" ]]; then
    BUILD_PYTHON_BIN="$BUILD_PYTHON"
    return
  fi

  if command -v "python$BUILD_PYTHON_VERSION" >/dev/null 2>&1; then
    BUILD_PYTHON_BIN="$(command -v "python$BUILD_PYTHON_VERSION")"
    return
  fi

  if [[ -x "$LOCAL_BUILD_PYTHON_DIR/bin/python$BUILD_PYTHON_VERSION" ]]; then
    BUILD_PYTHON_BIN="$LOCAL_BUILD_PYTHON_DIR/bin/python$BUILD_PYTHON_VERSION"
    return
  fi

  echo "==> Bootstrapping Python $BUILD_PYTHON_VERSION into $LOCAL_BUILD_PYTHON_DIR"
  python3 -m venv "$BOOTSTRAP_VENV"
  "$BOOTSTRAP_VENV/bin/python" -m pip install --upgrade pip
  "$BOOTSTRAP_VENV/bin/pip" install 'pbs-installer[download,install]'
  "$BOOTSTRAP_VENV/bin/pbs-install" "$BUILD_PYTHON_VERSION" -d "$LOCAL_BUILD_PYTHON_DIR"
  BUILD_PYTHON_BIN="$LOCAL_BUILD_PYTHON_DIR/bin/python$BUILD_PYTHON_VERSION"
}

platform_name() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux) echo "linux" ;;
    *) echo "unsupported" ;;
  esac
}

sanitize_version() {
  printf '%s' "$1" | tr '/ ' '--'
}

write_metadata() {
  python3 - "$METADATA_PATH" "$ASSET_NAME" "$RELEASE_VERSION" "$BACKEND_REV" "$FRONTEND_REV" "$UPSTREAM_REV" "$PLATFORM" "$ARCH" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, asset_name, version, backend_rev, frontend_rev, upstream_rev, platform_name, arch = sys.argv[1:]
payload = {
    "asset_name": asset_name,
    "version": version,
    "backend_overlay_rev": backend_rev,
    "frontend_rev": frontend_rev,
    "upstream_rev": upstream_rev,
    "platform": platform_name,
    "arch": arch,
    "built_at_utc": datetime.now(timezone.utc).isoformat(),
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
PY
}

require_cmd git
require_cmd make
require_cmd npm
require_cmd python3
require_cmd rsync
require_cmd tar

if [[ ! -d "$UPSTREAM_DIR" ]]; then
  echo "Upstream directory not found: $UPSTREAM_DIR" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Frontend directory not found: $FRONTEND_DIR" >&2
  exit 1
fi

UPSTREAM_DIR="$(cd "$UPSTREAM_DIR" && pwd)"
FRONTEND_DIR="$(cd "$FRONTEND_DIR" && pwd)"
mkdir -p "$BUILD_ROOT"
BUILD_ROOT="$(cd "$BUILD_ROOT" && pwd)"

WORKTREE_DIR="$BUILD_ROOT/worktree/activitywatch"
GENERATED_SERVER_DIR="$BUILD_ROOT/generated/aw-server"
FRONTEND_ARTIFACT_DIR="$BUILD_ROOT/frontend-artifact"
DIST_ROOT="$BUILD_ROOT/dist"
BUNDLE_DIR="$DIST_ROOT/browser-line"
METADATA_PATH="$DIST_ROOT/release-metadata.json"
TOOLS_VENV="$BUILD_ROOT/.tools-venv"
BOOTSTRAP_VENV="$BUILD_ROOT/.bootstrap-tools"
LOCAL_BUILD_PYTHON_DIR="$BUILD_ROOT/python-$BUILD_PYTHON_VERSION"

PLATFORM="$(platform_name)"
if [[ "$PLATFORM" == "unsupported" ]]; then
  echo "Unsupported platform: $(uname -s)" >&2
  exit 1
fi
ARCH="$(uname -m)"
VERSION_SLUG="$(sanitize_version "$RELEASE_VERSION")"
ASSET_NAME="trust-me-browser-line-${VERSION_SLUG}-${PLATFORM}-${ARCH}.tar.gz"

mkdir -p "$BUILD_ROOT" "$DIST_ROOT"
rm -rf "$WORKTREE_DIR" "$GENERATED_SERVER_DIR" "$BUNDLE_DIR"

ensure_build_tooling
require_cmd poetry
require_cmd pyinstaller

echo "==> Building frontend artifact"
"$REPO_ROOT/scripts/release/sync_frontend_static.sh" "$FRONTEND_DIR" "$FRONTEND_ARTIFACT_DIR"

echo "==> Copying upstream monorepo into worktree"
mkdir -p "$(dirname "$WORKTREE_DIR")"
rsync -a \
  --delete \
  --exclude ".git" \
  --exclude ".github" \
  --exclude "__pycache__" \
  --exclude "build" \
  --exclude "dist" \
  "$UPSTREAM_DIR/" "$WORKTREE_DIR/"

echo "==> Rendering overlay aw-server from backend repo"
python3 "$SCRIPT_DIR/render_overlay_aw_server.py" \
  --backend-dir "$REPO_ROOT" \
  --upstream-aw-server-dir "$UPSTREAM_DIR/aw-server" \
  --frontend-artifact-dir "$FRONTEND_ARTIFACT_DIR" \
  --output-dir "$GENERATED_SERVER_DIR"

rm -rf "$WORKTREE_DIR/aw-server"
mkdir -p "$WORKTREE_DIR"
rsync -a "$GENERATED_SERVER_DIR/" "$WORKTREE_DIR/aw-server/"

echo "==> Ensuring setuptools compatibility"
"$TOOLS_VENV/bin/python" -m pip install 'setuptools>49.1.1'

BUILD_MODULES=(
  aw-core
  aw-client
  aw-qt
  aw-server
  aw-watcher-afk
  aw-watcher-window
  aw-watcher-input
)

PACKAGE_MODULES=(
  aw-qt
  aw-server
  aw-watcher-afk
  aw-watcher-window
  aw-watcher-input
)

install_main_dependencies() {
  local module_dir="$1"
  (
    cd "$module_dir"
    poetry install --only main
  )
}

for module in "${BUILD_MODULES[@]}"; do
  echo "==> Building $module"
  case "$module" in
    aw-watcher-window)
      install_main_dependencies "$WORKTREE_DIR/$module"
      if [[ "$PLATFORM" == "macos" ]]; then
        make -C "$WORKTREE_DIR/$module" build-swift
      fi
      ;;
    *)
      install_main_dependencies "$WORKTREE_DIR/$module"
      ;;
  esac
done

for module in "${PACKAGE_MODULES[@]}"; do
  echo "==> Packaging $module"
  make -C "$WORKTREE_DIR/$module" package SKIP_WEBUI=true
done

echo "==> Assembling portable browser-line bundle"
mkdir -p "$BUNDLE_DIR"
rsync -a "$WORKTREE_DIR/aw-qt/dist/aw-qt/" "$BUNDLE_DIR/"
for module in aw-server aw-watcher-afk aw-watcher-window aw-watcher-input; do
  mkdir -p "$BUNDLE_DIR/$module"
  rsync -a "$WORKTREE_DIR/$module/dist/$module/" "$BUNDLE_DIR/$module/"
done

BACKEND_REV="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
FRONTEND_REV="$(git -C "$FRONTEND_DIR" rev-parse --short HEAD)"
UPSTREAM_REV="$(git -C "$UPSTREAM_DIR" rev-parse --short HEAD)"

echo "==> Writing release metadata"
write_metadata

echo "==> Creating archive $ASSET_NAME"
rm -f "$DIST_ROOT/$ASSET_NAME"
tar -czf "$DIST_ROOT/$ASSET_NAME" -C "$DIST_ROOT" browser-line

echo
echo "Bundle directory: $BUNDLE_DIR"
echo "Archive: $DIST_ROOT/$ASSET_NAME"
echo "Metadata: $METADATA_PATH"
