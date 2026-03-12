#!/usr/bin/env bash
# ============================================================================
# POSVENDELO — Instalador Automático
# Uso: bash setup.sh   (o doble clic en INSTALAR.desktop)
# Re-ejecutable: no sobreescribe .env si ya existe
# ============================================================================
set -euo pipefail

# --- Colores y utilidades ------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ╔════════════════════════════════════════════╗"
    echo "  ║         POSVENDELO — INSTALADOR             ║"
    echo "  ╚════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

step() {
    local n="$1" total=7 label="$2"
    local filled=$((n)) empty=$((total - n))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="■"; done
    for ((i=0; i<empty; i++)); do bar+="□"; done
    echo ""
    echo -e "  ${BOLD}[$bar]${NC}  ${CYAN}$label${NC}"
    echo ""
}

ok()   { echo -e "    ${GREEN}✔${NC} $1"; }
warn() { echo -e "    ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "    ${RED}✖${NC} $1"; }

die() {
    echo ""
    echo -e "  ${RED}${BOLD}════════════════════════════════════════════${NC}"
    echo -e "  ${RED}${BOLD}  ERROR: $1${NC}"
    echo -e "  ${RED}${BOLD}════════════════════════════════════════════${NC}"
    echo ""
    exit 1
}

# --- Inicio ---------------------------------------------------------------
banner

AGENT_DIR="${HOME}/.posvendelo"
AGENT_JSON_PATH="${AGENT_DIR}/titan-agent.json"

# ═══════════════════════════════════════════════════════════════════════════
# FASE 1: Verificar Docker
# ═══════════════════════════════════════════════════════════════════════════
step 1 "Verificando Docker..."

if command -v docker &>/dev/null && docker compose version &>/dev/null; then
    ok "Docker y Docker Compose encontrados"
else
    warn "Docker no encontrado. Intentando instalar..."
    if command -v sudo &>/dev/null; then
        if sudo apt-get update -qq && sudo apt-get install -y -qq docker.io docker-compose-v2 &>/dev/null; then
            # Agregar usuario al grupo docker para no necesitar sudo
            sudo usermod -aG docker "$USER" 2>/dev/null || true
            ok "Docker instalado correctamente"
            warn "Si los siguientes pasos fallan, cierra sesión y vuelve a entrar"
            warn "(para que el grupo 'docker' tome efecto)"
        else
            fail "No se pudo instalar Docker automáticamente"
            echo ""
            echo -e "  ${BOLD}Pide a tu técnico que instale Docker:${NC}"
            echo ""
            echo "    sudo apt install docker.io docker-compose-v2"
            echo "    sudo usermod -aG docker $USER"
            echo "    # Cerrar sesión y volver a entrar"
            echo ""
            die "Docker es necesario para POSVENDELO"
        fi
    else
        fail "No se puede instalar Docker (sudo no disponible)"
        echo ""
        echo -e "  ${BOLD}Pide a tu técnico que instale Docker:${NC}"
        echo ""
        echo "    sudo apt install docker.io docker-compose-v2"
        echo "    sudo usermod -aG docker $USER"
        echo "    # Cerrar sesión y volver a entrar"
        echo ""
        die "Docker es necesario para POSVENDELO"
    fi
fi

mkdir -p "$AGENT_DIR"
cat > "$AGENT_JSON_PATH" <<AGENTCFG
{
  "controlPlaneUrl": "",
  "branchId": null,
  "installToken": "",
  "releaseManifestUrl": "",
  "licenseResolveUrl": "",
  "localApiUrl": "http://127.0.0.1:8000",
  "backendHealthUrl": "http://127.0.0.1:8000/health",
  "appArtifact": "electron-linux",
  "backendArtifact": "backend",
  "releaseChannel": "stable",
  "pollIntervals": {
    "healthSeconds": 15,
    "manifestSeconds": 300,
    "licenseSeconds": 300
  },
  "license": null,
  "bootstrap": {
    "installDir": "$SCRIPT_DIR",
    "bootstrapPublicKey": "",
    "licenseResolveUrl": ""
  }
}
AGENTCFG
ok "Agente local base generado en $AGENT_JSON_PATH"

cat > "${SCRIPT_DIR}/INSTALL_SUMMARY.txt" <<EOF
POSVENDELO - RESUMEN DE INSTALACION

Directorio: ${SCRIPT_DIR}
Health local: http://127.0.0.1:8000/health
API local: http://127.0.0.1:8000
Agente local: ${AGENT_JSON_PATH}

Archivos clave:
- .env
- docker-compose.yml
- CREDENCIALES.txt
- INSTALL_SUMMARY.txt
EOF
ok "Resumen de instalacion generado en ${SCRIPT_DIR}/INSTALL_SUMMARY.txt"

# ═══════════════════════════════════════════════════════════════════════════
# FASE 2: Generar configuración
# ═══════════════════════════════════════════════════════════════════════════
step 2 "Configurando variables de entorno..."

if [ -f .env ]; then
    ok "Archivo .env ya existe (no se modifica)"
else
    if [ ! -f .env.example ]; then
        die "No se encontró .env.example — ¿la descarga está completa?"
    fi

    # Generar secretos aleatorios
    PG_PASS="$(openssl rand -base64 20 | tr -d '/+=' | head -c 24)"
    JWT_SEC="$(openssl rand -hex 32)"
    ADMIN_PASS="$(openssl rand -base64 12 | tr -d '/+=' | head -c 16)"

    # Crear .env desde template
    cp .env.example .env
    # Strip CRLF line endings (Windows-edited .env.example)
    sed -i 's/\r$//' .env

    # Reemplazar cada variable por nombre (evita ambigüedad)
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" .env
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SEC}|" .env
    sed -i "s|^ADMIN_API_PASSWORD=.*|ADMIN_API_PASSWORD=${ADMIN_PASS}|" .env

    # DATABASE_URL: insertar password real y apuntar a hostname Docker
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://posvendelo_user:${PG_PASS}@postgres:5432/posvendelo|" .env

    # Standalone mode: ensure license enforcement is disabled (no control plane)
    if grep -q "^TITAN_LICENSE_ENFORCEMENT=" .env; then
        sed -i "s|^TITAN_LICENSE_ENFORCEMENT=.*|TITAN_LICENSE_ENFORCEMENT=false|" .env
    else
        echo "TITAN_LICENSE_ENFORCEMENT=false" >> .env
    fi

    ok "Archivo .env generado con secretos aleatorios"

    # Guardar credenciales en archivo legible
    cat > CREDENCIALES.txt <<CREDS
