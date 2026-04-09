#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-dashboard-tests"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BOOTSTRAP_STAMP="${VENV_DIR}/.browser-backend-test-bootstrap"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if [ ! -f "${BOOTSTRAP_STAMP}" ] || [ "${FORCE_BOOTSTRAP:-0}" = "1" ]; then
  # Keep this lane focused on the dashboard/browser overlay while still
  # exercising the repo-level package boundary and contract generator.
  python -m pip install --upgrade pip >/dev/null
  python -m pip install \
    -e "${ROOT_DIR}" \
    pytest \
    pytest-benchmark >/dev/null
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${BOOTSTRAP_STAMP}"
fi

cd "${ROOT_DIR}"

python -m pytest \
  -o addopts='' \
  tests/test_backend_overlay_package.py \
  tests/test_dashboard_domain_service.py \
  tests/test_dashboard_scope_service.py \
  tests/test_dashboard_repository.py \
  tests/test_dashboard_service.py \
  tests/test_dashboard_details_service.py \
  tests/test_dashboard_checkins_service.py \
  tests/test_dashboard_summary.py \
  tests/test_checkins.py \
  tests/test_checkins_path_resolution.py \
  "$@"

python scripts/contracts/export_dashboard_contract_ts.py >/dev/null
