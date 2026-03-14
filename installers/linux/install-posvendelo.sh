#!/usr/bin/env bash
set -euo pipefail

# URL del nodo central por defecto (homelab/posvendelo.com). El usuario no tiene que escribir nada.
DEFAULT_CP_URL="${POSVENDELO_CP_URL:-https://posvendelo.com}"

usage() {
  echo "Uso: bash install-posvendelo.sh [--cp-url URL] [--install-token TOKEN] [--branch-name NOMBRE] [--cloud-email CORREO --cloud-password PASS --tenant-name EMPRESA --existing-cloud] [--dir DIR] [--api-port PUERTO] [--db-port PUERTO] [--backend-image IMAGEN]"
  echo "  Si no pasas --cp-url ni --install-token, se usa $DEFAULT_CP_URL y el token se obtiene automáticamente (pre-registro por hardware)."
}

CP_URL=""
INSTALL_TOKEN=""
BRANCH_NAME=""
INSTALL_DIR="$HOME/.posvendelo"
INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
APP_VERSION="1.0.0"
POS_VERSION="2.0.0"
LOCAL_API_PORT=""
LOCAL_POSTGRES_PORT=""
BOOTSTRAP_JSON=""
REGISTER_JSON=""
AGENT_JSON_PATH=""
CURRENT_STEP="inicio"
CLOUD_EMAIL=""
CLOUD_PASSWORD=""
TENANT_NAME=""
EXISTING_CLOUD_ACCOUNT="false"
BACKEND_IMAGE_OVERRIDE=""

report_status() {
  local status="$1"
  local error_msg="${2:-}"
  local report_json
  report_json="$(mktemp)"
  INSTALL_TOKEN="$INSTALL_TOKEN" STATUS="$status" ERROR_MSG="$error_msg" APP_VERSION="$APP_VERSION" POS_VERSION="$POS_VERSION" python3 - <<'PY' > "$report_json"
import json
import os

payload = {
    "install_token": os.environ["INSTALL_TOKEN"],
    "status": os.environ["STATUS"],
    "error": os.environ.get("ERROR_MSG") or None,
    "app_version": os.environ.get("APP_VERSION") or None,
    "pos_version": os.environ.get("POS_VERSION") or None,
}
print(json.dumps(payload))
PY
  curl -fsSL -X POST \
    -H "Content-Type: application/json" \
    --data @"$report_json" \
    "${CP_URL%/}/api/v1/branches/install-report" >/dev/null || true
  rm -f "$report_json"
}

cleanup() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && -n "$CP_URL" && -n "$INSTALL_TOKEN" ]]; then
    report_status "error" "${CURRENT_STEP:-instalacion fallida}"
  fi
  rm -f "${BOOTSTRAP_JSON:-}" "${REGISTER_JSON:-}"
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cp-url)
      CP_URL="$2"
      shift 2
      ;;
    --install-token)
      INSTALL_TOKEN="$2"
      shift 2
      ;;
    --branch-name)
      BRANCH_NAME="$2"
      shift 2
      ;;
    --cloud-email)
      CLOUD_EMAIL="$2"
      shift 2
      ;;
    --cloud-password)
      CLOUD_PASSWORD="$2"
      shift 2
      ;;
    --tenant-name)
      TENANT_NAME="$2"
      shift 2
      ;;
    --existing-cloud)
      EXISTING_CLOUD_ACCOUNT="true"
      shift 1
      ;;
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --api-port)
      LOCAL_API_PORT="$2"
      shift 2
      ;;
    --db-port)
      LOCAL_POSTGRES_PORT="$2"
      shift 2
      ;;
    --backend-image)
      BACKEND_IMAGE_OVERRIDE="$2"
      shift 2
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CP_URL" ]]; then
  CP_URL="$DEFAULT_CP_URL"
  echo "[POSVENDELO] Usando servidor central: $CP_URL (token se obtendrá automáticamente)"
fi

