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
# 1. Mode detection and agent config
#    From here on we disable set -e: network failures must NOT abort
#    the package installation.
# ---------------------------------------------------------------------------
set +e

INSTALL_DIR="/opt/posvendelo"

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=""
[ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ] && REAL_HOME=$(getent passwd "$REAL_USER" 2>/dev/null | cut -d: -f6) || true
if [ -z "$REAL_HOME" ]; then
  REAL_HOME="$HOME"
fi
POSVENDELO_CONFIG_DIR="${REAL_HOME}/.config/posvendelo"
INSTALL_MODE_FILE="$POSVENDELO_CONFIG_DIR/install-mode"

log() {
    echo "[POSVENDELO] $*"
}

# Modo caja secundaria (from stub installer env var): solo app, sin backend.
if [ "$INSTALL_MODE" = "client" ] || [ "$INSTALL_MODE" = "secundaria" ]; then
  log "Modo caja secundaria: no se instala backend ni base de datos."
  mkdir -p "$POSVENDELO_CONFIG_DIR"
  echo "client" > "$INSTALL_MODE_FILE"
  if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
    chown "$REAL_USER:$REAL_USER" "$INSTALL_MODE_FILE" 2>/dev/null || true
    chown "$REAL_USER:$REAL_USER" "$POSVENDELO_CONFIG_DIR" 2>/dev/null || true
  fi
  log "Al abrir la app, configura la dirección del servidor de la sucursal."
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. Generate posvendelo-agent.json (minimal — no installToken yet)
#    The backend auto-registers with control-plane on first boot.
# ---------------------------------------------------------------------------
AGENT_CONFIG_DIR="$POSVENDELO_CONFIG_DIR"
AGENT_CONFIG="$AGENT_CONFIG_DIR/posvendelo-agent.json"

# Read CONTROL_PLANE_URL from .env if it exists, default to posvendelo.com
CP_URL="https://posvendelo.com"
ENV_FILE="$INSTALL_DIR/.env"
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

# ---------------------------------------------------------------------------
# 3. Prepare INSTALL_DIR and copy agent config
# ---------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR"

# Copy to INSTALL_DIR for Docker container bind mount
if [ -f "$AGENT_CONFIG" ]; then
    cp "$AGENT_CONFIG" "$INSTALL_DIR/posvendelo-agent.json" 2>/dev/null && chmod 666 "$INSTALL_DIR/posvendelo-agent.json" || true
fi

# Upgrade path: if Docker backend is already running, auto-set mode to 'principal'
# so the user doesn't see the mode selection screen unnecessarily.
if [ ! -f "$INSTALL_MODE_FILE" ] && command -v docker &>/dev/null; then
    if docker compose -f "$INSTALL_DIR/docker-compose.yml" ps --quiet 2>/dev/null | grep -q .; then
        mkdir -p "$POSVENDELO_CONFIG_DIR"
        echo "principal" > "$INSTALL_MODE_FILE"
        if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
            chown "$REAL_USER:$REAL_USER" "$INSTALL_MODE_FILE" 2>/dev/null || true
        fi
        log "Backend existente detectado — modo 'principal' configurado automaticamente."
    fi
fi
cat > "$INSTALL_DIR/INSTALL_SUMMARY.txt" << 'SUMEOF'
╔══════════════════════════════════════════════╗
║         POSVENDELO — Instalado OK            ║
╠══════════════════════════════════════════════╣
║                                              ║
║  Abre la app "POSVENDELO" desde el menu      ║
║  de aplicaciones.                            ║
║                                              ║
║  En el primer arranque, elige si esta PC     ║
║  sera el servidor principal o una caja       ║
║  secundaria.                                 ║
║                                              ║
║  El sistema se configura automaticamente.    ║
║                                              ║
╚══════════════════════════════════════════════╝
SUMEOF

log "Instalacion completada. Abre POSVENDELO desde el menu de aplicaciones."

# Always exit 0 — package installation must never fail
exit 0
