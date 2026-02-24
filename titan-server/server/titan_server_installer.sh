#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
# 🚀 TITAN POS - INSTALADOR COMPLETO PLUG & PLAY
# Compatible con: Ubuntu Server, Raspberry Pi OS, Debian
# Ejecución: chmod +x titan_server_installer.sh && ./titan_server_installer.sh
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
echo "║   ████████╗██╗████████╗ █████╗ ███╗   ██╗    ██████╗  ██████╗ ███████╗║"
echo "║      ██║   ██║   ██║   ██╔══██╗████╗  ██║    ██╔══██╗██╔═══██╗██╔════╝║"
echo "║      ██║   ██║   ██║   ███████║██╔██╗ ██║    ██████╔╝██║   ██║███████╗║"
echo "║      ██║   ██║   ██║   ██╔══██║██║╚██╗██║    ██╔═══╝ ██║   ██║╚════██║║"
echo "║      ██║   ██║   ██║   ██║  ██║██║ ╚████║    ██║     ╚██████╔╝███████║║"
echo "║      ╚═╝   ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝    ╚═╝      ╚═════╝ ╚══════╝║"
echo "║                                                                    ║"
echo "║              🖥️  INSTALADOR AUTOMÁTICO DE SERVIDOR                 ║"
echo "║                     Versión 1.0 - Enero 2026                       ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Variables
TITAN_DIR="$HOME/titan-server"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

#───────────────────────────────────────────────────────────────────────────────
# Verificaciones iniciales
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[0/10] 🔍 Verificando sistema...${NC}"

# No ejecutar como root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ No ejecutes como root. Usa tu usuario normal.${NC}"
    exit 1
fi

# Detectar arquitectura
ARCH=$(uname -m)
echo -e "   Arquitectura: ${GREEN}$ARCH${NC}"

# Detectar OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VERSION=$VERSION_ID
    echo -e "   Sistema: ${GREEN}$OS $VERSION${NC}"
fi

# Detectar si es Raspberry Pi
if grep -q "Raspberry" /proc/cpuinfo 2>/dev/null; then
    IS_RASPBERRY=true
    echo -e "   Dispositivo: ${GREEN}Raspberry Pi detectada${NC}"
else
    IS_RASPBERRY=false
fi

echo -e "${GREEN}✅ Sistema compatible${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 1: Actualizar sistema
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[1/10] 📦 Actualizando sistema...${NC}"
sudo apt update && sudo apt upgrade -y
echo -e "${GREEN}✅ Sistema actualizado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 2: Instalar dependencias
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[2/10] 🔧 Instalando dependencias...${NC}"
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    unzip \
    htop \
    net-tools \
    cifs-utils \
    ufw
echo -e "${GREEN}✅ Dependencias instaladas${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 3: Instalar Docker
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[3/10] 🐳 Instalando Docker...${NC}"

if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker ya instalado${NC}"
else
    if [ "$IS_RASPBERRY" = true ]; then
        # Método para Raspberry Pi
        curl -fsSL https://get.docker.com | sh
    else
        # Método para Ubuntu/Debian
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || \
        curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
        sudo chmod a+r /etc/apt/keyrings/docker.gpg

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        sudo apt update
        sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    fi
    
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✅ Docker instalado${NC}"
fi

sudo systemctl enable docker
sudo systemctl start docker

#───────────────────────────────────────────────────────────────────────────────
# PASO 4: Instalar Tailscale
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[4/10] 🔒 Instalando Tailscale VPN...${NC}"

if command -v tailscale &> /dev/null; then
    echo -e "${GREEN}✅ Tailscale ya instalado${NC}"
else
    curl -fsSL https://tailscale.com/install.sh | sh
    echo -e "${GREEN}✅ Tailscale instalado${NC}"
fi

#───────────────────────────────────────────────────────────────────────────────
# PASO 5: Crear estructura de directorios
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[5/10] 📁 Creando estructura...${NC}"

