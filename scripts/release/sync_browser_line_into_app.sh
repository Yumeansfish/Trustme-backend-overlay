#!/usr/bin/env bash

set -euo pipefail

BUNDLE_DIR="${1:-}"
APP_PATH="${2:-/Applications/trust-me.app}"
MANIFEST_NAME=".trustme-browser-line-manifest"

if [[ -z "$BUNDLE_DIR" ]]; then
  echo "Usage: $0 /path/to/browser-line-bundle [/Applications/trust-me.app]" >&2
  exit 1
fi

BUNDLE_DIR="${BUNDLE_DIR%/}"
APP_PATH="${APP_PATH%/}"
APP_MACOS_DIR="$APP_PATH/Contents/MacOS"
APP_FRAMEWORKS_DIR="$APP_PATH/Contents/Frameworks"
MANIFEST_PATH="$APP_FRAMEWORKS_DIR/$MANIFEST_NAME"

COMPONENTS=(
  aw-server
  aw-watcher-afk
  aw-watcher-window
  aw-watcher-input
)

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "Bundle directory not found: $BUNDLE_DIR" >&2
  exit 1
fi

if [[ ! -x "$BUNDLE_DIR/aw-qt" ]]; then
  echo "Bundle root is missing executable aw-qt: $BUNDLE_DIR/aw-qt" >&2
  exit 1
fi

if [[ ! -d "$APP_PATH" || ! -d "$APP_MACOS_DIR" || ! -d "$APP_FRAMEWORKS_DIR" ]]; then
  echo "Target app bundle is incomplete: $APP_PATH" >&2
  exit 1
fi

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

record_manifest() {
  printf '%s\n' "$1" >> "$TMP_MANIFEST"
}

sync_framework_entries() {
  local source_root="$1"
  local executable_name="$2"
  local entry
  while IFS= read -r entry; do
    local name
    name="$(basename "$entry")"
    if [[ "$name" == "$executable_name" ]]; then
      continue
    fi
    rsync -a "$entry" "$APP_FRAMEWORKS_DIR/"
    record_manifest "Frameworks/$name"
  done < <(find "$source_root" -mindepth 1 -maxdepth 1 | sort)
}

install -m 755 "$BUNDLE_DIR/aw-qt" "$APP_MACOS_DIR/aw-qt"
record_manifest "MacOS/aw-qt"

while IFS= read -r entry; do
  name="$(basename "$entry")"
  case "$name" in
    aw-qt|aw-server|aw-watcher-afk|aw-watcher-window|aw-watcher-input)
      continue
      ;;
  esac
  rsync -a "$entry" "$APP_FRAMEWORKS_DIR/"
  record_manifest "Frameworks/$name"
done < <(find "$BUNDLE_DIR" -mindepth 1 -maxdepth 1 | sort)

for component in "${COMPONENTS[@]}"; do
  component_dir="$BUNDLE_DIR/$component"
  executable_path="$component_dir/$component"

  if [[ ! -d "$component_dir" ]]; then
    echo "Missing packaged component directory: $component_dir" >&2
    exit 1
  fi

  if [[ ! -x "$executable_path" ]]; then
    echo "Missing packaged component executable: $executable_path" >&2
    exit 1
  fi

  install -m 755 "$executable_path" "$APP_MACOS_DIR/$component"
  record_manifest "MacOS/$component"
  sync_framework_entries "$component_dir" "$component"
done

sort -u "$TMP_MANIFEST" -o "$TMP_MANIFEST"
mv "$TMP_MANIFEST" "$MANIFEST_PATH"

echo "Synced browser-line bundle into $APP_PATH"
echo "Managed files recorded in $MANIFEST_PATH"
