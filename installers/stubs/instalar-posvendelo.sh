#!/usr/bin/env bash
# PosVendelo — Instalador ligero (Bash)
# Descarga e instala el cajero o el owner desde el manifiesto publico.
# Uso: ./instalar-posvendelo.sh [--owner]

set -euo pipefail

# ─── Banner ───────────────────────────────────────────────────────────────────
printf '\n'
printf '╔════════════════════════════════════════╗\n'
printf '║  PosVendelo — Instalador ligero      ║\n'
printf '╚════════════════════════════════════════╝\n'
printf '\n'

# ─── Detectar tipo por nombre del script ──────────────────────────────────────
SCRIPT_NAME="$(basename -- "$0")"
if [[ "$SCRIPT_NAME" == *"owner"* ]]; then
  APP_TYPE="owner"
else
  APP_TYPE="cajero"
fi

# ─── Parsear argumentos ───────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --owner)
      APP_TYPE="owner"
      ;;
    --help | -h)
      printf 'Uso: %s [--owner]\n' "$SCRIPT_NAME"
      printf '  Sin argumentos → instala el cajero POS\n'
      printf '  --owner        → instala la app del propietario\n'
      exit 0
      ;;
  esac
done

printf 'Tipo de aplicacion: %s\n\n' "$APP_TYPE"

# ─── Seleccionar modo de instalacion (solo cajero) ──────────────────────────
INSTALL_MODE="principal"
if [[ "$APP_TYPE" == "cajero" ]]; then
  printf '¿Como se usara esta PC?\n'
  printf '  1) PC Principal — instala servidor y base de datos\n'
  printf '  2) Caja secundaria — se conecta a otro servidor en la red\n\n'
  read -rp 'Elige [1/2] (default 1): ' INSTALL_CHOICE
  if [[ "${INSTALL_CHOICE:-1}" == "2" ]]; then
    INSTALL_MODE="client"
    printf '\nModo: Caja secundaria (no se instalara base de datos)\n\n'
  else
    printf '\nModo: PC Principal\n\n'
  fi
fi

# ─── Verificar dependencias ───────────────────────────────────────────────────
check_dep() {
  if ! command -v "$1" > /dev/null 2>&1; then
    printf 'Error: "%s" no esta instalado. Instalalo antes de continuar.\n' "$1" >&2
    exit 1
  fi
}

check_dep bash
check_dep curl
check_dep python3

# ─── URL del manifiesto ───────────────────────────────────────────────────────
MANIFEST_URL="https://posvendelo.com/api/v1/releases/manifest?os=linux"

# ─── Descargar manifiesto ─────────────────────────────────────────────────────
printf 'Consultando manifiesto de versiones...\n'
MANIFEST_JSON="$(curl -sSf --max-time 30 "$MANIFEST_URL")" || {
  printf 'Error: no se pudo conectar con el servidor de versiones.\n' >&2
  exit 1
}

if [[ -z "$MANIFEST_JSON" ]]; then
  printf 'Error: no se pudo obtener el manifiesto desde %s\n' "$MANIFEST_URL" >&2
  exit 1
fi

# ─── Extraer URL de descarga y version ───────────────────────────────────────
PARSED="$(printf '%s' "$MANIFEST_JSON" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)['data']['artifacts']
    key = 'owner_app' if sys.argv[1] == 'owner' else 'app'
    a = d[key]
    # Output two lines: URL then version (no shell metacharacters)
    print(a['target_ref'])
    print(a['version'])
except Exception as e:
    print('ERROR: ' + str(e), file=sys.stderr)
    sys.exit(1)
" "$APP_TYPE")" || { printf 'Error al parsear manifiesto.\n' >&2; exit 1; }

# Read first and second line using bash builtins (no sed dependency).
{ IFS= read -r DOWNLOAD_URL; IFS= read -r VERSION; } <<< "$PARSED"

if [[ -z "$DOWNLOAD_URL" ]]; then
  printf 'Error: no se encontro URL de descarga en el manifiesto.\n' >&2
  exit 1
fi

printf 'Version disponible: %s\n' "$VERSION"
printf 'URL de descarga: %s\n\n' "$DOWNLOAD_URL"

# ─── Archivo temporal ─────────────────────────────────────────────────────────
TMPFILE_BASE="$(mktemp /tmp/posvendelo-installer-XXXXXX)"
TMPFILE="$TMPFILE_BASE"
cleanup() { rm -f -- "$TMPFILE_BASE" "$TMPFILE"; }
trap cleanup EXIT

# Obtener extension del nombre de archivo en la URL
URL_FILENAME="$(basename -- "${DOWNLOAD_URL%%\?*}")"
if [[ "$URL_FILENAME" == *.deb ]]; then
  TMPFILE="${TMPFILE_BASE}.deb"
elif [[ "$URL_FILENAME" == *.AppImage ]]; then
  TMPFILE="${TMPFILE_BASE}.AppImage"
fi

# ─── Descargar instalador ─────────────────────────────────────────────────────
printf 'Descargando PosVendelo %s (%s)...\n' "$VERSION" "$APP_TYPE"
curl --progress-bar -L --max-time 600 -o "$TMPFILE" "$DOWNLOAD_URL"
printf '\n'

# ─── Instalar segun tipo de archivo ──────────────────────────────────────────
install_file() {
  local file="$1"

  if [[ "$file" == *.deb ]]; then
    printf 'Instalando paquete .deb (modo: %s)...\n' "$INSTALL_MODE"
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
      INSTALL_MODE="$INSTALL_MODE" dpkg -i -- "$file"
    elif command -v pkexec > /dev/null 2>&1; then
      pkexec env INSTALL_MODE="$INSTALL_MODE" dpkg -i -- "$file"
    else
      sudo INSTALL_MODE="$INSTALL_MODE" dpkg -i -- "$file"
    fi
    printf '\nInstalacion completada. Inicia PosVendelo desde el menu de aplicaciones.\n'

  elif [[ "$file" == *.AppImage ]]; then
    printf 'Ejecutando AppImage...\n'
    chmod +x -- "$file"
    exec "$file"

  else
    # Intentar dpkg primero, si falla ejecutar directamente
    printf 'Tipo de archivo desconocido, intentando instalar con dpkg...\n'
    if command -v dpkg > /dev/null 2>&1; then
      if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        INSTALL_MODE="$INSTALL_MODE" dpkg -i -- "$file" 2>/dev/null && return
      elif command -v pkexec > /dev/null 2>&1; then
        pkexec env INSTALL_MODE="$INSTALL_MODE" dpkg -i -- "$file" 2>/dev/null && return
      else
        sudo INSTALL_MODE="$INSTALL_MODE" dpkg -i -- "$file" 2>/dev/null && return
      fi
    fi
    printf 'No se pudo instalar con dpkg, ejecutando directamente...\n'
    chmod +x -- "$file"
    exec "$file"
  fi
}

install_file "$TMPFILE"