mkdir -p $TITAN_DIR/{data,backups,logs,homepage-config}
cd $TITAN_DIR

echo -e "${GREEN}✅ Directorios creados${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 6: Buscar y copiar TITAN POS ZIP
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[6/10] 📦 Buscando TITAN POS...${NC}"

TITAN_ZIP=""

# Buscar en el mismo directorio del script
if [ -f "$SCRIPT_DIR/TITAN_POS_v6.3.6_20260103.zip" ]; then
    TITAN_ZIP="$SCRIPT_DIR/TITAN_POS_v6.3.6_20260103.zip"
elif [ -f "$SCRIPT_DIR/../TITAN_POS_v6.3.6_20260103.zip" ]; then
    TITAN_ZIP="$SCRIPT_DIR/../TITAN_POS_v6.3.6_20260103.zip"
elif [ -f "$HOME/TITAN_POS_v6.3.6_20260103.zip" ]; then
    TITAN_ZIP="$HOME/TITAN_POS_v6.3.6_20260103.zip"
fi

if [ -n "$TITAN_ZIP" ]; then
    cp "$TITAN_ZIP" $TITAN_DIR/
    echo -e "${GREEN}✅ TITAN POS encontrado y copiado${NC}"
else
    echo -e "${YELLOW}⚠️ TITAN POS no encontrado. Cópialo manualmente a: $TITAN_DIR/${NC}"
fi

#───────────────────────────────────────────────────────────────────────────────
# PASO 7: Crear docker-compose.yml completo
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[7/10] 📝 Creando docker-compose.yml...${NC}"

cat > $TITAN_DIR/docker-compose.yml << 'EOF'
services:
  #═══════════════════════════════════════════════════════════════════════════
  # TITAN POS - CORE
  #═══════════════════════════════════════════════════════════════════════════
  gateway:
    image: python:3.11-slim
    container_name: titan-gateway
    restart: always
    ports:
      - "8888:8000"
    volumes:
      - ./TITAN_POS_v6.3.6_20260103.zip:/titan.zip:ro
      - ./data:/titan/server/gateway_data
    command: >
      bash -c "
        apt-get update -qq && apt-get install -y -qq unzip curl sqlite3 >/dev/null 2>&1
        pip install -q fastapi uvicorn pydantic python-multipart aiofiles requests
        mkdir -p /titan && cd /titan && unzip -qo /titan.zip
        cd /titan/server
        python -m uvicorn titan_gateway:app --host 0.0.0.0 --port 8000 --log-level info
      "
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

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

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: always
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=86400

  #═══════════════════════════════════════════════════════════════════════════
  # MONITOREO
  #═══════════════════════════════════════════════════════════════════════════
  uptime-kuma:
    image: louislam/uptime-kuma:latest
    container_name: uptime-kuma
    restart: always
    ports:
      - "3001:3001"
    volumes:
      - uptime-kuma_data:/app/data

  netdata:
    image: netdata/netdata:stable
    container_name: netdata
    restart: always
    ports:
      - "19999:19999"
    cap_add:
      - SYS_PTRACE
    security_opt:
      - apparmor:unconfined
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro

  dozzle:
    image: amir20/dozzle:latest
    container_name: dozzle
    restart: always
    ports:
      - "8081:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    restart: always
    ports:
      - "3000:3000"
    environment:
      - HOMEPAGE_ALLOWED_HOSTS=*
    volumes:
      - ./homepage-config:/app/config
      - /var/run/docker.sock:/var/run/docker.sock:ro

  #═══════════════════════════════════════════════════════════════════════════
  # AUTOMATIZACIÓN
  #═══════════════════════════════════════════════════════════════════════════
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_SECURE_COOKIE=false
    volumes:
      - n8n_data:/home/node/.n8n

  gotify:
    image: gotify/server:latest
    container_name: gotify
    restart: always
    ports:
      - "8082:80"
    volumes:
      - gotify_data:/app/data

  #═══════════════════════════════════════════════════════════════════════════
  # SEGURIDAD Y DESARROLLO
  #═══════════════════════════════════════════════════════════════════════════
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: always
    ports:
      - "8083:80"
    volumes:
      - vaultwarden_data:/data

  gitea:
    image: gitea/gitea:latest
    container_name: gitea
    restart: always
    ports:
      - "3003:3000"
      - "2222:22"
    volumes:
      - gitea_data:/data

  #═══════════════════════════════════════════════════════════════════════════
  # ENTRETENIMIENTO
  #═══════════════════════════════════════════════════════════════════════════
  jellyfin:
    image: jellyfin/jellyfin:latest
    container_name: jellyfin
    restart: always
    ports:
      - "8096:8096"
    volumes:
      - jellyfin_config:/config
      - jellyfin_cache:/cache

  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    restart: always
    ports:
      - "8085:8080"
      - "6881:6881"
    volumes:
      - qbittorrent_config:/config
    environment:
      - PUID=1000
      - PGID=1000

