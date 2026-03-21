#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-dashboard-tests"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BOOTSTRAP_STAMP="${VENV_DIR}/.dashboard-test-bootstrap"

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
  python -m pip install --upgrade pip >/dev/null
  python -m pip install \
    -e "${ROOT_DIR}/aw-core" \
    -e "${ROOT_DIR}/aw-client" \
    -e "${ROOT_DIR}/aw-server" \
    pytest >/dev/null
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${BOOTSTRAP_STAMP}"
fi

cd "${ROOT_DIR}"

python -m pytest \
  --noconftest \
  -o addopts='' \
  aw-server/tests/test_dashboard_details.py \
  aw-server/tests/test_dashboard_domain_service.py \
  aw-server/tests/test_dashboard_api_facade.py \
  aw-server/tests/test_dashboard_dto.py \
  aw-server/tests/test_dashboard_contract_codegen.py \
  aw-server/tests/test_summary_snapshot_response.py \
  aw-server/tests/test_dashboard_routes.py \
  aw-server/tests/test_checkins.py \
  "$@"
