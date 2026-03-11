#!/usr/bin/env bash
# Actualizar el backend del nodo TITAN POS (descarga nueva imagen y reinicia).
# Uso: ./actualizar.sh [--dir INSTALL_DIR]
# Por defecto INSTALL_DIR=$HOME/.titanpos

set -euo pipefail

INSTALL_DIR="${HOME:-/root}/.titanpos"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    -h|--help)
      echo "Uso: $0 [--dir INSTALL_DIR]"
      echo "  Actualiza el backend del nodo: pull de la imagen y reinicio del contenedor."
      echo "  Por defecto INSTALL_DIR=$HOME/.titanpos"
      exit 0
      ;;
    *)
      echo "Opción desconocida: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "[TITAN] No existe el directorio de instalación: $INSTALL_DIR" >&2
  exit 1
fi

if [[ ! -f "$INSTALL_DIR/docker-compose.yml" ]] || [[ ! -f "$INSTALL_DIR/.env" ]]; then
  echo "[TITAN] No parece una instalación TITAN POS (falta docker-compose.yml o .env)." >&2
  exit 1
fi

cd "$INSTALL_DIR"

run_compose() {
  env -i \
    PATH="${PATH:-}" \
    HOME="${HOME:-/root}" \
    USER="${USER:-}" \
    docker compose --env-file .env "$@"
}

echo "[TITAN] Descargando nueva imagen del backend..."
if ! run_compose pull api; then
  echo "[TITAN] Si la imagen es privada (GHCR), ejecuta antes: docker login ghcr.io" >&2
  exit 1
fi

echo "[TITAN] Reiniciando el backend..."
run_compose up -d api

echo "[TITAN] Estado del stack:"
run_compose ps

LOCAL_API_PORT="$(grep -E '^LOCAL_API_PORT=' .env 2>/dev/null | cut -d= -f2 || echo "8000")"
echo ""
echo "[TITAN] Actualización aplicada. Health: http://127.0.0.1:${LOCAL_API_PORT}/health"
