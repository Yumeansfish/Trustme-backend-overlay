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
  # Keep this lane focused on the browser backend path while still exercising
  # the legacy aw_server compatibility imports and contract generator.
  python -m pip install --upgrade pip >/dev/null
  python -m pip install \
    -e "${ROOT_DIR}/trustme-api" \
    pytest \
    pytest-benchmark >/dev/null
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${BOOTSTRAP_STAMP}"
fi

cd "${ROOT_DIR}"

python -m pytest \
  -o addopts='' \
  trustme-api/tests/test_dashboard_details.py \
  trustme-api/tests/test_dashboard_domain_service.py \
  trustme-api/tests/test_dashboard_api_facade.py \
  trustme-api/tests/test_dashboard_dto.py \
  trustme-api/tests/test_dashboard_contract_codegen.py \
  trustme-api/tests/test_summary_snapshot_response.py \
  trustme-api/tests/test_dashboard_routes.py \
  trustme-api/tests/test_checkins.py \
  trustme-api/tests/test_server.py \
  trustme-api/tests/test_trustme_api.py \
  "$@"
