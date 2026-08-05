#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
quality_venv="$(mktemp -d /tmp/upservx-quality.XXXXXX)"
quality_python="$quality_venv/bin/python"
test_python="${UPSERVX_TEST_PYTHON:-python3.11}"
trap 'rm -rf "$quality_venv"' EXIT

cd "$repository_root"

if ! command -v "$test_python" >/dev/null; then
  echo "Python 3.11 is required (or set UPSERVX_TEST_PYTHON explicitly)." >&2
  exit 127
fi
command -v npm >/dev/null
command -v docker >/dev/null
docker compose version >/dev/null

"$test_python" -m venv "$quality_venv"
"$quality_python" -m pip install \
  -r upservx-service/requirements.lock \
  -r upservx-cli/requirements.lock \
  -r requirements-quality.lock

export PYTHONPATH="$repository_root/upservx-service:$repository_root/upservx-cli"
export PYTHONPYCACHEPREFIX="$quality_venv/pycache"
export UPSERVX_CONFIG_DIR="$quality_venv/config"
export UPSERVX_STATE_DIR="$quality_venv/state"
export UPSERVX_JOB_DB="$quality_venv/config/jobs.db"
export UPSERVX_LOG_FILE="$quality_venv/upservx.log"
export UPSERVX_COMPOSE_DIR="$quality_venv/compose"
export UPSERVX_APP_DATA_DIR="$quality_venv/app-data"
export UPSERVX_APP_STORE_DIR="$repository_root/app-store-templates"
export UPSERVX_APP_SCHEMA="$repository_root/app-store-templates/app.schema.json"

"$quality_python" -m compileall -q \
  upservx-service/api \
  upservx-service/handlers \
  upservx-service/lib \
  upservx-service/tests \
  upservx-cli/cli \
  upservx-cli/tests \
  tools

"$quality_python" -m flake8 \
  upservx-service/api \
  upservx-service/handlers \
  upservx-service/lib \
  upservx-service/tests \
  upservx-cli/cli \
  upservx-cli/tests \
  tools \
  --jobs=1 --count --select=E9,F63,F7,F82 --show-source --statistics

"$quality_python" -m pytest upservx-service/tests
"$quality_python" -m pytest upservx-cli/tests
"$quality_python" tools/generate_api_contract.py --check
"$quality_python" tools/validate_app_store.py

find . \
  -path ./.git -prune -o \
  -path ./upservx/node_modules -prune -o \
  -path ./upservx/public/novnc -prune -o \
  -type f -name '*.sh' -print0 \
  | xargs -0 -r bash -n

npm --prefix upservx ci
npm --prefix upservx run lint
npm --prefix upservx run build

echo "All local quality gates passed."
