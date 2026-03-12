#!/usr/bin/env bash
# Reinstalación limpia del nodo POSVENDELO en esta PC.
# Solo toca el directorio de instalación del nodo (~/.titanpos por defecto).
# No modifica el repositorio ni el entorno de desarrollo.
set -euo pipefail

INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
INSTALL_DIR="$HOME/.titanpos"

# Extraer --dir de los argumentos para desinstalar en el mismo sitio
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      ARGS+=("$1" "$2")
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

echo "[POSVENDELO] Desinstalando nodo en: $INSTALL_DIR"
bash "$INSTALLER_DIR/uninstall-titan.sh" "$INSTALL_DIR"

echo "[POSVENDELO] Instalando de nuevo..."
bash "$INSTALLER_DIR/install-titan.sh" "${ARGS[@]}"

echo "[POSVENDELO] Reinstalación terminada. Revisa $INSTALL_DIR/INSTALL_SUMMARY.txt"