╔══════════════════════════════════════════════════╗
║          POSVENDELO — CREDENCIALES                ║
║   Guarda este archivo en un lugar seguro         ║
╚══════════════════════════════════════════════════╝

Generado: $(date '+%Y-%m-%d %H:%M')

Base de datos:
  Usuario:    posvendelo_user
  Contraseña: ${PG_PASS}

API Admin:
  Usuario:    admin
  Contraseña: ${ADMIN_PASS}

JWT Secret: ${JWT_SEC}

NOTA: El usuario y contraseña para usar el punto de venta
se crean la primera vez que abres la aplicación.
CREDS
    ok "Credenciales guardadas en CREDENCIALES.txt"
fi

# ═══════════════════════════════════════════════════════════════════════════
# FASE 3: Construir contenedores
# ═══════════════════════════════════════════════════════════════════════════
step 3 "Construyendo contenedores (esto puede tardar unos minutos)..."

if docker compose build --quiet 2>&1; then
    ok "Contenedores construidos"
else
    fail "Error al construir contenedores"
    die "Revisa tu conexión a internet e intenta de nuevo"
fi

# ═══════════════════════════════════════════════════════════════════════════
# FASE 4: Iniciar base de datos
# ═══════════════════════════════════════════════════════════════════════════
step 4 "Iniciando base de datos..."

docker compose up -d postgres
ok "Contenedor postgres iniciado"

echo -n "    Esperando a que la base de datos esté lista"
for i in $(seq 1 60); do
    if docker compose exec -T postgres pg_isready -U titan_user -d titan_pos &>/dev/null; then
        echo ""
        ok "Base de datos lista"
        break
    fi
    echo -n "."
    sleep 1
    if [ "$i" -eq 60 ]; then
        echo ""
        fail "La base de datos no respondió en 60 segundos"
        die "Ejecuta 'docker compose logs postgres' para ver el error"
    fi
done

# ═══════════════════════════════════════════════════════════════════════════
# FASE 4.5: Inicializar schema y migraciones
# ═══════════════════════════════════════════════════════════════════════════
step 5 "Inicializando base de datos..."

PSQL_ERR=$(mktemp)
trap 'rm -f "$PSQL_ERR"' EXIT

# Helper: run psql and classify errors
# Returns 0 if OK or only benign notices, 1 on fatal/SQL errors
# ON_ERROR_STOP=1 makes psql exit on first ERROR (NOTICEs like "already exists" are fine)
run_psql() {
    local label="$1"
    if docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U titan_user -d titan_pos 2>"$PSQL_ERR"; then
        return 0
    else
        # Check if errors are only benign "already exists" notices
        if grep -qiE 'FATAL|could not connect|authentication failed|permission denied' "$PSQL_ERR"; then
            fail "$label — error critico de base de datos:"
            cat "$PSQL_ERR" >&2
            return 1
        elif grep -qiE 'ERROR:' "$PSQL_ERR"; then
            fail "$label — error SQL:"
            cat "$PSQL_ERR" >&2
            return 1
        else
            # Only benign notices (e.g., "table already exists")
            return 0
        fi
    fi
}