volumes:
  portainer_data:
  uptime-kuma_data:
  n8n_data:
  gotify_data:
  vaultwarden_data:
  gitea_data:
  jellyfin_config:
  jellyfin_cache:
  qbittorrent_config:

networks:
  default:
    name: titan-network
EOF

echo -e "${GREEN}✅ docker-compose.yml creado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 8: Crear configuración de Homepage
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[8/10] 🏠 Configurando Homepage dashboard...${NC}"

cat > $TITAN_DIR/homepage-config/settings.yaml << 'EOF'
title: TITAN Server
background: https://images.unsplash.com/photo-1502790671504-542ad42d5189?auto=format&fit=crop&w=2560&q=80
cardBlur: md
theme: dark
color: slate
EOF

cat > $TITAN_DIR/homepage-config/services.yaml << 'EOF'
- TITAN POS:
    - Gateway:
        href: http://localhost:8888
        description: API Central
        icon: mdi-server
    - Portainer:
        href: http://localhost:9001
        description: Docker GUI
        icon: portainer

- Monitoreo:
    - Uptime Kuma:
        href: http://localhost:3001
        icon: uptime-kuma
    - Netdata:
        href: http://localhost:19999
        icon: netdata
    - Dozzle:
        href: http://localhost:8081
        icon: dozzle

- Herramientas:
    - n8n:
        href: http://localhost:5678
        icon: n8n
    - Gitea:
        href: http://localhost:3003
        icon: gitea
    - Vaultwarden:
        href: http://localhost:8083
        icon: bitwarden

- Media:
    - Jellyfin:
        href: http://localhost:8096
        icon: jellyfin
    - qBittorrent:
        href: http://localhost:8085
        icon: qbittorrent
EOF

cat > $TITAN_DIR/homepage-config/widgets.yaml << 'EOF'
- resources:
    cpu: true
    memory: true
    disk: /
EOF

cat > $TITAN_DIR/homepage-config/bookmarks.yaml << 'EOF'
[]
EOF

cat > $TITAN_DIR/homepage-config/docker.yaml << 'EOF'
my-docker:
  socket: /var/run/docker.sock
EOF

echo -e "${GREEN}✅ Homepage configurado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 9: Configurar sistema
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[9/10] ⚙️ Configurando sistema...${NC}"

# Desactivar suspensión
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target 2>/dev/null || true

# Habilitar Docker al inicio
sudo systemctl enable docker containerd

# Configurar firewall
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 8888/tcp comment 'TITAN Gateway'
sudo ufw allow 9001/tcp comment 'Portainer'
sudo ufw allow 3000/tcp comment 'Homepage'
sudo ufw allow 3001/tcp comment 'Uptime Kuma'
sudo ufw allow 19999/tcp comment 'Netdata'
sudo ufw --force enable

echo -e "${GREEN}✅ Sistema configurado${NC}"

