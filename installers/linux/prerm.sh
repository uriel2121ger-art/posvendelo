#!/bin/bash
set -e

log() {
    echo "[POSVENDELO] $*"
}

log "Deteniendo servicios..."

systemctl stop posvendelo.service 2>/dev/null || true
systemctl disable posvendelo.service 2>/dev/null || true

log "Servicios detenidos."
log "Los datos se conservan en /opt/posvendelo/ — elimínalos manualmente si no los necesitas."
