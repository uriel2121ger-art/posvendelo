#!/bin/bash
# ============================================
# POSVENDELO - Lanzador
# ============================================

# Obtener directorio del script
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
echo "╔══════════════════════════════════════════╗"
echo "║         POSVENDELO - Punto de Venta       ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python 3 no está instalado${NC}"
    echo ""
    echo "Instalar con: sudo apt install python3 python3-pip python3-venv"
    echo ""
    read -p "Presione Enter para salir..."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✅ Python $PYTHON_VERSION detectado${NC}"

# Verificar/crear entorno virtual
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo -e "${YELLOW}Creando entorno virtual...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activar entorno virtual
source "$VENV_DIR/bin/activate"

# Verificar dependencias
if [ ! -f "$VENV_DIR/.deps_installed" ]; then
    echo ""
    echo -e "${YELLOW}Instalando dependencias (primera ejecución)...${NC}"
    echo "Esto puede tardar unos minutos..."
    echo ""

    pip install --upgrade pip -q

    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements.txt" -q
    else
        # Dependencias mínimas
        pip install PyQt6 psycopg2-binary pandas openpyxl python-dateutil -q
    fi

    touch "$VENV_DIR/.deps_installed"
    echo -e "${GREEN}✅ Dependencias instaladas${NC}"
fi

# Verificar configuración de base de datos
DB_CONFIG="$SCRIPT_DIR/data/config/database.json"
if [ -f "$DB_CONFIG" ]; then
    DB_USER=$(python3 -c "import json; print(json.load(open('$DB_CONFIG'))['postgresql'].get('user', ''))" 2>/dev/null)
    if [ -z "$DB_USER" ]; then
        echo ""
        echo -e "${YELLOW}⚠️  Base de datos no configurada${NC}"
        echo "Ejecute primero: sudo ./setup_postgres.sh"
        echo ""
        read -p "Presione Enter para salir..."
        exit 1
    fi
fi

# Ejecutar aplicación
echo ""
echo -e "${GREEN}🚀 Iniciando POSVENDELO...${NC}"
echo ""

python3 -m app.main

# Si hay error, mostrar mensaje
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ La aplicación terminó con errores (código: $EXIT_CODE)${NC}"
    echo ""
    read -p "Presione Enter para salir..."
fi