#───────────────────────────────────────────────────────────────────────────────
# PASO 10: Crear script de inicio
#───────────────────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[10/10] 🚀 Creando scripts de utilidad...${NC}"

# Script para iniciar todo
cat > $TITAN_DIR/start.sh << 'EOF'
#!/bin/bash
cd ~/titan-server
docker compose up -d
echo "✅ Servicios iniciados"
docker ps --format "table {{.Names}}\t{{.Status}}"
EOF
chmod +x $TITAN_DIR/start.sh

# Script para detener todo
cat > $TITAN_DIR/stop.sh << 'EOF'
#!/bin/bash
cd ~/titan-server
docker compose down
echo "✅ Servicios detenidos"
EOF
chmod +x $TITAN_DIR/stop.sh

# Script para ver logs
cat > $TITAN_DIR/logs.sh << 'EOF'
#!/bin/bash
docker logs -f ${1:-titan-gateway}
EOF
chmod +x $TITAN_DIR/logs.sh

# Script de backup
cat > $TITAN_DIR/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=~/titan-server/backups
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz ~/titan-server/data/
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +30 -delete
echo "✅ Backup completado: backup_$DATE.tar.gz"
EOF
chmod +x $TITAN_DIR/backup.sh

# Agregar backup al cron
(crontab -l 2>/dev/null | grep -v backup.sh; echo "0 3 * * * $TITAN_DIR/backup.sh >> $TITAN_DIR/logs/backup.log 2>&1") | crontab -

echo -e "${GREEN}✅ Scripts creados${NC}"

#───────────────────────────────────────────────────────────────────────────────
# FINALIZACIÓN - Generar archivo de configuración completo
#───────────────────────────────────────────────────────────────────────────────
IP_LOCAL=$(hostname -I | awk '{print $1}')
HOSTNAME_LOCAL=$(hostname)
GATEWAY_INTERFACE=$(ip route | grep default | awk '{print $5}')
GATEWAY_IP=$(ip route | grep default | awk '{print $3}')
MAC_ADDRESS=$(cat /sys/class/net/$GATEWAY_INTERFACE/address 2>/dev/null || echo "N/A")
DISK_TOTAL=$(df -h / | awk 'NR==2 {print $2}')
DISK_FREE=$(df -h / | awk 'NR==2 {print $4}')
RAM_TOTAL=$(free -h | awk '/^Mem:/ {print $2}')
CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d':' -f2 | xargs)
CPU_CORES=$(nproc)
DOCKER_VERSION=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "No conectado")
FECHA_INSTALACION=$(date '+%Y-%m-%d %H:%M:%S')

# Crear archivo de configuración completo
cat > $TITAN_DIR/SERVER_INFO.txt << SERVERINFO
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    TITAN SERVER - INFORMACIÓN COMPLETA                        ║
║                    Generado: $FECHA_INSTALACION                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════
                              🖥️ SISTEMA
═══════════════════════════════════════════════════════════════════════════════
   Hostname:           $HOSTNAME_LOCAL
   Sistema Operativo:  $OS $VERSION
   Arquitectura:       $ARCH
   CPU:                $CPU_MODEL
   Núcleos:            $CPU_CORES
   RAM Total:          $RAM_TOTAL
   Disco Total:        $DISK_TOTAL
   Disco Libre:        $DISK_FREE
   Docker:             $DOCKER_VERSION

═══════════════════════════════════════════════════════════════════════════════
                              🌐 RED
═══════════════════════════════════════════════════════════════════════════════
   IP Local:           $IP_LOCAL
   IP Tailscale:       $TAILSCALE_IP
   Gateway/Router:     $GATEWAY_IP
   Interfaz:           $GATEWAY_INTERFACE
   MAC Address:        $MAC_ADDRESS

═══════════════════════════════════════════════════════════════════════════════
                              🔌 PUERTOS Y SERVICIOS
