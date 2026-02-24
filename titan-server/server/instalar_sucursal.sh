#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
# 🏪 TITAN POS - INSTALADOR PARA SUCURSALES v2.0
# Instalación completa: Tailscale + Registro automático + TITAN POS
# Ejecución: chmod +x instalar_sucursal.sh && ./instalar_sucursal.sh
#═══════════════════════════════════════════════════════════════════════════════

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║          🏪 TITAN POS - INSTALADOR PARA SUCURSALES               ║"
echo "║                     Versión 2.0 - Enero 2026                       ║"
echo "║                                                                    ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Variables
TITAN_DIR="$HOME/titan-pos"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADMIN_TOKEN="${TITAN_GATEWAY_ADMIN_TOKEN:-}"

#───────────────────────────────────────────────────────────────────────────────
# Preguntar datos del servidor y sucursal
#───────────────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}📋 CONFIGURACIÓN INICIAL${NC}"
echo ""
echo "   Necesitamos algunos datos para conectar esta sucursal al servidor central."
echo ""
read -p "   IP del servidor central (ej: 100.81.7.8): " SERVER_IP
if [ -z "$ADMIN_TOKEN" ]; then
    read -s -p "   Token admin del gateway (se oculta): " ADMIN_TOKEN
    echo ""
fi
read -s -p "   Contraseña PostgreSQL central (usuario titan): " DB_PASSWORD
echo ""
read -p "   ID de sucursal (número único, ej: 1, 2, 3): " BRANCH_ID
read -p "   Nombre de esta sucursal (ej: Centro, Norte): " BRANCH_NAME
read -p "   Número de terminal/caja (ej: 1): " TERMINAL_ID
echo ""

# Valores por defecto
[ -z "$BRANCH_ID" ] && BRANCH_ID=1
[ -z "$TERMINAL_ID" ] && TERMINAL_ID=1
[ -z "$BRANCH_NAME" ] && BRANCH_NAME="Sucursal $BRANCH_ID"

