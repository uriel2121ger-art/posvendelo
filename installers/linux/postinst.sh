#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# 0. Standard Electron app registration (symlink, sandbox, mime, apparmor)
#    This replaces what electron-builder's default postinst would do.
# ---------------------------------------------------------------------------
APP_DIR="/opt/POSVENDELO"

if [ -d "$APP_DIR" ]; then
    # Symlink to /usr/bin
    if type update-alternatives >/dev/null 2>&1; then
        if [ -L '/usr/bin/posvendelo' ] && [ -e '/usr/bin/posvendelo' ] && [ "$(readlink '/usr/bin/posvendelo')" != '/etc/alternatives/posvendelo' ]; then
            rm -f '/usr/bin/posvendelo'
        fi
        update-alternatives --install '/usr/bin/posvendelo' 'posvendelo' "$APP_DIR/posvendelo" 100 || ln -sf "$APP_DIR/posvendelo" '/usr/bin/posvendelo'
    else
        ln -sf "$APP_DIR/posvendelo" '/usr/bin/posvendelo'
    fi

    # Chrome sandbox permissions
    if ! { [[ -L /proc/self/ns/user ]] && unshare --user true; }; then
        chmod 4755 "$APP_DIR/chrome-sandbox" || true
    else
        chmod 0755 "$APP_DIR/chrome-sandbox" || true
    fi

    # Update desktop/mime databases
    hash update-mime-database 2>/dev/null && update-mime-database /usr/share/mime || true
    hash update-desktop-database 2>/dev/null && update-desktop-database /usr/share/applications || true

    # AppArmor profile (Ubuntu 24+)
    if apparmor_status --enabled > /dev/null 2>&1; then
        APPARMOR_PROFILE_SOURCE="$APP_DIR/resources/apparmor-profile"
        APPARMOR_PROFILE_TARGET="/etc/apparmor.d/posvendelo"
        if [ -f "$APPARMOR_PROFILE_SOURCE" ] && apparmor_parser --skip-kernel-load --debug "$APPARMOR_PROFILE_SOURCE" > /dev/null 2>&1; then
            cp -f "$APPARMOR_PROFILE_SOURCE" "$APPARMOR_PROFILE_TARGET"
            if ! { [ -x '/usr/bin/ischroot' ] && /usr/bin/ischroot; } && hash apparmor_parser 2>/dev/null; then
                apparmor_parser --replace --write-cache --skip-read-cache "$APPARMOR_PROFILE_TARGET" || true
            fi
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 1. Backend setup — Docker + PostgreSQL + API
#    From here on we disable set -e: network/Docker failures must NOT abort
#    the package installation. The app installs fine, backend starts later.
#    If INSTALL_MODE=client or INSTALL_MODE=secundaria: skip backend, only write marker for app.
# ---------------------------------------------------------------------------
set +e

INSTALL_DIR="/opt/posvendelo"

# Modo caja secundaria: solo app, sin backend. El usuario conecta a un servidor en LAN.
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=""
[ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ] && REAL_HOME=$(getent passwd "$REAL_USER" 2>/dev/null | cut -d: -f6) || true
if [ -z "$REAL_HOME" ]; then
  REAL_HOME="$HOME"
fi
POSVENDELO_CONFIG_DIR="${REAL_HOME}/.config/posvendelo"
INSTALL_MODE_FILE="$POSVENDELO_CONFIG_DIR/install-mode"

if [ "$INSTALL_MODE" = "client" ] || [ "$INSTALL_MODE" = "secundaria" ]; then
  log "Modo caja secundaria: no se instala backend ni base de datos."
  mkdir -p "$POSVENDELO_CONFIG_DIR"
  echo "client" > "$INSTALL_MODE_FILE"
  if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
    chown "$REAL_USER:$REAL_USER" "$INSTALL_MODE_FILE" 2>/dev/null || true
    chown "$REAL_USER:$REAL_USER" "$POSVENDELO_CONFIG_DIR" 2>/dev/null || true
  fi
  log "Al abrir la app, configura la dirección del servidor de la sucursal (Conectar al servidor)."
  exit 0
