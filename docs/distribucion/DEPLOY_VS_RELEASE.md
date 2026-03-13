# Deploy vs release: qué se construye y cuándo

Para no quedarse solo en “frontend”: el **backend** y el **resto** (control-plane, owner-app, instaladores) se actualizan en flujos distintos.

---

## Resumen rápido

| Acción | Backend (imagen Docker) | Frontend (instaladores) | Control-plane / subida |
|--------|------------------------|--------------------------|--------------------------|
| **Push a `master`** | Sí: se construye y se sube a GHCR | No | No |
| **Push de tag `v*`** (ej. `v1.0.1`) | Sí + se registra en CP | Sí (Linux + Windows + Android) | Sí: artefactos subidos al control-plane |
| **Build local** (`npm run build:linux` / `build:win`) | No | Solo lo que ejecutes en `frontend/` | No |

---

## 1. Push a `master` (deploy diario)

**Workflow:** `.github/workflows/deploy.yml`

- **Backend:** se construye la imagen Docker desde `backend/` y se sube a GHCR (`ghcr.io/<repo>/posvendelo:latest`, etc.). Los nodos que hacen `docker compose pull` (o Watchtower) reciben esta imagen. **No hay “instalador” de backend:** es una imagen que usa el nodo vía Docker.
- **Lint y tests:** se ejecutan (incluidos tests del backend).
- **Frontend / instaladores:** no se construyen en este workflow.
- **Control-plane:** no se sube nada; el control-plane ya está desplegado en tu servidor (homelab, posvendelo.com, etc.).

Por eso, al hacer solo **commit + push**, ya estás desplegando **backend**. Lo que no se regenera en ese flujo son los instaladores de la app de escritorio ni la subida al control-plane.

---

## 2. Push de tag `v*` o “Run workflow” (release completa)

**Workflow:** `.github/workflows/release.yml`  
**Se dispara con:** `git tag v1.0.1 && git push origin v1.0.1` o desde GitHub Actions → “Run workflow”.

Aquí sí se hace **todo**:

1. **Backend:** build de la imagen Docker, push a GHCR y **registro en el control-plane** (versión, `target_ref`, etc.).
2. **Frontend Linux:** AppImage + .deb; se **suben al control-plane** (y opcionalmente a GitHub Release).
3. **Frontend Windows:** instalador NSIS (.exe); se **sube al control-plane** (y opcionalmente a GitHub Release).
4. **Frontend Android:** APK de cajero (si está configurado en el workflow).

Es decir: **backend + instaladores + subida al control-plane** se regeneran y publican en este flujo.

---

## 3. Build solo en `frontend/` (local)

Cuando ejecutas en tu máquina:

- `cd frontend && npm run build:linux` → genera .deb, AppImage, snap en `frontend/dist/`.
- `cd frontend && npm run build:win` → genera el .exe en `frontend/dist/`.

Eso **no** construye el backend ni sube nada al control-plane. Sirve para tener instaladores locales o probar; para que los clientes los reciban vía control-plane (o homelab), hace falta usar el **release** (tag o “Run workflow”) o subir a mano los archivos de `frontend/dist/` al servidor de descargas.

---

## 4. “Lo demás”: control-plane, owner-app

- **Control-plane:** es un servicio (Python/FastAPI) que sueles desplegar en un servidor (homelab 192.168.10.90, posvendelo.com, etc.). No se “regenera” como instalador de usuario; se actualiza desplegando esa app (Docker, systemd, etc.) cuando cambies su código o imagen.
- **Owner-app:** tiene su propio build (`owner-app/`: `build:linux`, `build:win`). El workflow de **release** actual solo incluye el frontend del **cajero** (app de escritorio). Si quieres que la owner-app también se construya y se suba en cada release, hay que añadir un job en `release.yml` que haga build de `owner-app/` y suba sus artefactos.

---

## Qué hacer según lo que quieras actualizar

| Objetivo | Acción |
|----------|--------|
| **Solo backend** (cambios en API, lógica, Docker) | `git push origin master`. El deploy construye y sube la imagen a GHCR. |
| **Backend + instaladores cajero + que el control-plane los sirva** | Crear tag y push: `git tag v1.0.1 && git push origin v1.0.1`. O ejecutar el workflow “Release Artifacts” manualmente. |
| **Solo instaladores locales** (probar .deb / .exe sin subir) | `cd frontend && npm run build:linux` y/o `npm run build:win`. |
| **Control-plane** (cambios en ese servicio) | Desplegar el control-plane en tu servidor (compose, script, etc.). |
| **Owner-app** en el release | Añadir job en `release.yml` que haga build de `owner-app/` y suba los artefactos donde corresponda. |

Referencias: [FLUJO_ACTUALIZACION_CLIENTE.md](FLUJO_ACTUALIZACION_CLIENTE.md), [HOMELAB.md](../operacion/HOMELAB.md).
