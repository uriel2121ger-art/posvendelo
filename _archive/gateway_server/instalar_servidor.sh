#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
# 🚀 TITAN POS - Script de Instalación Completa del Servidor
# Ejecutar como usuario normal (no root) - pedirá sudo cuando necesite
#═══════════════════════════════════════════════════════════════════════════════

set -e  # Detener si hay error

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════════════════"
echo "   🚀 TITAN POS - Instalación del Servidor Central"
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Verificar que no sea root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ No ejecutes este script como root. Usa tu usuario normal.${NC}"
    exit 1
fi

# Variables
TITAN_DIR="$HOME/titan-server"
TITAN_ZIP_NAME="TITAN_POS_v6.3.6_20260103.zip"

#───────────────────────────────────────────────────────────────────────────────
# PASO 1: Actualizar sistema
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[1/7] 📦 Actualizando sistema...${NC}"
sudo apt update && sudo apt upgrade -y

#───────────────────────────────────────────────────────────────────────────────
# PASO 2: Instalar dependencias básicas
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[2/7] 🔧 Instalando dependencias...${NC}"
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    unzip \
    htop \
    net-tools

#───────────────────────────────────────────────────────────────────────────────
# PASO 3: Instalar Docker
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[3/7] 🐳 Instalando Docker...${NC}"

# Verificar si Docker ya está instalado
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker ya está instalado${NC}"
else
    # Agregar repositorio Docker
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Instalar Docker
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Agregar usuario al grupo docker
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}✅ Docker instalado${NC}"
fi

# Iniciar Docker
sudo systemctl enable docker
sudo systemctl start docker

#───────────────────────────────────────────────────────────────────────────────
# PASO 4: Instalar Tailscale (VPN)
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[4/7] 🔒 Instalando Tailscale...${NC}"

if command -v tailscale &> /dev/null; then
    echo -e "${GREEN}✅ Tailscale ya está instalado${NC}"
else
    curl -fsSL https://tailscale.com/install.sh | sh
    echo -e "${GREEN}✅ Tailscale instalado${NC}"
fi

#───────────────────────────────────────────────────────────────────────────────
# PASO 5: Crear estructura de directorios
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[5/7] 📁 Creando estructura de directorios...${NC}"

mkdir -p $TITAN_DIR/{data,backups,logs}
cd $TITAN_DIR

echo -e "${GREEN}✅ Directorios creados en $TITAN_DIR${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 6: Crear docker-compose.yml
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[6/7] 📝 Creando docker-compose.yml...${NC}"

cat > $TITAN_DIR/docker-compose.yml << 'COMPOSEOF'
version: '3.8'

services:
  #─────────────────────────────────────────────────────────────────────────────
  # TITAN Gateway - Servidor Central
  #─────────────────────────────────────────────────────────────────────────────
  gateway:
    image: python:3.11-slim
    container_name: titan-gateway
    restart: always
    ports:
      - "8888:8000"
    volumes:
      - ./TITAN_POS_v6.3.6_20260103.zip:/titan.zip:ro
      - ./data:/titan/server/gateway_data
    environment:
      - TZ=America/Mexico_City
    command: >
      bash -c "
        echo '🚀 Iniciando TITAN Gateway...'
        apt-get update -qq && apt-get install -y -qq unzip curl sqlite3 >/dev/null 2>&1
        pip install -q fastapi uvicorn pydantic python-multipart aiofiles requests
        mkdir -p /titan && cd /titan && unzip -qo /titan.zip
        echo '✅ TITAN POS extraído'
        cd /titan/server
        echo '🌐 Servidor iniciando en puerto 8000...'
        python -m uvicorn titan_gateway:app --host 0.0.0.0 --port 8000 --log-level info
      "
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  #─────────────────────────────────────────────────────────────────────────────
  # Portainer - GUI para Docker
  #─────────────────────────────────────────────────────────────────────────────
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    restart: always
    ports:
      - "9001:9000"
      - "9443:9443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
    environment:
      - TZ=America/Mexico_City

  #─────────────────────────────────────────────────────────────────────────────
  # Watchtower - Auto-actualización de contenedores (opcional)
  #─────────────────────────────────────────────────────────────────────────────
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: always
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - TZ=America/Mexico_City
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=86400  # Cada 24 horas

volumes:
  portainer_data:

networks:
  default:
    name: titan-network
COMPOSEOF

echo -e "${GREEN}✅ docker-compose.yml creado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 7: Configurar Firewall
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[7/7] 🔥 Configurando Firewall...${NC}"

sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 8888/tcp comment 'TITAN Gateway API'
sudo ufw allow 9001/tcp comment 'Portainer HTTP'
sudo ufw allow 9443/tcp comment 'Portainer HTTPS'
sudo ufw allow 41641/udp comment 'Tailscale'
echo "y" | sudo ufw enable || true

echo -e "${GREEN}✅ Firewall configurado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# FINALIZACIÓN
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${CYAN}"
echo "═══════════════════════════════════════════════════════════════════"
echo "   ✅ INSTALACIÓN COMPLETADA"
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Obtener IP
IP_LOCAL=$(hostname -I | awk '{print $1}')

echo -e "${GREEN}📋 RESUMEN:${NC}"
echo ""
echo "   📁 Directorio TITAN: $TITAN_DIR"
echo "   🌐 IP Local: $IP_LOCAL"
echo ""
echo -e "${YELLOW}📌 PASOS SIGUIENTES:${NC}"
echo ""
echo "   1. Copia el archivo TITAN POS al servidor:"
echo -e "      ${BLUE}scp /ruta/al/$TITAN_ZIP_NAME $USER@$IP_LOCAL:$TITAN_DIR/${NC}"
echo ""
echo "   2. Inicia Tailscale:"
echo -e "      ${BLUE}sudo tailscale up${NC}"
echo ""
echo "   3. Inicia los contenedores:"
echo -e "      ${BLUE}cd $TITAN_DIR && docker compose up -d${NC}"
echo ""
echo "   4. Accede a los servicios:"
echo "      • Gateway:   http://$IP_LOCAL:8888"
echo "      • Portainer: http://$IP_LOCAL:9001"
echo ""
echo -e "${RED}⚠️  IMPORTANTE: Cierra sesión y vuelve a entrar para que${NC}"
echo -e "${RED}   los permisos de Docker se apliquen correctamente.${NC}"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
