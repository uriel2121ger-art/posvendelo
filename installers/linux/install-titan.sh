#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Uso: bash install-titan.sh --cp-url URL --install-token TOKEN [--branch-name NOMBRE] [--dir DIR] [--api-port PUERTO] [--db-port PUERTO]"
}

CP_URL=""
INSTALL_TOKEN=""
BRANCH_NAME=""
INSTALL_DIR="$HOME/.titanpos"
APP_VERSION="1.0.0"
POS_VERSION="2.0.0"
LOCAL_API_PORT=""
LOCAL_POSTGRES_PORT=""
BOOTSTRAP_JSON=""
REGISTER_JSON=""
AGENT_JSON_PATH=""
CURRENT_STEP="inicio"

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
    *)
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CP_URL" || -z "$INSTALL_TOKEN" ]]; then
  usage
  exit 1
fi

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

run_compose() {
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    USER="${USER:-}" \
    docker compose --env-file .env "$@"
}

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "[TITAN] Docker no encontrado. Instalando..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi

echo "[TITAN] Verificando que Docker este listo..."
for _ in $(seq 1 45); do
  if docker version >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker version >/dev/null 2>&1; then
  echo "[TITAN] Docker no responde todavia."
  echo "[TITAN] Si acabas de instalar Docker, cierra sesion y vuelve a entrar antes de reintentar."
  exit 1
fi

mkdir -p "$INSTALL_DIR/backups"
cd "$INSTALL_DIR"
AGENT_JSON_PATH="$INSTALL_DIR/titan-agent.json"

BOOTSTRAP_JSON="$(mktemp)"
REGISTER_JSON="$(mktemp)"

CURRENT_STEP="descargando bootstrap"
curl -fsSL "${CP_URL%/}/api/v1/branches/bootstrap-config?install_token=${INSTALL_TOKEN}" -o "$BOOTSTRAP_JSON"

if [[ -z "$LOCAL_API_PORT" ]]; then
  LOCAL_API_PORT="$(pick_port 8000)"
fi
if [[ -z "$LOCAL_POSTGRES_PORT" ]]; then
  LOCAL_POSTGRES_PORT="$(pick_port 5434)"
fi

POS_VERSION="$POS_VERSION" LOCAL_API_PORT="$LOCAL_API_PORT" LOCAL_POSTGRES_PORT="$LOCAL_POSTGRES_PORT" python3 - "$BOOTSTRAP_JSON" > .env <<'PY'
import json
import os
import secrets
import sys

data = json.load(open(sys.argv[1], "r", encoding="utf-8"))["data"]

def rand_hex(n: int) -> str:
    return secrets.token_hex(n)

print(f"POSTGRES_PASSWORD={rand_hex(16)}")
print("ADMIN_API_USER=admin")
print(f"ADMIN_API_PASSWORD={rand_hex(12)}")
print(f"JWT_SECRET={rand_hex(32)}")
print("CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080")
print(f"CONTROL_PLANE_URL={data.get('cp_url', '')}")
print(f"TITAN_LICENSE_KEY={data.get('tenant_slug', '')}")
print(f"TITAN_BRANCH_ID={data['branch_id']}")
print(f"TITAN_VERSION={os.environ.get('POS_VERSION', '2.0.0')}")
print(f"CF_TUNNEL_TOKEN={data.get('cf_tunnel_token') or ''}")
print(
    f"BACKEND_IMAGE={data.get('backend_image') or os.environ.get('TITAN_DEFAULT_BACKEND_IMAGE', 'ghcr.io/titan-pos/titan-pos:latest')}"
)
print(f"LOCAL_API_PORT={os.environ['LOCAL_API_PORT']}")
print(f"LOCAL_POSTGRES_PORT={os.environ['LOCAL_POSTGRES_PORT']}")
print("TITAN_LICENSE_ENFORCEMENT=true")
PY

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

CURRENT_STEP="descargando compose"
curl -fsSL "${CP_URL%/}/api/v1/branches/compose-template?install_token=${INSTALL_TOKEN}" -o docker-compose.yml

cat > INSTALL_SUMMARY.txt <<EOF
TITAN POS - RESUMEN DE INSTALACION

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

Archivos clave:
- .env
- docker-compose.yml
- titan-agent.json
EOF

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
run_compose pull
CURRENT_STEP="arrancando stack"
run_compose up -d

echo "[TITAN] Esperando health local..."
CURRENT_STEP="validando health"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${LOCAL_API_PORT}/health" >/dev/null 2>&1; then
    report_status "success"
    echo "[TITAN] Instalacion completada en $INSTALL_DIR"
    exit 0
  fi
  sleep 2
done

echo "[TITAN] El backend no respondio a tiempo"
exit 1
