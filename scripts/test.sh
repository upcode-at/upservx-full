#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
quality_venv="$(mktemp -d /tmp/upcode-harbor-quality.XXXXXX)"
quality_python="$quality_venv/bin/python"
test_python="${UPCODE_HARBOR_TEST_PYTHON:-python3.11}"
trap 'rm -rf "$quality_venv"' EXIT

cd "$repository_root"

if ! command -v "$test_python" >/dev/null; then
  echo "Python 3.11 is required (or set UPCODE_HARBOR_TEST_PYTHON explicitly)." >&2
  exit 127
fi
command -v npm >/dev/null
command -v docker >/dev/null
docker compose version >/dev/null

"$test_python" -m venv "$quality_venv"
"$quality_python" -m pip install \
  -r upcode-harbor-service/requirements.lock \
  -r upcode-harbor-cli/requirements.lock \
  -r requirements-quality.lock

export PYTHONPATH="$repository_root/upcode-harbor-service:$repository_root/upcode-harbor-cli"
export PYTHONPYCACHEPREFIX="$quality_venv/pycache"
export UPCODE_HARBOR_CONFIG_DIR="$quality_venv/config"
export UPCODE_HARBOR_STATE_DIR="$quality_venv/state"
export UPCODE_HARBOR_JOB_DB="$quality_venv/config/jobs.db"
export UPCODE_HARBOR_LOG_FILE="$quality_venv/upcode-harbor.log"
export UPCODE_HARBOR_COMPOSE_DIR="$quality_venv/compose"
export UPCODE_HARBOR_APP_DATA_DIR="$quality_venv/app-data"
export UPCODE_HARBOR_APP_STORE_DIR="$repository_root/app-store-templates"
export UPCODE_HARBOR_APP_SCHEMA="$repository_root/app-store-templates/app.schema.json"

"$quality_python" -m compileall -q \
  upcode-harbor-service/api \
  upcode-harbor-service/handlers \
  upcode-harbor-service/lib \
  upcode-harbor-service/tests \
  upcode-harbor-cli/cli \
  upcode-harbor-cli/tests \
  tools

"$quality_python" -m flake8 \
  upcode-harbor-service/api \
  upcode-harbor-service/handlers \
  upcode-harbor-service/lib \
  upcode-harbor-service/tests \
  upcode-harbor-cli/cli \
  upcode-harbor-cli/tests \
  tools \
  --jobs=1 --count --select=E9,F63,F7,F82 --show-source --statistics

"$quality_python" -m pytest upcode-harbor-service/tests
"$quality_python" -m pytest upcode-harbor-cli/tests
"$quality_python" tools/generate_api_contract.py --check
"$quality_python" tools/validate_app_store.py

find . \
  -path ./.git -prune -o \
  -path ./upcode-harbor/node_modules -prune -o \
  -path ./upcode-harbor/public/novnc -prune -o \
  -path ./upcode-harbor-service/ssh_keys -prune -o \
  -path ./upcode-harbor-service/authorized_keys -prune -o \
  -type f -name '*.sh' -print0 \
  | xargs -0 -r bash -n

npm --prefix upcode-harbor ci
npm --prefix upcode-harbor run lint
npm --prefix upcode-harbor run build

echo "All local quality gates passed."
