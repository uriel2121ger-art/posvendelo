# Auditoría del homelab (servidor central 192.168.10.90)

**Objetivo:** Verificar que el servidor central (homelab) tiene los servicios esperados, recursos suficientes, configuración segura y que el control-plane responde correctamente.

**Cuándo ejecutar:** Tras un deploy, ante incidencias o de forma periódica (ej. mensual).

**Prerrequisito:** Acceso SSH al homelab (`ssh prod` con `HostName 192.168.10.90` en `~/.ssh/config`).

---

## 1. Conectividad y acceso

| Verificación | Comando | Resultado esperado |
|-------------|---------|--------------------|
| SSH al servidor central | `ssh prod 'echo OK'` | `OK` |
| Ping (opcional) | `ping -c 1 192.168.10.90` | Respuesta del host |

---

## 2. Docker y contenedores

Ejecutar **en el homelab** (o vía `ssh prod '...'`):

| Verificación | Comando | Resultado esperado |
|-------------|---------|--------------------|
| Docker en ejecución | `docker info 2>/dev/null | head -5` | Info del daemon sin error |
| Contenedores del control-plane | `docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'posvendelo|control-plane|watchtower'` | api, db, redis (y opcional watchtower) en Up |
| Contenedor API control-plane | `docker ps --filter name=api --format '{{.Names}} {{.Status}}'` | Nombre del servicio api y estado Up |
| Contenedor Watchtower | `docker ps -a --filter name=watchtower --format '{{.Names}} {{.Status}}'` | Watchtower presente y Up (si lo usas) |

**Comando resumido (copiar/pegar en el homelab):**

```bash
echo "=== Contenedores POSVENDELO / control-plane ==="
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'posvendelo|control|watchtower|api|redis|db' || docker ps -a
```

---

## 3. Control-plane: salud y puertos

| Verificación | Comando | Resultado esperado |
|-------------|---------|--------------------|
| Health local (desde el homelab) | `curl -s http://127.0.0.1:9090/health` | JSON con `"status":"ok"` o similar |
| Health vía túnel público | `curl -s https://posvendelo.com/health` | Mismo tipo de respuesta (desde cualquier máquina) |
| Puerto 9090 en escucha | `ss -tlnp | grep 9090` o `netstat -tlnp | grep 9090` | Proceso escuchando en 9090 |
| PostgreSQL (interno) | `ss -tlnp | grep 5435` | Puerto 5435 (mapeo de 5432 del contenedor) si expuesto |

**Comandos (ejecutar en el homelab):**

```bash
echo "=== Health control-plane (local) ==="
curl -s http://127.0.0.1:9090/health | head -5

echo "=== Puertos 9090 y 5435 ==="
ss -tlnp | grep -E '9090|5435'
```

---

## 4. Recursos: disco y memoria

| Verificación | Comando | Resultado esperado |
|-------------|---------|--------------------|
| Uso de disco | `df -h / /var/lib/docker 2>/dev/null` | Por debajo del 85–90 % |
| Uso de disco por Docker | `docker system df` | Sin volumen “Reclaimable” crítico si hay problemas de espacio |
| Memoria | `free -h` | Memoria disponible suficiente para API + DB + Redis |

```bash
echo "=== Disco ==="
df -h /

echo "=== Docker disk ==="
docker system df

echo "=== Memoria ==="
free -h
```

---

## 5. Seguridad básica

| Verificación | Comando / Acción | Resultado esperado |
|-------------|------------------|--------------------|
| .env no expuesto en web | Revisar que `control-plane/.env` no esté en un directorio servido por el control-plane | .env solo en el host, no en `downloads/` ni en rutas públicas |
| Puertos sensibles solo localhost | `ss -tlnp | grep -E '9090|5435'` | 127.0.0.1:9090 y 127.0.0.1:5435 (no 0.0.0.0) |
| Variables críticas definidas | `grep -E '^CP_ADMIN_TOKEN=|^CP_RELEASES_TOKEN=|^POSTGRES_PASSWORD=' control-plane/.env 2>/dev/null | sed 's/=.*/=***/'` | Las tres presentes (valores no mostrados) |

**Nota:** No ejecutar en remoto comandos que impriman secretos; comprobar solo que existan las claves.

---

## 6. Carpeta de descargas (control-plane)

| Verificación | Comando | Resultado esperado |
|-------------|---------|--------------------|
| Ruta de downloads existe | `ls -la control-plane/downloads/ 2>/dev/null || ls -la /ruta/donde/esté/control-plane/downloads/` | Directorio existe y tiene al menos los artefactos esperados (.deb, .AppImage, etc. si ya se desplegaron) |
| Permisos | `ls -ld control-plane/downloads/` | Legible por el usuario que corre el contenedor API |

```bash
echo "=== Downloads ==="
ls -la control-plane/downloads/ 2>/dev/null || true
```

---

## 7. Logs recientes (errores)

| Verificación | Comando | Resultado esperado |
|-------------|---------|--------------------|
| Errores recientes del API | `docker logs --tail 50 <nombre_contenedor_api> 2>&1 | grep -i -E 'error|exception|traceback'` | Pocos o ninguno; revisar si hay 500 o fallos de DB |
| Errores PostgreSQL | `docker logs --tail 30 <nombre_contenedor_db> 2>&1 | grep -i error` | Sin errores críticos de conexión o disco |

Sustituir `<nombre_contenedor_api>` y `<nombre_contenedor_db>` por los nombres reales (ej. `control-plane-api-1`, `control-plane-db-1`).

```bash
echo "=== Logs API (últimas 30 líneas) ==="
docker logs --tail 30 $(docker ps -q --filter 'publish=9090') 2>&1

echo "=== Errores en logs API ==="
docker logs --tail 100 $(docker ps -q --filter 'publish=9090') 2>&1 | grep -i -E 'error|exception|traceback' || echo "Ninguno"
```

---

## 8. Resumen de criterios (checklist)

Marcar tras ejecutar los comandos anteriores:

- [ ] SSH a 192.168.10.90 (o `ssh prod`) funciona.
- [ ] Docker está en ejecución y los contenedores del control-plane (api, db, redis) están Up.
- [ ] Watchtower está Up si se usa para auto-actualizar nodos.
- [ ] `curl http://127.0.0.1:9090/health` desde el homelab responde OK.
- [ ] `curl https://posvendelo.com/health` responde OK (túnel CF operativo).
- [ ] Puertos 9090 y 5435 escuchan en 127.0.0.1 (no expuestos a la LAN).
- [ ] Disco y memoria sin saturación.
- [ ] `control-plane/.env` existe y contiene CP_ADMIN_TOKEN, CP_RELEASES_TOKEN, POSTGRES_PASSWORD (sin mostrar valores).
- [ ] Carpeta `control-plane/downloads/` existe y tiene permisos correctos.
- [ ] Logs del API sin errores críticos recientes.

---

## 9. Acciones correctivas típicas

| Síntoma | Acción |
|---------|--------|
| Health falla (local o público) | `docker restart <contenedor_api>`; revisar `docker logs` y `.env`. |
| Contenedor parado | `cd control-plane && docker compose up -d` (desde el homelab). |
| Disco lleno | `docker system prune -f`; revisar logs y volúmenes; limpiar artefactos viejos en `downloads/`. |
| Watchtower no actualiza | `docker exec posvendelo-watchtower-1 /watchtower --run-once` (o nombre real del contenedor). |
| Túnel CF no responde | Revisar en Cloudflare Dashboard y proceso del túnel en el homelab. |

---

**Referencia:** [HOMELAB.md](HOMELAB.md) — identificación del servidor central y flujos de despliegue.
