#!/bin/bash
set -e

log() {
    echo "[POSVENDELO] $*"
}

log "Deteniendo servicios..."

systemctl stop titan-pos.service 2>/dev/null || true
systemctl disable titan-pos.service 2>/dev/null || true

log "Servicios detenidos."
log "Los datos se conservan en /opt/titan-pos/ — elimínalos manualmente si no los necesitas."