# Buscar schema SQL (puede estar en varias ubicaciones)
SCHEMA_FILE=""
for candidate in \
    "backend/db/schema.sql" \
    "_archive/backend_original/src/infra/schema_postgresql.sql" \
    "backend/schema_postgresql.sql" \
    "schema_postgresql.sql"; do
    if [ -f "$candidate" ]; then
        SCHEMA_FILE="$candidate"
        break
    fi
done

if [ -n "$SCHEMA_FILE" ]; then
    if run_psql "Schema base" < "$SCHEMA_FILE"; then
        ok "Schema base aplicado ($SCHEMA_FILE)"
    else
        die "No se pudo aplicar el schema base — revisa 'docker compose logs postgres'"
    fi
else
    warn "No se encontro ningun schema SQL conocido — asegurate de que las tablas existan"
fi

# Migraciones incrementales (orden numerico, idempotentes)
MIGRATION_COUNT=0
MIGRATION_FAIL=0
if [ -d "backend/migrations" ]; then
    for f in $(ls backend/migrations/*.sql 2>/dev/null | sort -V); do
        [ -f "$f" ] || continue
        if run_psql "Migracion $(basename "$f")" < "$f"; then
            MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
        else
            MIGRATION_FAIL=$((MIGRATION_FAIL + 1))
            fail "Migracion fallida: $(basename "$f")"
        fi
    done
    if [ "$MIGRATION_FAIL" -gt 0 ]; then
        die "$MIGRATION_FAIL migraciones fallaron — revisa los errores arriba"
    fi
    ok "$MIGRATION_COUNT migraciones aplicadas"
else
    warn "No se encontro directorio de migraciones"
fi

# Verificar tablas criticas existen
MISSING_TABLES=""
for tbl in products users sales schema_version; do
    COUNT=$(docker compose exec -T postgres psql -U titan_user -d titan_pos -tAc \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='$tbl';" 2>/dev/null)
    if [ "$COUNT" != "1" ]; then
        MISSING_TABLES="$MISSING_TABLES $tbl"
    fi
done
if [ -n "$MISSING_TABLES" ]; then
    die "Tablas criticas faltantes:$MISSING_TABLES — el schema no se aplico correctamente"
fi
ok "Tablas criticas presentes (products, users, sales, schema_version)"

# Seed: crear usuario admin si no existe
if run_psql "Seed admin" <<'SEED'; then
INSERT INTO users (username, password_hash, role, is_active, created_at)
SELECT 'admin',
       '$2b$12$LJ3m4ys3Lk0T/XEVpGmCaOZEgMnUVWxYfPXZBCmO0jH/6YvQe6XAa',
       'admin', 1, NOW()
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');
SEED
    ok "Usuario admin verificado"
else
    warn "No se pudo verificar usuario admin (la app pedira crear uno al iniciar)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# FASE 5: Iniciar servidor
# ═══════════════════════════════════════════════════════════════════════════
step 6 "Iniciando servidor POSVENDELO..."

docker compose up -d api
ok "Contenedor api iniciado"

echo -n "    Esperando a que el servidor esté listo"
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        echo ""
        ok "Servidor listo"
        break
    fi
    echo -n "."
    sleep 1
    if [ "$i" -eq 60 ]; then
        echo ""
        fail "El servidor no respondió en 60 segundos"
        die "Ejecuta 'docker compose logs api' para ver el error"
    fi
done

# ═══════════════════════════════════════════════════════════════════════════
# FASE 6: Crear acceso directo en escritorio
# ═══════════════════════════════════════════════════════════════════════════
step 7 "Creando acceso directo en el escritorio..."

# Detectar carpeta de escritorio
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
if [ -d "$HOME/Escritorio" ]; then
    DESKTOP_DIR="$HOME/Escritorio"
elif [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
fi

mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/POSVENDELO.desktop" <<DESK
[Desktop Entry]
Name=POSVENDELO
Comment=Punto de Venta
Exec=xdg-open http://localhost:8000
Terminal=false
Type=Application
Icon=accessories-calculator
Categories=Office;Finance;
DESK

chmod +x "$DESKTOP_DIR/POSVENDELO.desktop"

# Marcar como confiable (GNOME) — ignorar si falla
gio set "$DESKTOP_DIR/POSVENDELO.desktop" metadata::trusted true 2>/dev/null || true

ok "Acceso directo creado en $DESKTOP_DIR"

# ═══════════════════════════════════════════════════════════════════════════
# LISTO
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo -e "  ${GREEN}${BOLD}════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}${BOLD}  ✅ ¡INSTALACIÓN COMPLETADA!${NC}"
echo -e "  ${GREEN}${BOLD}════════════════════════════════════════════${NC}"
echo ""
echo -e "  Se creó un acceso directo ${BOLD}POSVENDELO${NC} en tu escritorio."
echo -e "  Ábrelo para comenzar a usar el punto de venta."
echo ""
echo -e "  La primera vez, la aplicación te pedirá crear"
echo -e "  tu usuario y contraseña."
echo ""

# Intentar abrir el navegador automáticamente
xdg-open http://localhost:8000 2>/dev/null &
