# Instrucciones para distribución — POSVENDELO

Guía para quien publica y distribuye POSVENDELO (releases, instaladores y nodos de sucursal).

---

## 1. Antes de distribuir (checklist)

- [ ] **Tests en verde:** backend, control-plane y frontend (ver `CLAUDE.md` / `AGENTS.md`).
- [ ] **Migraciones aplicadas** en entorno de prueba (backend 045, control-plane 002 si aplica).
- [ ] **Control-plane en marcha** y accesible (URL pública o túnel) para que los instaladores de nodo puedan descargar `bootstrap-config` y `compose-template`.
- [ ] **Al menos un tenant y una sucursal** creados en el control-plane, con **install token** generado para nuevas instalaciones.
- [ ] **Versión decidida** (ej. `1.0.0`). El tag será `v1.0.0`.

---

## 2. Publicar una release (generar instaladores)

Los instaladores de la **app de caja** (Windows .exe, Linux AppImage/deb/snap) se generan con GitHub Actions al hacer **push de un tag** `v*`.

### Pasos

1. **Fusionar** en `master` todo lo que quieras incluir en la release.

2. **Crear y subir el tag:**
   ```bash
   git checkout master
   git pull origin master
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Esperar al workflow** en GitHub: **Actions** → workflow "POSVENDELO Release Artifacts".  
   - Construye Linux y Windows.  
   - Crea el **Release** en la pestaña **Releases** con los archivos adjuntos y `SHA256SUMS.txt`.

4. **Revisar el Release** en:  
   `https://github.com/<ORG>/<REPO>/releases/tag/v1.0.0`  
   Ahí estarán los instaladores listos para distribución.

### Opcional: publicar versión en el control-plane

Si tienes configurados los secrets del repo (`CP_RELEASES_PUBLISH_URL`, `CP_RELEASES_TOKEN`), el mismo workflow envía la versión al control-plane para que los nodos instalados puedan ver actualizaciones. Si no están configurados, el workflow no falla; solo no publica en el control-plane.

---

## 3. Qué repartir y a quién

### A) Cajeros (solo app de escritorio)

**Qué dar:** el instalador del Release, nada más.

| Plataforma | Archivo (ej. v1.0.0) | Enlace |
|------------|----------------------|--------|
| Windows    | `posvendelo-1.0.0-setup.exe` | Descargar desde el Release de GitHub |
| Linux      | `posvendelo-1.0.0.AppImage` o `posvendelo_1.0.0_amd64.deb` | Idem |

**Instrucciones para el cajero:**

- **Windows:** Descargar el `.exe`, ejecutarlo y seguir el asistente. La app se conecta al nodo de la sucursal (IP/puerto o URL que ya esté configurada en la red).
- **Linux:** Descargar el AppImage, `chmod +x posvendelo-1.0.0.AppImage`, ejecutarlo. O instalar el `.deb` con el gestor de paquetes.

No hace falta clonar el repo ni tener el código. Solo el instalador.

---

### B) Sucursales (nodo completo: API + DB + agente)

Aquí se instala el **nodo** en una máquina (servidor o PC) que tendrá el backend, la base de datos y el agente. Las terminales de caja se conectan a ese nodo.

**Qué dar:**

1. **URL del control-plane** (ej. `https://titan.ejemplo.com`).
2. **Install token** de la sucursal (generado en el control-plane para esa sucursal).
3. **Enlace al script de instalación** (o el script en un archivo).

**Opciones para el instalador del nodo:**

- **Opción 1 – Descargar el script desde GitHub (recomendado)**  
  El responsable de la sucursal descarga solo el script y lo ejecuta (no clona el repo):

  **Linux:**
  ```bash
  curl -fsSL -o install-titan.sh \
    "https://raw.githubusercontent.com/<ORG>/<REPO>/master/installers/linux/install-titan.sh"
  chmod +x install-titan.sh
  bash install-titan.sh --cp-url https://tu-control-plane.ejemplo.com --install-token TOKEN_QUE_LE_DISTE
  ```

  **Windows (PowerShell):**
  ```powershell
  Invoke-WebRequest -Uri "https://raw.githubusercontent.com/<ORG>/<REPO>/master/installers/windows/Install-Titan.ps1" -OutFile Install-Titan.ps1
  powershell -ExecutionPolicy Bypass -File .\Install-Titan.ps1 -CpUrl https://tu-control-plane.ejemplo.com -InstallToken TOKEN_QUE_LE_DISTE
  ```

- **Opción 2 – Enviar el script por correo/Drive**  
  Descargas tú el script desde el repo y lo envías; ellos lo ejecutan con su `--cp-url` y `--install-token`.

- **Opción 3 – Clonar el repo solo para tener el script**  
  Si prefieren tener el repo: `git clone`, entrar en la carpeta, ejecutar el script desde `installers/linux/` o `installers/windows/`. Luego pueden borrar el clon.

Tras la instalación, en la máquina del nodo quedan `.env`, `docker-compose.yml`, `titan-agent.json` e `INSTALL_SUMMARY.txt`. Las **terminales de caja** (instaladores del punto A) se configuran para apuntar a la IP/puerto de ese nodo (según tu red y cómo expongas el API).

---

## 4. Resumen rápido

| Destinatario   | Qué distribuyes                                      | Origen                    |
|----------------|------------------------------------------------------|---------------------------|
| Cajeros        | Instalador .exe (Windows) o .AppImage/.deb (Linux)   | GitHub Release (tag v*)   |
| Sucursal (nodo)| URL del control-plane + install token + script      | Script desde repo/Release |
| Desarrolladores| Repo completo                                        | `git clone`               |

---

## 5. Enlaces útiles (sustituir ORG y REPO)

- **Releases:** `https://github.com/<ORG>/<REPO>/releases`
- **Script Linux (raw):** `https://raw.githubusercontent.com/<ORG>/<REPO>/master/installers/linux/install-titan.sh`
- **Script Windows (raw):** `https://raw.githubusercontent.com/<ORG>/<REPO>/master/installers/windows/Install-Titan.ps1`

Para más detalle para quien **recibe** la distribución (instalación en equipo nuevo), ver **`docs/distribucion/INSTALACION_EQUIPOS.md`**.