═══════════════════════════════════════════════════════════════════════════════
   SERVICIO            PUERTO    URL
   ─────────────────────────────────────────────────────────────────────────
   Homepage            3000      http://$IP_LOCAL:3000
   TITAN Gateway       8888      http://$IP_LOCAL:8888
   Portainer           9001      http://$IP_LOCAL:9001
   Portainer HTTPS     9443      https://$IP_LOCAL:9443
   Uptime Kuma         3001      http://$IP_LOCAL:3001
   Netdata             19999     http://$IP_LOCAL:19999
   Dozzle (Logs)       8081      http://$IP_LOCAL:8081
   n8n (Automation)    5678      http://$IP_LOCAL:5678
   Gotify (Push)       8082      http://$IP_LOCAL:8082
   Vaultwarden         8083      http://$IP_LOCAL:8083
   Gitea               3003      http://$IP_LOCAL:3003
   Gitea SSH           2222      ssh://git@$IP_LOCAL:2222
   Jellyfin            8096      http://$IP_LOCAL:8096
   qBittorrent         8085      http://$IP_LOCAL:8085
   qBittorrent DHT     6881      (UDP/TCP)

═══════════════════════════════════════════════════════════════════════════════
                              🔐 CREDENCIALES POR DEFECTO
═══════════════════════════════════════════════════════════════════════════════
   ⚠️  IMPORTANTE: Cambiar estas contraseñas después de instalar

   SERVICIO            USUARIO         CONTRASEÑA
   ─────────────────────────────────────────────────────────────────────────
   qBittorrent         admin           adminadmin
   Gotify              admin           admin
   Portainer           (crear)         (crear en primer acceso)
   Uptime Kuma         (crear)         (crear en primer acceso)
   Gitea               (crear)         (crear en primer acceso)
   n8n                 (crear)         (crear en primer acceso)
   Vaultwarden         (crear)         (crear en primer acceso)
   Jellyfin            (crear)         (crear en primer acceso)

═══════════════════════════════════════════════════════════════════════════════
                              📁 DIRECTORIOS
═══════════════════════════════════════════════════════════════════════════════
   Directorio TITAN:   $TITAN_DIR
   Docker Compose:     $TITAN_DIR/docker-compose.yml
   Datos:              $TITAN_DIR/data/
   Backups:            $TITAN_DIR/backups/
   Logs:               $TITAN_DIR/logs/
   Homepage Config:    $TITAN_DIR/homepage-config/

═══════════════════════════════════════════════════════════════════════════════
                              🔧 SCRIPTS DISPONIBLES
═══════════════════════════════════════════════════════════════════════════════
   Iniciar servicios:  $TITAN_DIR/start.sh
   Detener servicios:  $TITAN_DIR/stop.sh
   Ver logs:           $TITAN_DIR/logs.sh [nombre-contenedor]
   Backup manual:      $TITAN_DIR/backup.sh

═══════════════════════════════════════════════════════════════════════════════
                              ⏰ TAREAS AUTOMÁTICAS (CRON)
═══════════════════════════════════════════════════════════════════════════════
   Backup diario:      03:00 AM → $TITAN_DIR/backups/

═══════════════════════════════════════════════════════════════════════════════
                              🔥 FIREWALL (UFW)
═══════════════════════════════════════════════════════════════════════════════
   Puertos abiertos:   22, 3000, 3001, 8888, 9001, 19999

═══════════════════════════════════════════════════════════════════════════════
                              📱 ACCESO VIA TAILSCALE
═══════════════════════════════════════════════════════════════════════════════
   IP Tailscale:       $TAILSCALE_IP
   
   Desde cualquier dispositivo conectado a Tailscale:
   • Homepage:         http://$TAILSCALE_IP:3000
   • Gateway:          http://$TAILSCALE_IP:8888
   • Portainer:        http://$TAILSCALE_IP:9001

═══════════════════════════════════════════════════════════════════════════════
                              🚀 COMANDOS ÚTILES
