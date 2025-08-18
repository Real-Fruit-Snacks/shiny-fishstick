#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)"
"${DIR}/.venv/bin/python" -m delta_vision "$@"
