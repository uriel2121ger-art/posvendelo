# 🖥️ Guía de Instalación - Servidor TITAN POS

## Requisitos del Servidor

- **OS:** Ubuntu Server 24.04 LTS
- **RAM:** Mínimo 4GB (recomendado 8GB)
- **Disco:** Mínimo 64GB SSD
- **Red:** Conexión a Internet estable

---

## Paso 1: Instalación de Ubuntu Server

Durante la instalación:
1. Idioma: Español
2. Teclado: Español (Latinoamérica)
3. Tipo de instalación: **Ubuntu Server (minimized)** - opcional para ahorrar espacio
4. Red: Configurar IP estática si es posible
5. Storage: Usar disco completo (LVM opcional)
6. Nombre de servidor: `titan-server`
7. Usuario: `titan`
8. **✅ Instalar OpenSSH Server** (IMPORTANTE)
9. Snaps: No instalar ninguno

---

## Paso 2: Primer Acceso (después de instalar)

Conectarte desde tu PC con Kubuntu:
```bash
ssh titan@<IP-DEL-SERVIDOR>
```

---

## Paso 3: Actualizar Sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

---

## Paso 4: Instalar Docker

```bash
# Dependencias
sudo apt install -y ca-certificates curl gnupg

# Agregar repositorio Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER
newgrp docker

# Verificar
docker --version
docker compose version
```

---

## Paso 5: Instalar Tailscale (VPN)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Esto te dará un enlace para autenticar. Abrelo en tu navegador.

---

## Paso 6: Crear Estructura TITAN

```bash
# Crear directorios
mkdir -p ~/titan-server/{gateway,data,backups}
cd ~/titan-server
```

---

## Paso 7: Subir TITAN POS al Servidor

Desde tu PC con Kubuntu:
```bash
scp ./TITAN_POS.tar.gz titan@<IP-SERVIDOR>:~/titan-server/
```

---

## Paso 8: Crear docker-compose.yml

```bash
cat > ~/titan-server/docker-compose.yml << 'EOF'
version: '3.8'

services:
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
        apt-get update -qq && apt-get install -y -qq unzip curl sqlite3 >/dev/null
        pip install -q fastapi uvicorn pydantic python-multipart aiofiles requests
        mkdir -p /titan && cd /titan && unzip -qo /titan.zip
        cd /titan/server
        python -m uvicorn titan_gateway:app --host 0.0.0.0 --port 8000 --log-level info
      "
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    restart: always
    ports:
      - "9001:9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data

volumes:
  portainer_data:
EOF
```

---

## Paso 9: Iniciar Servicios

```bash
cd ~/titan-server
docker compose up -d

# Verificar
docker ps
```

---

## Paso 10: Configurar Firewall

```bash
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 8888/tcp    # Gateway API
sudo ufw allow 9001/tcp    # Portainer
sudo ufw enable
```

---

## Paso 11: Verificar Todo

Desde tu PC con Kubuntu:
```bash
# Verificar Gateway
curl http://<IP-SERVIDOR>:8888/health

# Abrir Portainer en navegador
# http://<IP-SERVIDOR>:9001
```

---

## Acceso Remoto con Tailscale

Una vez que el servidor y las PCs de las sucursales tengan Tailscale:
- El servidor tendrá una IP tipo: `100.x.x.x`
- Las sucursales acceden al Gateway via: `http://100.x.x.x:8888`

---

## Comandos Útiles

```bash
# Ver logs del gateway
docker logs -f titan-gateway

# Reiniciar gateway
docker restart titan-gateway

# Ver estado de contenedores
docker ps -a

# Backup de datos
tar -czf backup_$(date +%Y%m%d).tar.gz ~/titan-server/data/
```

---

## Contacto

Creado: Enero 2026
Sistema: TITAN POS Multi-Ubicación