═══════════════════════════════════════════════════════════════════════════════
   Ver contenedores:       docker ps
   Ver logs de Gateway:    docker logs -f titan-gateway
   Reiniciar Gateway:      docker restart titan-gateway
   Ver uso de recursos:    docker stats
   Espacio de Docker:      docker system df
   Limpiar Docker:         docker system prune -a

═══════════════════════════════════════════════════════════════════════════════
                              📋 INFORMACIÓN SSH
═══════════════════════════════════════════════════════════════════════════════
   Conectar vía SSH:   ssh $USER@$IP_LOCAL
   Conectar Tailscale: ssh $USER@$TAILSCALE_IP

═══════════════════════════════════════════════════════════════════════════════
                              ⚠️ NOTAS IMPORTANTES
═══════════════════════════════════════════════════════════════════════════════
   1. Cambiar todas las contraseñas por defecto
   2. Configurar 2FA en servicios críticos
   3. Revisar logs regularmente en Dozzle
   4. Verificar backups periódicamente
   5. Mantener Docker actualizado (Watchtower lo hace automático)

═══════════════════════════════════════════════════════════════════════════════
SERVERINFO

echo -e "\n${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║              ✅ INSTALACIÓN COMPLETADA                            ║"
echo "║                                                                    ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}📋 INFORMACIÓN DEL SISTEMA:${NC}"
echo ""
echo "   🖥️  Hostname:     $HOSTNAME_LOCAL"
echo "   📡 IP Local:      $IP_LOCAL"
echo "   🔒 IP Tailscale:  $TAILSCALE_IP"
echo "   💾 Disco libre:   $DISK_FREE de $DISK_TOTAL"
echo "   🐳 Docker:        $DOCKER_VERSION"
echo ""
echo -e "${YELLOW}📌 PASOS PARA FINALIZAR:${NC}"
echo ""
echo "   1. ${CYAN}Cerrar sesión y volver a entrar${NC} (permisos Docker)"
echo ""
echo "   2. Activar Tailscale (si no lo hiciste):"
echo "      ${BLUE}sudo tailscale up${NC}"
echo ""
echo "   3. Iniciar servicios:"
echo "      ${BLUE}cd ~/titan-server && ./start.sh${NC}"
echo ""
echo -e "${GREEN}🌐 URLs (después de iniciar):${NC}"
echo ""
echo "   • 🏠 Homepage:    http://$IP_LOCAL:3000"
echo "   • 🚀 Gateway:     http://$IP_LOCAL:8888"
echo "   • 🐳 Portainer:   http://$IP_LOCAL:9001"
echo "   • 📊 Uptime Kuma: http://$IP_LOCAL:3001"
echo "   • 📈 Netdata:     http://$IP_LOCAL:19999"
echo "   • 🐳 Dozzle:      http://$IP_LOCAL:8081"
echo "   • ⚡ n8n:         http://$IP_LOCAL:5678"
echo "   • 📲 Gotify:      http://$IP_LOCAL:8082"
echo "   • 🔐 Vaultwarden: http://$IP_LOCAL:8083"
echo "   • 📁 Gitea:       http://$IP_LOCAL:3003"
echo "   • 🎬 Jellyfin:    http://$IP_LOCAL:8096"
echo "   • ⬇️  qBittorrent: http://$IP_LOCAL:8085"
echo ""
echo -e "${YELLOW}🔐 CREDENCIALES POR DEFECTO:${NC}"
echo ""
echo "   • qBittorrent:  admin / adminadmin  ⚠️ CAMBIAR"
echo "   • Gotify:       admin / admin       ⚠️ CAMBIAR"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}📄 Información completa guardada en:${NC}"
echo "   ${BLUE}$TITAN_DIR/SERVER_INFO.txt${NC}"
echo ""
echo -e "${YELLOW}⚠️ RECUERDA: Cierra sesión y vuelve a entrar antes de continuar${NC}"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
