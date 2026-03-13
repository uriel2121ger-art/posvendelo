# Auditoría homelab 192.168.10.90 — 2026-03-13

Ejecutada por SSH (solo lectura; no se eliminó nada). Referencia: [AUDITORIA_HOMELAB.md](../operacion/AUDITORIA_HOMELAB.md).

---

## Resumen

| Área | Estado | Notas |
|------|--------|-------|
| Conectividad SSH | OK | Conexión a 192.168.10.90 correcta |
| Docker | OK | Contenedores control-plane y titan-pos Up |
| Control-plane health | OK | Local 127.0.0.1:9090 y público (posvendelo.com) responden |
| Puertos | OK | 9090 y 5435 en 127.0.0.1 (no expuestos a LAN) |
| Disco | Atención | 86 % uso (80G/98G); 14G libres |
| Memoria | OK | ~12 Gi disponibles |
| Downloads | OK | Carpeta con .deb, AppImage, .exe, APK |
| Logs API | OK | Sin errores en últimas 200 líneas |

---

## 1. Contenedores Docker (relevantes POSVENDELO)

| Nombre | Estado | Puertos |
|--------|--------|---------|
| posvendelo-control-plane-api-1 | Up About an hour (healthy) | 127.0.0.1:9090->9090/tcp |
| posvendelo-control-plane-db-1 | Up About an hour (healthy) | 127.0.0.1:5436->5432/tcp |
| posvendelo-control-plane-redis-1 | Up About an hour | 6379/tcp |
| titan-pos-api-1 | Up 10 minutes (healthy) | 0.0.0.0:8000->8000/tcp |
| titan-pos-postgres-1 | Up 3 days (healthy) | 127.0.0.1:5434->5432/tcp |
| titan-pos-watchtower-1 | Up 3 days (healthy) | 8080/tcp |
| titan-cp-tunnel | Up 2 days | — |

Otros servicios en el homelab: uptime-kuma, n8n, catalogo-pro-*, portainer, netdata, homepage, vaultwarden, hbbs, hbbr.

---

## 2. Health control-plane

- **Local:** `curl http://127.0.0.1:9090/health` → `{"success":true,"data":{"status":"healthy","service":"posvendelo-control-plane","version":"1.0.0"}}`
- **Público:** `https://posvendelo.com/health` → 200 OK (comprobado desde fuera).

---

## 3. Puertos en escucha

- `127.0.0.1:9090` — API control-plane.
- `127.0.0.1:5435` — PostgreSQL (catalogo-pro-db; el control-plane DB usa 5436).

Sensibles correctamente acotados a localhost.

---

## 4. Disco y memoria

- **Disco:** `/` 98G total, 80G usados, 14G libres (**86 % uso**). Recomendación: vigilar; no se ejecutó prune ni borrado (por indicación de no eliminar nada).
- **Docker system df:** Imágenes 45.78GB (reclaimable 40.98GB); build cache 52.92GB (reclaimable 43.31GB). Opcional en el futuro: `docker system prune` cuando decidas liberar espacio.
- **Memoria:** 15G total, ~12G disponibles. OK.

---

## 5. Carpeta downloads (control-plane)

- **Ruta en el servidor:** `/home/uriel/posvendelo-control-plane/downloads/`
- **Bind mount en el contenedor:** `/app/downloads`
- **Contenido:** .deb (amd64, arm64), AppImage, .exe (setup, owner), APK (cajero, owner), scripts Install-Posvendelo.ps1 e install-posvendelo.sh, README.md, symlinks a latest. Permisos propietario uriel.

---

## 6. Logs API control-plane

- Últimas 25 líneas: peticiones `/health` 200 OK y 404 a rutas wp-* (escaneos externos, esperables).
- Búsqueda de "error|exception|traceback|failed" en últimas 200 líneas: **ninguno encontrado**.

---

## 7. Checklist (AUDITORIA_HOMELAB.md)

- [x] SSH a 192.168.10.90 funciona.
- [x] Docker en ejecución; contenedores control-plane (api, db, redis) Up.
- [x] Watchtower (titan-pos-watchtower-1) Up.
- [x] Health local 127.0.0.1:9090 OK.
- [x] Health público posvendelo.com OK.
- [x] Puertos 9090 y 5435 en 127.0.0.1.
- [x] Memoria suficiente.
- [x] Carpeta downloads existe y con artefactos.
- [x] Logs API sin errores críticos recientes.
- [ ] Disco: 86 % uso — vigilar; no se eliminó nada en esta auditoría.

---

*Auditoría ejecutada por SSH en modo solo lectura. No se usó sudo ni se eliminó ningún dato.*