bootstrap_cloud_install_token() {
  local auth_json auth_response auth_token branch_json branch_response generated_token

  if [[ -z "$CLOUD_EMAIL" ]]; then
    read -r -p "Correo cloud: " CLOUD_EMAIL
  fi
  if [[ -z "$CLOUD_PASSWORD" ]]; then
    read -rs -p "Contraseña cloud: " CLOUD_PASSWORD
    echo
  fi
  if [[ "$EXISTING_CLOUD_ACCOUNT" != "true" && -z "$TENANT_NAME" ]]; then
    read -r -p "Empresa o negocio: " TENANT_NAME
  fi
  if [[ -z "$BRANCH_NAME" ]]; then
    read -r -p "Nombre de la sucursal: " BRANCH_NAME
  fi

  auth_json="$(mktemp)"
  if [[ "$EXISTING_CLOUD_ACCOUNT" == "true" ]]; then
    CLOUD_EMAIL="$CLOUD_EMAIL" CLOUD_PASSWORD="$CLOUD_PASSWORD" python3 - <<'PY' > "$auth_json"
import json
import os
print(json.dumps({"email": os.environ["CLOUD_EMAIL"], "password": os.environ["CLOUD_PASSWORD"]}))
PY
    auth_response="$(curl -fsSL -X POST -H "Content-Type: application/json" --data @"$auth_json" "${CP_URL%/}/api/v1/cloud/login")"
  else
    CLOUD_EMAIL="$CLOUD_EMAIL" CLOUD_PASSWORD="$CLOUD_PASSWORD" TENANT_NAME="$TENANT_NAME" BRANCH_NAME="$BRANCH_NAME" python3 - <<'PY' > "$auth_json"
import json
import os
print(json.dumps({
    "email": os.environ["CLOUD_EMAIL"],
    "password": os.environ["CLOUD_PASSWORD"],
    "business_name": os.environ["TENANT_NAME"],
    "branch_name": os.environ["BRANCH_NAME"],
}))
PY
    auth_response="$(curl -fsSL -X POST -H "Content-Type: application/json" --data @"$auth_json" "${CP_URL%/}/api/v1/cloud/register")"
    generated_token="$(AUTH_RESPONSE="$auth_response" python3 - <<'PY'
import json
import os
body = json.loads(os.environ["AUTH_RESPONSE"])
print((body.get("data") or {}).get("install_token") or "")
PY
)"
    if [[ -n "$generated_token" ]]; then
      INSTALL_TOKEN="$generated_token"
      rm -f "$auth_json"
      return
    fi
  fi

  auth_token="$(AUTH_RESPONSE="$auth_response" python3 - <<'PY'
import json
import os
body = json.loads(os.environ["AUTH_RESPONSE"])
print((body.get("data") or {}).get("session_token") or "")
PY
)"
  if [[ -z "$auth_token" ]]; then
    echo "[POSVENDELO] No se pudo obtener sesión cloud."
    rm -f "$auth_json"
    exit 1
  fi

  branch_json="$(mktemp)"
  BRANCH_NAME="$BRANCH_NAME" python3 - <<'PY' > "$branch_json"
import json
import os
print(json.dumps({"branch_name": os.environ["BRANCH_NAME"] or "Sucursal Principal"}))
PY
  branch_response="$(curl -fsSL -X POST -H "Content-Type: application/json" -H "Authorization: Bearer ${auth_token}" --data @"$branch_json" "${CP_URL%/}/api/v1/cloud/register-branch")"
  INSTALL_TOKEN="$(BRANCH_RESPONSE="$branch_response" python3 - <<'PY'
import json
import os
body = json.loads(os.environ["BRANCH_RESPONSE"])
print((body.get("data") or {}).get("install_token") or "")
PY
)"
  rm -f "$auth_json" "$branch_json"
  if [[ -z "$INSTALL_TOKEN" ]]; then
    echo "[POSVENDELO] No se pudo obtener install_token desde cloud/register-branch."
    exit 1
  fi
}

pick_port() {
  local preferred="$1"
  python3 - "$preferred" <<'PY'
import socket
import sys

start = int(sys.argv[1])
for port in range(start, start + 200):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            print(port)
            raise SystemExit(0)
raise SystemExit(1)
PY
}

