#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

check_pi_bus_support() {
    if [ ! -f /proc/device-tree/model ]; then
        return
    fi

    local model
    model="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)"
    if [[ "${model}" != *"Raspberry Pi"* ]]; then
        return
    fi

    local missing=()

    if [ ! -e /dev/i2c-1 ]; then
        missing+=("I2C")
    fi

    if [ ! -e /dev/spidev0.0 ] && [ ! -e /dev/spidev0.1 ]; then
        missing+=("SPI")
    fi

    if [ "${#missing[@]}" -gt 0 ]; then
        echo "Missing required Raspberry Pi interfaces: ${missing[*]}."
        echo "Enable them first, for example with: sudo raspi-config"
        echo "Then go to Interface Options and enable I2C and SPI, reboot, and rerun ./setup.sh."
        exit 1
    fi
}

check_pi_bus_support

# install package dependencies
# required for Pillow and lgpio
sudo apt install -y libopenblas0 libjpeg-dev zlib1g-dev libfreetype-dev python3-venv python3-pip swig liblgpio-dev

if [ ! -d ./.venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
