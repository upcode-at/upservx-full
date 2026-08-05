#!/usr/bin/env bash
# Compatibility entry point. Updates are performed by an independent root unit.
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  printf 'This command must be run as root.\n' >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  printf 'Usage: sudo update.sh VERSION\n' >&2
  printf 'Stage the signed artifact under /var/lib/upservx/updates/VERSION first.\n' >&2
  exit 2
fi
exec /usr/local/libexec/upservx-updater apply "$1"