fi

COMPOSE_FILE="$INSTALL_DIR/docker-compose.yml"
ENV_FILE="$INSTALL_DIR/.env"
SERVICE_FILE="/etc/systemd/system/posvendelo.service"

log() {
    echo "[POSVENDELO] $*"
}

# ---------------------------------------------------------------------------
# Ensure CUPS is available for printer discovery/printing
# ---------------------------------------------------------------------------
if ! command -v lpstat &>/dev/null; then
    log "Instalando soporte de impresión (cups)..."
    apt-get install -y --no-install-recommends cups-client 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Upgrade path: regenerate compose, pull image and restart
# ---------------------------------------------------------------------------
_write_compose() {
    mkdir -p "$INSTALL_DIR"
    cat > "$COMPOSE_FILE" << 'DCEOF'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: posvendelo
      POSTGRES_USER: posvendelo_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U posvendelo_user -d posvendelo"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    image: ${BACKEND_IMAGE}
    env_file:
      - .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      JWT_SECRET: ${JWT_SECRET}
      ADMIN_API_USER: ${ADMIN_API_USER:-}
      ADMIN_API_PASSWORD: ${ADMIN_API_PASSWORD:-}
      CORS_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
      CORS_ALLOWED_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
      POSVENDELO_AGENT_CONFIG_PATH: /runtime/posvendelo-agent.json
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./posvendelo-agent.json:/runtime/posvendelo-agent.json:ro
      - /var/run/cups/cups.sock:/var/run/cups/cups.sock
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
DCEOF
}

if [ -f "$ENV_FILE" ] && docker compose -f "$COMPOSE_FILE" ps --quiet 2>/dev/null | grep -q .; then
    log "Backend ya en ejecución — actualizando..."
    _write_compose
    docker compose -f "$COMPOSE_FILE" pull --quiet 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" up -d 2>/dev/null || true
    log "Actualización completada."
    exit 0
fi

log "Instalando sistema completo..."

# ---------------------------------------------------------------------------
# 1. Install Docker if not present
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    log "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    log "Docker ya instalado."
fi

# Make sure the Docker daemon is running
systemctl start docker 2>/dev/null || true

# ---------------------------------------------------------------------------
# 2. Add real user to docker group
# ---------------------------------------------------------------------------
REAL_USER="${SUDO_USER:-$USER}"
if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
    usermod -aG docker "$REAL_USER" 2>/dev/null || true
    log "Usuario '$REAL_USER' agregado al grupo docker."
fi

# ---------------------------------------------------------------------------
# 3. Create install directory
# ---------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR/backups"

# ---------------------------------------------------------------------------
# 4. Generate .env (only on fresh install — never overwrite existing secrets)
# ---------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
    cat > "$ENV_FILE" << ENVEOF
POSTGRES_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql+asyncpg://posvendelo_user:$DB_PASSWORD@postgres:5432/posvendelo
JWT_SECRET=$JWT_SECRET
ADMIN_API_USER=
ADMIN_API_PASSWORD=
DEBUG=false
BACKEND_IMAGE=ghcr.io/uriel2121ger-art/posvendelo:latest
ENVEOF
    chmod 600 "$ENV_FILE"
    log ".env generado con credenciales seguras."
else
    log ".env existente conservado."
fi

# ---------------------------------------------------------------------------
# 5. Create docker-compose.yml (always overwritten to pick up image updates)
# ---------------------------------------------------------------------------
_write_compose

# ---------------------------------------------------------------------------
# 6. Create systemd service for auto-start on boot
# ---------------------------------------------------------------------------
cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=POSVENDELO POS Backend
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable posvendelo.service
log "Servicio systemd registrado."

# ---------------------------------------------------------------------------
# 7. Pull image and start containers
# ---------------------------------------------------------------------------
log "Descargando backend (puede tardar unos minutos en la primera instalación)..."
cd "$INSTALL_DIR"
if docker compose pull 2>&1; then
    docker compose up -d && log "Contenedores iniciados." || log "ADVERTENCIA: No se pudieron iniciar los contenedores. Reinicia el equipo o ejecuta: sudo systemctl start posvendelo"
