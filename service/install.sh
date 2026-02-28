#!/bin/bash
set -euo pipefail

SERVICE_NAME="infoink.service"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/infoink.service.template"
TARGET_FILE="${SYSTEMD_DIR}/${SERVICE_NAME}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root: sudo ${0} [run_user]"
    exit 1
fi

RUN_USER="${1:-${SUDO_USER:-root}}"

if [ ! -f "${TEMPLATE_FILE}" ]; then
    echo "Missing template: ${TEMPLATE_FILE}"
    exit 1
fi

sed \
    -e "s|__RUN_USER__|${RUN_USER}|g" \
    -e "s|__WORKDIR__|${PROJECT_DIR}|g" \
    "${TEMPLATE_FILE}" > "${TARGET_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "Installed ${SERVICE_NAME} for user '${RUN_USER}'."
echo "Check status with: systemctl status ${SERVICE_NAME}"
