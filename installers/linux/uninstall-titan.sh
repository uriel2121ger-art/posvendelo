#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${1:-$HOME/.titanpos}"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "[TITAN] No existe $INSTALL_DIR"
  exit 0
fi

cd "$INSTALL_DIR"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down -v || true
fi

rm -rf "$INSTALL_DIR"
echo "[TITAN] Instalacion eliminada: $INSTALL_DIR"
