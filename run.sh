#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ ! -d ./.venv ]; then
    ./setup.sh
fi
source .venv/bin/activate
python3 monitor.py "$@"
