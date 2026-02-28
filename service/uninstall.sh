#!/bin/bash
set -euo pipefail

SERVICE_NAME="infoink.service"
TARGET_FILE="/etc/systemd/system/${SERVICE_NAME}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root: sudo ${0}"
    exit 1
fi

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}"; then
    systemctl disable --now "${SERVICE_NAME}" || true
fi

if [ -f "${TARGET_FILE}" ]; then
    rm -f "${TARGET_FILE}"
fi

systemctl daemon-reload
systemctl reset-failed || true

echo "Uninstalled ${SERVICE_NAME}."
