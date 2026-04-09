#!/usr/bin/env bash

set -euo pipefail

APP_PATH="${1:-}"
DIST_DIR="${2:-}"
MANIFEST_NAME=".trustme-browser-backend-manifest"

if [[ -z "$APP_PATH" || -z "$DIST_DIR" ]]; then
  echo "Usage: $0 /Applications/trust-me.app /path/to/dist/backend-bundle" >&2
  exit 1
fi

APP_PATH="${APP_PATH%/}"
DIST_DIR="${DIST_DIR%/}"
APP_MACOS_DIR="$APP_PATH/Contents/MacOS"
APP_FRAMEWORKS_DIR="$APP_PATH/Contents/Frameworks"
MANIFEST_PATH="$APP_FRAMEWORKS_DIR/$MANIFEST_NAME"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

if [[ ! -d "$APP_MACOS_DIR" ]]; then
  echo "App bundle is missing Contents/MacOS: $APP_PATH" >&2
  exit 1
fi

if [[ ! -d "$APP_FRAMEWORKS_DIR" ]]; then
  echo "App bundle is missing Contents/Frameworks: $APP_PATH" >&2
  exit 1
fi

if [[ ! -d "$DIST_DIR" ]]; then
  echo "Built backend bundle not found: $DIST_DIR" >&2
  echo "Run 'make package' first." >&2
  exit 1
fi

resolve_backend_executable() {
  local candidate
  for candidate in "$DIST_DIR/aw-server" "$DIST_DIR/trustme-api"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "Expected backend executable not found under $DIST_DIR (looked for aw-server and trustme-api)" >&2
  return 1
}

BACKEND_EXECUTABLE="$(resolve_backend_executable)"

if pgrep -af "$APP_MACOS_DIR/" >/dev/null 2>&1; then
  echo "The installed trust-me app appears to be running. Quit it before syncing." >&2
  pgrep -af "$APP_MACOS_DIR/" || true
  exit 1
fi

TMP_MANIFEST="$(mktemp)"
trap 'rm -f "$TMP_MANIFEST"' EXIT

if [[ -f "$MANIFEST_PATH" ]]; then
  while IFS= read -r relpath; do
    [[ -n "$relpath" ]] || continue
    rm -rf "$APP_PATH/Contents/$relpath"
  done < "$MANIFEST_PATH"
fi

while IFS= read -r source_path; do
  name="$(basename "$source_path")"
  [[ "$name" == "aw-server" || "$name" == "trustme-api" ]] && continue
  rsync -a "$source_path" "$APP_FRAMEWORKS_DIR/"
  printf '%s\n' "Frameworks/$name" >> "$TMP_MANIFEST"
done < <(find "$DIST_DIR" -mindepth 1 -maxdepth 1 | sort)

install -m 755 "$BACKEND_EXECUTABLE" "$APP_MACOS_DIR/aw-server"
printf '%s\n' "MacOS/aw-server" >> "$TMP_MANIFEST"
mv "$TMP_MANIFEST" "$MANIFEST_PATH"

echo "Synced browser backend into $APP_PATH"
echo "Managed files recorded in $MANIFEST_PATH"
