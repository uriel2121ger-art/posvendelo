# Homelab — Servidor central (nodo central)

**Objetivo:** Documentar el servidor central (homelab) donde corre el control-plane, Watchtower y la carpeta de descargas. **IP del servidor central: 192.168.10.90**

---

## 1. Identificación del homelab

| Concepto | Valor / Notas |
|----------|----------------|
| **IP del servidor central** | `192.168.10.90` (homelab / nodo central) |
| **Alias SSH** | `prod` (usado en `deploy.yml` y en esta doc) |
| **Hostname opcional** | `homelab.local` o el que tengas en `/etc/hosts` / DNS |

Configura en `~/.ssh/config` (ejemplo):

```
Host prod
  HostName 192.168.10.90
  User tu_usuario
  # IdentityFile ~/.ssh/id_ed25519_posvendelo
```

Así los comandos de esta doc con `ssh prod` apuntan al homelab .90.

---

## 2. Servicios en el homelab

| Servicio | Puerto / Contenedor | Descripción |
|----------|----------------------|-------------|
| **Control-plane** | `127.0.0.1:9090` (interno), expuesto vía Cloudflare Tunnel en `https://posvendelo.com` | API bootstrap, licencias, tenants, releases, downloads |
| **Watchtower** | Contenedor `posvendelo-watchtower-1` | Auto-pull de `ghcr.io/uriel2121ger-art/posvendelo:latest` y redeploy del backend en nodos |
| **Downloads** | Bind mount `control-plane/downloads` | `.deb`, AppImage, `.exe`, APK servidos por el control-plane en `/downloads` |

El control-plane usa **puerto 9090** (`CP_PORT`, ver `control-plane/docker-compose.yml`). El túnel CF expone ese servicio como `posvendelo.com`.

---

## 3. Flujo de despliegue

### 3.1 Backend (imagen Docker)

- **GitHub Actions** (`deploy.yml`): en push a `master` se construye y sube la imagen a GHCR como `:latest`.
- **Homelab:** Watchtower hace pull periódico (intervalo configurado en el homelab, ej. 15–30 min). Los nodos POS que usan esa imagen se actualizan al reiniciar el contenedor.
- **Forzar actualización inmediata** (desde tu máquina, con acceso SSH al homelab):

  ```bash
  ssh prod 'docker exec posvendelo-watchtower-1 /watchtower --run-once'
  ```

### 3.2 Artefactos de frontend e instaladores

Los artefactos (`.deb`, AppImage, `.exe`, APK) se suben al control-plane de dos formas:

1. **Release con tag `v*`** (`.github/workflows/release.yml`): se suben vía API a `https://posvendelo.com` (control-plane detrás del túnel). No necesitas la IP .90; el control-plane recibe los archivos por HTTPS.
2. **Copia manual al homelab** (cuando quieras probar builds locales en la landing de descargas):

  ```bash
  export HOMELAB_HOST="${HOMELAB_HOST:-192.168.10.90}"
  cd frontend && npm run build:linux
  scp dist/posvendelo_amd64.deb "user@${HOMELAB_HOST}:/ruta/en/homelab/control-plane/downloads/"
  scp dist/posvendelo.AppImage "user@${HOMELAB_HOST}:/ruta/en/homelab/control-plane/downloads/"
  ```

  Sustituye `user` y `/ruta/en/homelab/` por el usuario y la ruta real del repo control-plane en el homelab .90.

### 3.3 Auto-deploy local en el homelab (opcional)

En el propio servidor .90 puede existir un cron que ejecute algo como `/opt/posvendelo/auto-deploy.sh` (git pull, rebuild control-plane, copiar instaladores a `control-plane/downloads`). Ese script **no está en el repo**; vive solo en el homelab. Para tener una versión de referencia en el repo, ver `scripts/homelab-auto-deploy.example.sh`.

---

## 4. Verificación rápida

Desde tu máquina (con `prod` apuntando al homelab .90):

```bash
# Salud del control-plane (vía túnel público)
curl -s https://posvendelo.com/health

# Si tienes acceso SSH al homelab y el CP escucha en localhost:9090
ssh prod 'curl -s http://127.0.0.1:9090/health'

# Contenedor Watchtower
ssh prod 'docker ps --filter name=watchtower'
```

---

## 5. Variables y referencias en el repo

| Lugar | Uso |
|-------|-----|
| `docs/referencia/CHANGELOG_INSTALL_FLOW_2026_03_12.md` | Ejemplos con `<HOMELAB_IP>` para `scp` de artefactos |
| `.github/workflows/deploy.yml` | Comentario "Watchtower on homelab" y comando `ssh prod ...` |
| `.github/workflows/release.yml` | Subida a `CP_URL` (https://posvendelo.com); no usa IP .90 |
| `control-plane/downloads/README.md` | Indica subir `downloads/` al servidor del control-plane (homelab) |

El **servidor central (homelab)** es **192.168.10.90**. En scripts puedes usar `HOMELAB_HOST` (por defecto 192.168.10.90) o el alias SSH `prod` apuntando a esa IP.

---

## 6. Resumen

- **Homelab = servidor central 192.168.10.90**: ahí corre control-plane, Watchtower y la carpeta de descargas.
- **Alias SSH `prod`** apunta a ese host para comandos manuales y forzar Watchtower.
- **Control-plane** se expone como `https://posvendelo.com` vía Cloudflare Tunnel; releases desde GitHub suben artefactos por esa URL.
- Para copiar builds locales al homelab, usa `scp` con `HOMELAB_HOST` o `prod` y la ruta real de `control-plane/downloads` en el servidor.