collect_hw_info() {
  local board_serial board_name cpu_model mac_primary disk_serial

  board_serial="$(cat /sys/class/dmi/id/board_serial 2>/dev/null || echo '')"
  board_name="$(cat /sys/class/dmi/id/board_name 2>/dev/null || echo '')"
  cpu_model="$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo '')"

  # Primary MAC: first physical NIC (not lo, docker, veth, br-)
  mac_primary="$(ip link show 2>/dev/null \
    | grep -B1 'link/ether' \
    | grep -v 'docker\|veth\|br-\|virbr' \
    | grep 'link/ether' \
    | head -n1 \
    | awk '{print $2}' || echo '')"
  if [[ -z "$mac_primary" ]]; then
    mac_primary="$(cat /sys/class/net/e*/address 2>/dev/null | head -n1 || echo '')"
  fi

  # Disk serial: first real disk (nvme or sd)
  disk_serial="$(lsblk -ndo SERIAL /dev/nvme0n1 2>/dev/null || lsblk -ndo SERIAL /dev/sda 2>/dev/null || echo '')"

  HW_INFO_JSON="$(BOARD_SERIAL="$board_serial" BOARD_NAME="$board_name" CPU_MODEL="$cpu_model" MAC_PRIMARY="$mac_primary" DISK_SERIAL="$disk_serial" python3 - <<'PY'
import json
import os

hw = {
    "board_serial": os.environ.get("BOARD_SERIAL", "").strip() or None,
    "board_name": os.environ.get("BOARD_NAME", "").strip() or None,
    "cpu_model": os.environ.get("CPU_MODEL", "").strip() or None,
    "mac_primary": os.environ.get("MAC_PRIMARY", "").strip() or None,
    "disk_serial": os.environ.get("DISK_SERIAL", "").strip() or None,
}
print(json.dumps(hw))
PY
)"
}

pre_register() {
  echo "[POSVENDELO] Recolectando información de hardware..."
  collect_hw_info

  local pre_reg_json pre_reg_response
  pre_reg_json="$(mktemp)"

  OS_PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')" BRANCH_NAME="${BRANCH_NAME:-Sucursal Principal}" HW_INFO_JSON="$HW_INFO_JSON" python3 - <<'PY' > "$pre_reg_json"
import json
import os

payload = {
    "hw_info": json.loads(os.environ["HW_INFO_JSON"]),
    "os_platform": os.environ["OS_PLATFORM"],
    "branch_name": os.environ.get("BRANCH_NAME", "Sucursal Principal"),
}
print(json.dumps(payload))
PY

  echo "[POSVENDELO] Registrando equipo en el servidor central..."
  CURRENT_STEP="pre-registro"
  pre_reg_response="$(curl -fsSL -X POST \
    -H "Content-Type: application/json" \
    --data @"$pre_reg_json" \
    "${CP_URL%/}/api/v1/branches/pre-register")" || {
    echo "[POSVENDELO] No se pudo conectar al servidor central."
    echo "[POSVENDELO] Verifique su conexión a internet e intente de nuevo."
    rm -f "$pre_reg_json"
    exit 1
  }

  INSTALL_TOKEN="$(PRE_REG="$pre_reg_response" python3 - <<'PY'
import json
import os

body = json.loads(os.environ["PRE_REG"])
data = body.get("data", {})
is_new = data.get("is_new", True)
if is_new:
    print(f"[INFO] Equipo registrado por primera vez.", file=__import__("sys").stderr)
else:
    print(f"[INFO] Equipo reconocido. Período de prueba continúa.", file=__import__("sys").stderr)
print(data.get("install_token", ""))
PY
)"

  rm -f "$pre_reg_json"

  if [[ -z "$INSTALL_TOKEN" ]]; then
    echo "[POSVENDELO] No se obtuvo token de instalación del servidor."
    exit 1
  fi
}

run_compose() {
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    USER="${USER:-}" \
    docker compose --env-file .env "$@"
}

# --- Obtain install token (all functions now defined above) ---
if [[ -z "$INSTALL_TOKEN" ]]; then
  if [[ -n "$CLOUD_EMAIL" || -n "$CLOUD_PASSWORD" || -n "$TENANT_NAME" ]]; then
    bootstrap_cloud_install_token
  else
    # Pre-register with hardware fingerprint (plug-and-play, no account needed)
    pre_register
  fi
fi

if [[ -z "$INSTALL_TOKEN" ]]; then
  echo "[POSVENDELO] No se pudo obtener un token de instalación."
  usage
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "[POSVENDELO] Docker no encontrado. Instalando..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi

echo "[POSVENDELO] Verificando que Docker este listo..."
for _ in $(seq 1 45); do
  if docker version >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker version >/dev/null 2>&1; then
  echo "[POSVENDELO] Docker no responde todavia."
  echo "[POSVENDELO] Si acabas de instalar Docker, cierra sesion y vuelve a entrar antes de reintentar."
  exit 1
fi

mkdir -p "$INSTALL_DIR/backups"
cd "$INSTALL_DIR"
AGENT_JSON_PATH="$INSTALL_DIR/posvendelo-agent.json"