# Validar que BRANCH_ID y TERMINAL_ID sean números
if ! [[ "$BRANCH_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}❌ El ID de sucursal debe ser un número${NC}"
    exit 1
fi
if ! [[ "$TERMINAL_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}❌ El número de terminal debe ser un número${NC}"
    exit 1
fi

if [ -z "$SERVER_IP" ]; then
    echo -e "${RED}❌ Debes proporcionar la IP del servidor${NC}"
    exit 1
fi
if [ -z "$ADMIN_TOKEN" ]; then
    echo -e "${RED}❌ Debes proporcionar el token admin del gateway${NC}"
    exit 1
fi
if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}❌ Debes proporcionar la contraseña de PostgreSQL central${NC}"
    exit 1
fi

GATEWAY_URL="http://$SERVER_IP:8888"

#───────────────────────────────────────────────────────────────────────────────
# PASO 1: Actualizar sistema
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[1/6] 📦 Actualizando sistema...${NC}"
sudo apt update && sudo apt upgrade -y
echo -e "${GREEN}✅ Sistema actualizado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 2: Instalar dependencias para TITAN POS
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[2/6] 🔧 Instalando dependencias...${NC}"
sudo apt install -y \
    python3 \
    python3-pip \
    python3-pyqt6 \
    python3-venv \
    git \
    curl \
    jq \
    unzip \
    libcups2-dev \
    cups
echo -e "${GREEN}✅ Dependencias instaladas${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 3: Instalar y conectar Tailscale
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[3/6] 🔒 Configurando Tailscale VPN...${NC}"

if command -v tailscale &> /dev/null; then
    echo -e "${GREEN}✅ Tailscale ya instalado${NC}"
else
    curl -fsSL https://tailscale.com/install.sh | sh
    echo -e "${GREEN}✅ Tailscale instalado${NC}"
fi

# Verificar si ya está conectado
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")

if [ -z "$TAILSCALE_IP" ]; then
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}📡 CONECTAR TAILSCALE${NC}"
    echo ""
    echo "   Se abrirá una URL de autenticación."
    echo "   1. Copia la URL que aparecerá"
    echo "   2. Ábrela en tu navegador"
    echo "   3. Inicia sesión con tu cuenta Tailscale"
    echo "   4. El script continuará automáticamente"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Ejecutar tailscale up en background y mostrar la URL
    sudo tailscale up &
    TS_PID=$!
    
    # Esperar a que tenga IP (máximo 5 minutos)
    echo -e "${YELLOW}⏳ Esperando conexión de Tailscale...${NC}"
    for i in {1..150}; do
        TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
        if [ -n "$TAILSCALE_IP" ]; then
            echo ""
            echo -e "${GREEN}✅ ¡Tailscale conectado!${NC}"
            break
        fi
        sleep 2
        # Mostrar progreso cada 10 segundos
        if [ $((i % 5)) -eq 0 ]; then
            echo -n "."
        fi
    done
    
    # Esperar a que termine el proceso de tailscale up
    wait $TS_PID 2>/dev/null || true
fi

# Verificar conexión final
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
if [ -n "$TAILSCALE_IP" ]; then
    echo -e "${GREEN}✅ Tailscale conectado: ${BLUE}$TAILSCALE_IP${NC}"
else
    echo -e "${YELLOW}⚠️ Tailscale no conectado. Ejecuta 'sudo tailscale up' después.${NC}"
fi

#───────────────────────────────────────────────────────────────────────────────
# PASO 4: Registrar sucursal en el Gateway
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[4/6] 🌐 Registrando sucursal en el servidor central...${NC}"

BRANCH_TOKEN=""

# Verificar conexión al servidor
if curl -s --connect-timeout 5 "$GATEWAY_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Servidor alcanzable${NC}"
    
    # Registrar sucursal
    REGISTER_RESPONSE=$(curl -s -X POST "$GATEWAY_URL/api/branches/register" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "{\"branch_id\": $BRANCH_ID, \"branch_name\": \"$BRANCH_NAME\", \"terminal_id\": $TERMINAL_ID, \"tailscale_ip\": \"$TAILSCALE_IP\"}" 2>/dev/null || echo "")
    
    if echo "$REGISTER_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
        BRANCH_TOKEN=$(echo "$REGISTER_RESPONSE" | jq -r '.token')
        echo -e "${GREEN}✅ Sucursal registrada exitosamente${NC}"
        echo -e "   Token: ${BLUE}${BRANCH_TOKEN:0:20}...${NC}"
    else
        echo -e "${YELLOW}⚠️ No se pudo registrar automáticamente. Puede que ya exista.${NC}"
        echo "   Respuesta: $REGISTER_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠️ No se puede conectar al servidor $GATEWAY_URL${NC}"
    echo "   Verifica que Tailscale esté conectado y el servidor esté activo."
    echo "   Podrás configurar la conexión manualmente después."
fi

#───────────────────────────────────────────────────────────────────────────────
# PASO 5: Crear estructura y configuración
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[5/6] 📁 Configurando TITAN POS...${NC}"

mkdir -p $TITAN_DIR/{data,data/config,backups,logs}

# Buscar y copiar TITAN POS
TITAN_ZIP=""
for file in "$SCRIPT_DIR"/TITAN_POS*.zip "$HOME"/TITAN_POS*.zip; do
    if [ -f "$file" ]; then
        TITAN_ZIP="$file"
        break
    fi
done

if [ -n "$TITAN_ZIP" ]; then
    unzip -qo "$TITAN_ZIP" -d $TITAN_DIR/
    echo -e "${GREEN}✅ TITAN POS extraído${NC}"
else
    echo -e "${YELLOW}⚠️ TITAN POS no encontrado. Cópialo manualmente.${NC}"
fi

# Crear archivo de configuración de base de datos remoto
cat > $TITAN_DIR/data/config/database.json << EOF
{
    "postgresql": {
        "host": "$SERVER_IP",
        "port": 5432,
        "database": "titan_pos",
        "user": "titan",
        "password": "$DB_PASSWORD"
    }
}
EOF

# Crear archivo de configuración COMPLETO
cat > $TITAN_DIR/data/config/config.json << EOF
{
    "branch_id": $BRANCH_ID,
    "branch_name": "$BRANCH_NAME",
    "terminal_id": $TERMINAL_ID,
    "central_enabled": true,
    "central_url": "$GATEWAY_URL",
    "central_token": "$BRANCH_TOKEN",
    "auto_sync_enabled": false,
    "sync_interval": 30,
    "sync_sales": false,
    "sync_inventory": false,
    "sync_customers": false,
    "sync_products": false,
    "heartbeat_enabled": true,
    "heartbeat_interval": 60,
    "tailscale_ip": "$TAILSCALE_IP",
    "installed_date": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

echo -e "${GREEN}✅ Configuración guardada${NC}"

# Crear script de inicio (buscar el archivo principal)
MAIN_FILE=""
for f in "TITAN_POS.py" "main.py" "app/main.py" "run.py"; do
    if [ -f "$TITAN_DIR/$f" ]; then
        MAIN_FILE="$f"
        break
    fi
done
[ -z "$MAIN_FILE" ] && MAIN_FILE="TITAN_POS.py"

cat > $TITAN_DIR/iniciar.sh << EOF
#!/bin/bash
cd ~/titan-pos
python3 $MAIN_FILE
EOF
chmod +x $TITAN_DIR/iniciar.sh

# Crear acceso directo en escritorio
DESKTOP_FILE="$HOME/Desktop/TITAN-POS.desktop"
mkdir -p "$HOME/Desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=TITAN POS - $BRANCH_NAME
Comment=Punto de Venta TITAN - Sucursal $BRANCH_NAME
Exec=$TITAN_DIR/iniciar.sh
Icon=applications-office
Terminal=false
Categories=Office;
EOF
chmod +x "$DESKTOP_FILE"

echo -e "${GREEN}✅ TITAN POS configurado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 6: Instalar dependencias Python
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[6/6] 🐍 Instalando dependencias Python...${NC}"

cd $TITAN_DIR
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || \
    pip3 install -r requirements.txt
fi

# Instalar dependencias básicas
pip3 install --break-system-packages PyQt6 requests aiohttp python-dateutil 2>/dev/null || \
pip3 install PyQt6 requests aiohttp python-dateutil

echo -e "${GREEN}✅ Dependencias Python instaladas${NC}"

#───────────────────────────────────────────────────────────────────────────────
# FINALIZACIÓN
#───────────────────────────────────────────────────────────────────────────────
IP_LOCAL=$(hostname -I | awk '{print $1}')
HOSTNAME_LOCAL=$(hostname)

# Crear archivo de información
cat > $TITAN_DIR/SUCURSAL_INFO.txt << EOF
╔═══════════════════════════════════════════════════════════════════╗
║              TITAN POS - INFORMACIÓN DE SUCURSAL                  ║
╚═══════════════════════════════════════════════════════════════════╝

   ID Sucursal:        $BRANCH_ID
   Nombre:             $BRANCH_NAME
   Terminal/Caja:      $TERMINAL_ID
   
   Hostname:           $HOSTNAME_LOCAL
   IP Local:           $IP_LOCAL
   IP Tailscale:       $TAILSCALE_IP
   
   Servidor Central:   $GATEWAY_URL
   Token:              ${BRANCH_TOKEN:0:20}...
   
   Instalación:        $(date '+%Y-%m-%d %H:%M:%S')

═══════════════════════════════════════════════════════════════════
                         COMANDOS
═══════════════════════════════════════════════════════════════════
   Iniciar TITAN POS:     $TITAN_DIR/iniciar.sh
   Reconectar Tailscale:  sudo tailscale up
   Ver IP Tailscale:      tailscale ip -4

═══════════════════════════════════════════════════════════════════
EOF

echo -e "\n${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║              ✅ INSTALACIÓN COMPLETADA                            ║"
echo "║                                                                    ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}📋 INFORMACIÓN DE LA SUCURSAL:${NC}"
echo ""
echo "   🏪 Sucursal:     #$BRANCH_ID - $BRANCH_NAME"
echo "   🖥️  Terminal:     $TERMINAL_ID"
echo "   📡 IP Local:     $IP_LOCAL"
echo "   🔐 IP Tailscale: $TAILSCALE_IP"
echo "   🌐 Servidor:     $GATEWAY_URL"
echo ""

if [ -n "$BRANCH_TOKEN" ]; then
    echo -e "${GREEN}✅ SUCURSAL REGISTRADA Y CONECTADA AL SERVIDOR${NC}"
    echo ""
    echo "   La sucursal ya está configurada para sincronizar con el servidor."
    echo "   Solo necesitas iniciar TITAN POS."
else
    echo -e "${YELLOW}⚠️ CONFIGURACIÓN PENDIENTE${NC}"
    echo ""
    echo "   1. Verifica que Tailscale esté conectado: sudo tailscale up"
    echo "   2. Ve a Settings → Multi-Sucursal y configura manualmente"
fi

echo ""
echo -e "${BLUE}▶ Para iniciar TITAN POS:${NC}"
echo ""
echo "   $TITAN_DIR/iniciar.sh"
echo "   O usa el acceso directo en el escritorio"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}📄 Información guardada en: ${BLUE}$TITAN_DIR/SUCURSAL_INFO.txt${NC}"
echo ""