else
    log "ADVERTENCIA: No se pudo descargar la imagen. El servicio iniciará automáticamente cuando haya internet."
    log "Para iniciar manualmente: sudo systemctl start posvendelo"
fi

# ---------------------------------------------------------------------------
# 8. Wait for the API health endpoint (up to 60 s)
# ---------------------------------------------------------------------------
log "Esperando que el servidor esté listo..."
READY=0
for _ in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 2
done

if [ "$READY" -eq 1 ]; then
    log "¡Servidor listo en http://127.0.0.1:8000!"
else
    log "El servidor tardó más de lo esperado. Abre POSVENDELO en unos minutos."
fi

# ---------------------------------------------------------------------------
# 9. Generate posvendelo-agent.json for auto-update
#    The agent needs controlPlaneUrl to poll for updates.
#    installToken gets set later during pre-registration.
# ---------------------------------------------------------------------------
AGENT_CONFIG_DIR="$HOME/.config/posvendelo"
AGENT_CONFIG="$AGENT_CONFIG_DIR/posvendelo-agent.json"
# Also generate for the real user (not root)
if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
    REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
    AGENT_CONFIG_DIR="$REAL_HOME/.config/posvendelo"
    AGENT_CONFIG="$AGENT_CONFIG_DIR/posvendelo-agent.json"
fi

# Read CONTROL_PLANE_URL from .env if set, default to posvendelo.com
CP_URL="https://posvendelo.com"
if [ -f "$ENV_FILE" ]; then
    env_cp=$(grep -oP 'CONTROL_PLANE_URL=\K.*' "$ENV_FILE" 2>/dev/null | tr -d '[:space:]' || true)
    [ -n "$env_cp" ] && CP_URL="$env_cp"
fi

if [ ! -f "$AGENT_CONFIG" ]; then
    mkdir -p "$AGENT_CONFIG_DIR"
    cat > "$AGENT_CONFIG" << AGENTEOF
{
  "installDir": "/opt/posvendelo",
  "controlPlaneUrl": "$CP_URL",
  "localApiUrl": "http://127.0.0.1:8000",
  "backendHealthUrl": "http://127.0.0.1:8000/health",
  "appArtifact": "electron-linux",
  "backendArtifact": "backend",
  "releaseChannel": "stable",
  "pollIntervals": {
    "healthSeconds": 30,
    "manifestSeconds": 300,
    "licenseSeconds": 3600
  }
}
AGENTEOF
    if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
        chown -R "$REAL_USER:$REAL_USER" "$AGENT_CONFIG_DIR" 2>/dev/null || true
    fi
    log "posvendelo-agent.json generado."
else
    log "posvendelo-agent.json existente conservado."
fi
# Copia en INSTALL_DIR para que el contenedor del backend la monte (Licencia del nodo)
if [ -f "$AGENT_CONFIG" ]; then
    cp "$AGENT_CONFIG" "$INSTALL_DIR/posvendelo-agent.json" 2>/dev/null && chmod 644 "$INSTALL_DIR/posvendelo-agent.json" || true
fi

# ---------------------------------------------------------------------------
# 10. Write INSTALL_SUMMARY
# ---------------------------------------------------------------------------
cat > "$INSTALL_DIR/INSTALL_SUMMARY.txt" << 'SUMEOF'
╔══════════════════════════════════════════════╗
║         POSVENDELO — Instalado OK            ║
╠══════════════════════════════════════════════╣
║                                              ║
║  Abre la app "POSVENDELO" desde el menú      ║
║  de aplicaciones.                            ║
║                                              ║
║  Configura tu usuario al abrir el POS        ║
║  por primera vez.                            ║
║                                              ║
║  Backend: http://127.0.0.1:8000              ║
║  Datos en: /opt/posvendelo/                  ║
║                                              ║
╚══════════════════════════════════════════════╝
SUMEOF

log "¡Instalación completada! Abre POSVENDELO desde el menú de aplicaciones."

# Always exit 0 — backend issues must never fail dpkg
exit 0