BOOTSTRAP_JSON="$(mktemp)"
REGISTER_JSON="$(mktemp)"

CURRENT_STEP="descargando bootstrap"
curl -fsSL -H "Authorization: Bearer ${INSTALL_TOKEN}" "${CP_URL%/}/api/v1/branches/bootstrap-config" -o "$BOOTSTRAP_JSON"

if [[ -z "$LOCAL_API_PORT" ]]; then
  LOCAL_API_PORT="$(pick_port 8000)"
fi
if [[ -z "$LOCAL_POSTGRES_PORT" ]]; then
  LOCAL_POSTGRES_PORT="$(pick_port 5434)"
fi

POS_VERSION="$POS_VERSION" LOCAL_API_PORT="$LOCAL_API_PORT" LOCAL_POSTGRES_PORT="$LOCAL_POSTGRES_PORT" BACKEND_IMAGE_OVERRIDE="${BACKEND_IMAGE_OVERRIDE:-}" python3 - "$BOOTSTRAP_JSON" > .env <<'PY'
import json
import os
import secrets
import sys

data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]

def rand_hex(n: int) -> str:
    return secrets.token_hex(n)

print(f"POSTGRES_PASSWORD={rand_hex(16)}")
print("ADMIN_API_USER=")
print("ADMIN_API_PASSWORD=")
print(f"JWT_SECRET={rand_hex(32)}")
print("CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080")
print(f"CONTROL_PLANE_URL={data.get('cp_url', '')}")
print(f"POSVENDELO_LICENSE_KEY={data.get('tenant_slug', '')}")
print(f"POSVENDELO_BRANCH_ID={data['branch_id']}")
print(f"POSVENDELO_VERSION={os.environ.get('POS_VERSION', '2.0.0')}")
print(f"CF_TUNNEL_TOKEN={data.get('cf_tunnel_token') or ''}")
override = os.environ.get("BACKEND_IMAGE_OVERRIDE", "").strip()
backend_image = override or data.get("backend_image") or os.environ.get("POSVENDELO_DEFAULT_BACKEND_IMAGE", "ghcr.io/uriel2121ger-art/posvendelo:latest")
print(f"BACKEND_IMAGE={backend_image}")
print(f"LOCAL_API_PORT={os.environ['LOCAL_API_PORT']}")
print(f"LOCAL_POSTGRES_PORT={os.environ['LOCAL_POSTGRES_PORT']}")
print("POSVENDELO_LICENSE_ENFORCEMENT=true")
PY
chmod 600 "$INSTALL_DIR/.env"

INSTALL_TOKEN="$INSTALL_TOKEN" INSTALL_DIR="$INSTALL_DIR" AGENT_JSON_PATH="$AGENT_JSON_PATH" LOCAL_API_PORT="$LOCAL_API_PORT" python3 - "$BOOTSTRAP_JSON" <<'PY'
import json
import os
import sys

