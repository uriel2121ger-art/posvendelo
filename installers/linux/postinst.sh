#!/bin/bash
set -e

INSTALL_DIR="/opt/titan-pos"
COMPOSE_FILE="$INSTALL_DIR/docker-compose.yml"
ENV_FILE="$INSTALL_DIR/.env"
SERVICE_FILE="/etc/systemd/system/titan-pos.service"

log() {
    echo "[POSVENDELO] $*"
}

# ---------------------------------------------------------------------------
# Upgrade path: if backend is already running just pull + restart and exit
# ---------------------------------------------------------------------------
if [ -f "$COMPOSE_FILE" ] && docker compose -f "$COMPOSE_FILE" ps --quiet 2>/dev/null | grep -q .; then
    log "Backend ya en ejecución — actualizando imagen..."
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
DATABASE_URL=postgresql+asyncpg://titan_user:$DB_PASSWORD@postgres:5432/titan_pos
JWT_SECRET=$JWT_SECRET
ADMIN_API_USER=
ADMIN_API_PASSWORD=
DEBUG=false
ENVEOF
    chmod 600 "$ENV_FILE"
    log ".env generado con credenciales seguras."
else
    log ".env existente conservado."
fi

# ---------------------------------------------------------------------------
# 5. Create docker-compose.yml (always overwritten to pick up image updates)
# ---------------------------------------------------------------------------
cat > "$COMPOSE_FILE" << 'DCEOF'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: titan_pos
      POSTGRES_USER: titan_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U titan_user -d titan_pos"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    image: ghcr.io/uriel2121ger-art/titan-pos:latest
    env_file:
      - .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      JWT_SECRET: ${JWT_SECRET}
      ADMIN_API_USER: ${ADMIN_API_USER:-}
      ADMIN_API_PASSWORD: ${ADMIN_API_PASSWORD:-}
      CORS_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
      CORS_ALLOWED_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
DCEOF

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
systemctl enable titan-pos.service
log "Servicio systemd registrado."

# ---------------------------------------------------------------------------
# 7. Pull image and start containers
# ---------------------------------------------------------------------------
log "Descargando backend (puede tardar unos minutos en la primera instalación)..."
cd "$INSTALL_DIR"
docker compose pull 2>&1 | tail -5 || {
    log "ADVERTENCIA: No se pudo descargar la imagen. El servicio iniciará cuando haya internet."
    exit 0
}
docker compose up -d
log "Contenedores iniciados."

# ---------------------------------------------------------------------------
# 8. Wait for the API health endpoint (up to 60 s)
# ---------------------------------------------------------------------------
log "Esperando que el servidor esté listo..."
READY=0
for i in $(seq 1 30); do
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
# 9. Write INSTALL_SUMMARY
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
║  Datos en: /opt/titan-pos/                   ║
║                                              ║
╚══════════════════════════════════════════════╝
SUMEOF

log "¡Instalación completada! Abre POSVENDELO desde el menú de aplicaciones."
