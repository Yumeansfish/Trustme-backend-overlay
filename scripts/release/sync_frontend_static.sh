#!/usr/bin/env bash
set -euo pipefail

FRONTEND_DIR="${1:-${FRONTEND_DIR:-../frontend}}"
STATIC_DIR="${2:-aw-server/aw_server/static}"

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Frontend directory not found: $FRONTEND_DIR" >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_DIR/package.json" ]]; then
  echo "package.json not found in frontend directory: $FRONTEND_DIR" >&2
  exit 1
fi

echo "Building frontend from $FRONTEND_DIR"
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run build

mkdir -p "$STATIC_DIR"
rsync -a --delete "$FRONTEND_DIR/dist/" "$STATIC_DIR/"