data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]
api_port = os.environ["LOCAL_API_PORT"]
payload = {
    "controlPlaneUrl": data.get("cp_url", ""),
    "branchId": data.get("branch_id"),
    "installToken": os.environ["INSTALL_TOKEN"],
    "releaseManifestUrl": data.get("release_manifest_url", ""),
    "licenseResolveUrl": data.get("license_resolve_url", ""),
    "localApiUrl": f"http://127.0.0.1:{api_port}",
    "backendHealthUrl": f"http://127.0.0.1:{api_port}/health",
    "appArtifact": "electron-linux",
    "backendArtifact": "backend",
    "releaseChannel": data.get("release_channel") or "stable",
    "pollIntervals": {
        "healthSeconds": 15,
        "manifestSeconds": 300,
        "licenseSeconds": 300
    },
    "license": data.get("license"),
    "bootstrap": {
        "installDir": os.environ["INSTALL_DIR"],
        "composeTemplateUrl": data.get("compose_template_url", ""),
        "registerUrl": data.get("register_url", ""),
        "installReportUrl": data.get("install_report_url", ""),
        "bootstrapPublicKey": data.get("bootstrap_public_key", ""),
        "licenseResolveUrl": data.get("license_resolve_url", ""),
        "ownerSessionUrl": data.get("owner_session_url", ""),
        "ownerApiBaseUrl": data.get("owner_api_base_url", ""),
        "companionUrl": data.get("companion_url", ""),
        "companionEntryUrl": data.get("companion_entry_url", ""),
        "quickLinks": data.get("quick_links", {})
    }
}
with open(os.environ["AGENT_JSON_PATH"], "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
PY
chmod 600 "$INSTALL_DIR/posvendelo-agent.json"

CURRENT_STEP="descargando compose"
curl -fsSL -H "Authorization: Bearer ${INSTALL_TOKEN}" "${CP_URL%/}/api/v1/branches/compose-template" -o docker-compose.yml

cat > INSTALL_SUMMARY.txt <<EOF
POSVENDELO - RESUMEN DE INSTALACION

Directorio: ${INSTALL_DIR}
Branch ID: $(python3 - "$BOOTSTRAP_JSON" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]
print(data.get("branch_id", ""))
PY
)
Health local: http://127.0.0.1:${LOCAL_API_PORT}/health
API local: http://127.0.0.1:${LOCAL_API_PORT}
Postgres local: 127.0.0.1:${LOCAL_POSTGRES_PORT}
Control Plane: ${CP_URL}
Manifest: $(python3 - "$BOOTSTRAP_JSON" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]
print(data.get("release_manifest_url", ""))
PY
)
Companion: $(python3 - "$BOOTSTRAP_JSON" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]
print(data.get("companion_url", ""))
PY
)
Companion Portfolio: $(python3 - "$BOOTSTRAP_JSON" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]
print(data.get("companion_entry_url", ""))
PY
)
Owner API: $(python3 - "$BOOTSTRAP_JSON" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]
print(data.get("owner_api_base_url", ""))
PY
)

Primer acceso:
Configura tu usuario al abrir el POS por primera vez.
El asistente de configuracion te pedira crear un usuario administrador.

Período de prueba: 40 días desde el primer registro
Activar Nube: Desde la app, Configuración > Nube PosVendelo

Archivos clave:
- .env
- docker-compose.yml
- posvendelo-agent.json

Actualizar backend (cuando haya nueva versión):
  cd ${INSTALL_DIR} && ./actualizar.sh

Cómo abrir el punto de venta (POS):
  - Doble clic en el icono "POSVENDELO" del escritorio o del menú de aplicaciones (abre la app o la página de descargas).
  - Con la app instalada: busque "POSVENDELO" en el menú o ejecute: posvendelo
  - Si no tiene la app: descargue el .deb (Linux/Raspberry Pi) desde la web e instale (dpkg -i ...)
  - Si la app no inicia: ejecute desde terminal "posvendelo" para ver mensajes de error.
EOF
chmod 600 "$INSTALL_DIR/INSTALL_SUMMARY.txt"

if [[ -f "$INSTALLER_DIR/actualizar.sh" ]]; then
  cp "$INSTALLER_DIR/actualizar.sh" "$INSTALL_DIR/actualizar.sh"
  chmod +x "$INSTALL_DIR/actualizar.sh"
fi

# Script para abrir el POS (o la pagina de descargas si aun no esta instalada la app)
DOWNLOAD_PAGE="${CP_URL%/}/"
cat > "$INSTALL_DIR/abrir-pos.sh" <<ABRIRPOS
#!/usr/bin/env bash
if command -v posvendelo >/dev/null 2>&1; then
  exec posvendelo "\$@"
fi
echo "[POSVENDELO] La app de escritorio no esta instalada. Descargue el .deb desde: $DOWNLOAD_PAGE"
if command -v xdg-open >/dev/null 2>&1 && [[ -n "\${DISPLAY:-}" ]]; then
  xdg-open "$DOWNLOAD_PAGE" 2>/dev/null &
fi
ABRIRPOS
chmod +x "$INSTALL_DIR/abrir-pos.sh"

# Icono en escritorio y en el menu de aplicaciones (doble clic para abrir el POS)
DESKTOP_NAME="POSVENDELO"
DESKTOP_FILE="[Desktop Entry]
Version=1.0
Type=Application
Name=POSVENDELO - Punto de venta
Comment=Abrir el punto de venta
Exec=\"$INSTALL_DIR/abrir-pos.sh\"
Icon=utilities-terminal
Categories=Utility;
Terminal=false
"
mkdir -p "$HOME/.local/share/applications"
echo "$DESKTOP_FILE" > "$HOME/.local/share/applications/posvendelo-nodo.desktop"
chmod +x "$HOME/.local/share/applications/posvendelo-nodo.desktop"
if [[ -d "$HOME/Desktop" ]]; then
  echo "$DESKTOP_FILE" > "$HOME/Desktop/$DESKTOP_NAME.desktop"
  chmod +x "$HOME/Desktop/$DESKTOP_NAME.desktop"
  if command -v gio >/dev/null 2>&1; then
    gio set "$HOME/Desktop/$DESKTOP_NAME.desktop" metadata::trusted true 2>/dev/null || true
  fi
