#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# install package dependencies
# required for Pillow
sudo apt install libopenblas0 libjpeg-dev zlib1g-dev libfreetype6-dev

if [ ! -d ./.venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
