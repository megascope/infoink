#!/bin/bash
set -euo pipefail

if [ ! -d ./.venv ]; then
    ./setup.sh
fi
source .venv/bin/activate
python3 monitor.py "$@"
