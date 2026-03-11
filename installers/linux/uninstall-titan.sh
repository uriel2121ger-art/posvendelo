#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${1:-$HOME/.titanpos}"

# Quitar icono del escritorio y entrada del menú creados por el instalador
rm -f "$HOME/Desktop/POSVENDELO.desktop" 2>/dev/null || true
rm -f "$HOME/.local/share/applications/posvendelo-nodo.desktop" 2>/dev/null || true

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "[POSVENDELO] No existe $INSTALL_DIR"
  exit 0
fi

cd "$INSTALL_DIR"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down -v || true
fi

rm -rf "$INSTALL_DIR"
echo "[POSVENDELO] Instalacion eliminada: $INSTALL_DIR"