fi

MACHINE_ID="$(cat /etc/machine-id 2>/dev/null || hostname)"
OS_PLATFORM="$(uname -s | tr '[:upper:]' '[:lower:]')"

CURRENT_STEP="registrando sucursal"
INSTALL_TOKEN="$INSTALL_TOKEN" MACHINE_ID="$MACHINE_ID" OS_PLATFORM="$OS_PLATFORM" BRANCH_NAME="$BRANCH_NAME" APP_VERSION="$APP_VERSION" POS_VERSION="$POS_VERSION" python3 - <<'PY' > "$REGISTER_JSON"
import json
import os

payload = {
    "install_token": os.environ["INSTALL_TOKEN"],
    "machine_id": os.environ["MACHINE_ID"],
    "os_platform": os.environ["OS_PLATFORM"],
    "branch_name": os.environ.get("BRANCH_NAME") or None,
    "app_version": os.environ.get("APP_VERSION") or None,
    "pos_version": os.environ.get("POS_VERSION") or None,
}
print(json.dumps(payload))
PY

curl -fsSL -X POST \
  -H "Content-Type: application/json" \
  --data @"$REGISTER_JSON" \
  "${CP_URL%/}/api/v1/branches/register" >/dev/null

CURRENT_STEP="descargando imagenes"
PULL_FAILED=0
run_compose pull || PULL_FAILED=$?
if [[ "$PULL_FAILED" -ne 0 ]]; then
  echo ""
  echo "[POSVENDELO] No se pudo descargar alguna imagen (por ejemplo la del API)."
  if [[ -n "${BACKEND_IMAGE_OVERRIDE:-}" ]] && docker image inspect "$BACKEND_IMAGE_OVERRIDE" >/dev/null 2>&1; then
    echo "[POSVENDELO] La imagen $BACKEND_IMAGE_OVERRIDE existe localmente. Continuando con el arranque..."
  else
    echo "[POSVENDELO] Si tienes la imagen del API construida en esta máquina, ejecuta de nuevo con:"
    echo "        --backend-image posvendelo:local"
    echo "        (construir antes:  docker build -t posvendelo:local ./backend  desde la raíz del repo)"
    echo ""
    report_status "error" "fallo al descargar imagenes docker"
    exit 1
  fi
fi
CURRENT_STEP="arrancando stack"
CF_TUNNEL_TOKEN="$(awk -F= '$1=="CF_TUNNEL_TOKEN"{print $2}' .env | head -n1)"
if [[ -n "$CF_TUNNEL_TOKEN" ]]; then
  run_compose up -d
else
  echo "[POSVENDELO] Modo local (sin túnel remoto)."
  run_compose up -d
fi

echo "[POSVENDELO] Esperando health local..."
CURRENT_STEP="validando health"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${LOCAL_API_PORT}/health" >/dev/null 2>&1; then
    report_status "success"
    echo ""
    echo "[POSVENDELO] Instalacion completada en $INSTALL_DIR"
    echo ""
    echo "Para abrir el punto de venta (POS):"
    echo "  - Si ya instalaste la app: busque 'POSVENDELO' en el menu o ejecute: posvendelo"
    echo "  - Si aun no tiene la app: descargue el .deb desde la web e instalelo (dpkg -i ...)"
    echo ""
    if [[ -n "${DISPLAY:-}" ]] && command -v posvendelo >/dev/null 2>&1; then
      echo "[POSVENDELO] Iniciando la aplicacion POS..."
      nohup posvendelo >/dev/null 2>&1 &
      sleep 1
    elif [[ -n "${DISPLAY:-}" ]] && command -v xdg-open >/dev/null 2>&1; then
      echo "[POSVENDELO] Abriendo el POS en el navegador para configuracion inicial..."
      xdg-open "http://127.0.0.1:${LOCAL_API_PORT}" 2>/dev/null &
    fi
    exit 0
  fi
  sleep 2
done

echo "[POSVENDELO] El backend no respondio a tiempo"
exit 1
