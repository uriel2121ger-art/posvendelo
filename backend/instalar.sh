#!/bin/bash
# ============================================
# POSVENDELO - Instalador/Reinstalador
# ============================================
# Un solo script que hace todo:
# 1. Borra BD existente (si hay)
# 2. Configura PostgreSQL
# 3. Lanza el POS
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║       POSVENDELO - Instalador                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================
# 1. VERIFICAR DEPENDENCIAS
# ============================================
echo -e "${YELLOW}[1/4] Verificando dependencias...${NC}"

# Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 no instalado${NC}"
    echo "Ejecute: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
echo "  ✓ Python 3"

# PostgreSQL
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}  PostgreSQL no instalado. Instalando...${NC}"
    sudo apt update && sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi
echo "  ✓ PostgreSQL"

# ============================================
# 2. CONFIGURAR BASE DE DATOS
# ============================================
echo ""
echo -e "${YELLOW}[2/4] Configurando base de datos...${NC}"
echo ""

read -p "Usuario PostgreSQL [posvendelo_user]: " DB_USER
DB_USER=${DB_USER:-posvendelo_user}

read -sp "Contraseña: " DB_PASS
echo ""

if [ -z "$DB_PASS" ]; then
    echo -e "${RED}Error: Contraseña requerida${NC}"
    exit 1
fi

DB_NAME="posvendelo"
DB_HOST="localhost"
DB_PORT="5432"

echo ""
echo "Configurando PostgreSQL..."

# Borrar BD existente y crear nueva
sudo -u postgres psql \
  -v db_user="$DB_USER" \
  -v db_pass="$DB_PASS" \
  -v db_name="$DB_NAME" << 'EOSQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = :'db_name' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :db_name;
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'db_user') THEN
        EXECUTE format('CREATE USER %I WITH PASSWORD %L', :'db_user', :'db_pass');
    ELSE
        EXECUTE format('ALTER USER %I WITH PASSWORD %L', :'db_user', :'db_pass');
    END IF;
END $$;
CREATE DATABASE :db_name OWNER :db_user;
GRANT ALL PRIVILEGES ON DATABASE :db_name TO :db_user;
EOSQL

echo -e "${GREEN}  ✓ Base de datos creada${NC}"

# ============================================
# 3. GUARDAR CONFIGURACIÓN
# ============================================
echo ""
echo -e "${YELLOW}[3/4] Guardando configuración...${NC}"

# database.json
cat > "$SCRIPT_DIR/data/config/database.json" << EOF
{
  "postgresql": {
    "host": "$DB_HOST",
    "port": $DB_PORT,
    "database": "$DB_NAME",
    "user": "$DB_USER",
    "password": "$DB_PASS"
  }
}
EOF

# config.json limpio
cat > "$SCRIPT_DIR/data/config/config.json" << 'EOF'
{
    "admin_user": "",
    "admin_pass_hash": "",
    "setup_completed": false,
    "business_name": "",
    "business_type": "",
    "mode": "server",
    "server_port": 8000,
    "theme": "Dark",
    "setup_complete": false
}
EOF

echo -e "${GREEN}  ✓ Configuración guardada${NC}"

# ============================================
# 4. INSTALAR DEPENDENCIAS PYTHON
# ============================================
echo ""
echo -e "${YELLOW}[4/4] Instalando dependencias Python...${NC}"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo -e "${GREEN}  ✓ Dependencias instaladas${NC}"

# ============================================
# LISTO
# ============================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ INSTALACIÓN COMPLETADA                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Para iniciar POSVENDELO:"
echo "  ./posvendelo.sh"
echo ""
echo "O doble click en POSVENDELO.desktop"
echo ""

read -p "¿Iniciar POSVENDELO ahora? [S/n]: " START_NOW
if [ "$START_NOW" != "n" ] && [ "$START_NOW" != "N" ]; then
    echo ""
    echo -e "${GREEN}🚀 Iniciando POSVENDELO...${NC}"
    python3 -m app.main
fi
