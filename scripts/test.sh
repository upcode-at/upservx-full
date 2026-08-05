#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
quality_venv="$(mktemp -d /tmp/upservx-quality.XXXXXX)"
quality_python="$quality_venv/bin/python"
trap 'rm -rf "$quality_venv"' EXIT

cd "$repository_root"

command -v python3 >/dev/null
command -v npm >/dev/null
command -v docker >/dev/null
docker compose version >/dev/null

python3 -m venv "$quality_venv"
"$quality_python" -m pip install --upgrade pip
"$quality_python" -m pip install \
  -r upservx-service/requirements.lock \
  -r upservx-cli/requirements.lock \
  flake8==7.3.0

export PYTHONPATH="$repository_root/upservx-service:$repository_root/upservx-cli"
export PYTHONPYCACHEPREFIX="$quality_venv/pycache"

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
  --count --select=E9,F63,F7,F82 --show-source --statistics

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
