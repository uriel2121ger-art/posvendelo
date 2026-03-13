# Instalación en equipos nuevos (sucursales / cajeros)

Tres formas de dejar POSVENDELO listo en equipos nuevos. **No hace falta clonar el repo** para instalar en una sucursal o cajero.

---

## 1. Descargar instalador del Release (recomendado para cajeros)

Cuando publiques un **tag** `v*` (ej. `v1.0.0`), GitHub Actions genera los artefactos y los sube al **GitHub Release**.

**En un equipo nuevo (cajero / sucursal):**

- **Windows:** Descargar desde el Release el archivo `posvendelo-X.X.X-setup.exe` y ejecutarlo. No se necesita repo ni ZIP del código.
- **Linux (PC):** Descargar el `.AppImage` o el `.deb` (amd64) del Release; dar permisos de ejecución (AppImage) o instalar el .deb.
- **Raspberry Pi (64-bit):** No uses el .deb de PC (amd64). Descarga el **.deb arm64** (en la landing: "Raspberry Pi (.deb)" o desde `/download/cajero/deb/arm64`). Luego: `sudo dpkg -i posvendelo_arm64.deb` y si pide dependencias: `sudo apt -f install`. Si en la landing no aparece aún, genera el paquete con `cd frontend && npm run build:linux:arm64` y publica el `posvendelo_arm64.deb`.

No se usa ZIP del repo ni clonación. Solo el instalador de la app de escritorio (POS para cajeros).

Para que el nodo (API + base de datos) esté en esa misma máquina, sigue la opción 2.

---

## 2. Instalar el nodo con el script (sucursal con Control Plane)

En la máquina donde quieres el **nodo de sucursal** (backend + DB + agente):

**No hace falta clonar el repo.** Basta con tener el script de instalación y la URL + token del control-plane.

### Opción A – Descargar solo el script (sin clonar)

- Descargar el script desde el repo (raw):
  - Linux: `installers/linux/install-posvendelo.sh`
  - Windows: `installers/windows/Install-Posvendelo.ps1`
- Ejecutarlo pasando la URL del control-plane y el token que te dio el administrador.

Ejemplo Linux (con curl, sin git):

```bash
curl -fsSL -o install-posvendelo.sh \
  "https://raw.githubusercontent.com/<ORG>/<REPO>/master/installers/linux/install-posvendelo.sh"
chmod +x install-posvendelo.sh
bash install-posvendelo.sh --cp-url https://tu-control-plane.ejemplo.com --install-token TOKEN_QUE_TE_DIERON
```

Ejemplo Windows (PowerShell, descargando el script):

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/<ORG>/<REPO>/master/installers/windows/Install-Posvendelo.ps1" -OutFile Install-Posvendelo.ps1
powershell -ExecutionPolicy Bypass -File .\Install-Posvendelo.ps1 -CpUrl https://tu-control-plane.ejemplo.com -InstallToken TOKEN_QUE_TE_DIERON
```

El script descarga del control-plane el `docker-compose` y la configuración; genera `.env`, `posvendelo-agent.json` e `INSTALL_SUMMARY.txt`. Además crea un icono en el escritorio (y en el menú en Linux) para abrir el POS o la página de descargas. En esa máquina no necesitas el código fuente.

### Opción B – Clonar solo para tener los scripts

Si prefieres tener el repo:

```bash
git clone --depth 1 https://github.com/<ORG>/<REPO>.git posvendelo-install
cd posvendelo-install
bash installers/linux/install-posvendelo.sh --cp-url <URL> --install-token <TOKEN>
```

Después puedes borrar la carpeta clonada; el nodo queda en el directorio de instalación que el script indique (por defecto `/opt/posvendelo` en Linux).

---

## 3. Clonar el repo completo (desarrolladores / CI)

Solo si vas a **desarrollar, hacer build o correr tests**:

```bash
git clone https://github.com/<ORG>/<REPO>.git
cd <REPO>
# Configurar .env, instalar deps, etc.
```

Para **solo instalar** en una sucursal o cajero, la opción 1 (Release) + opción 2 (script) son suficientes; no hace falta clonar.

---

## Resumen

| Escenario              | Qué usar                          | ¿Clonar repo? |
|------------------------|------------------------------------|----------------|
| Cajero: solo app POS   | Descargar .exe / .AppImage del Release | No            |
| Sucursal: nodo completo| Script de instalación + URL + token   | No (o solo para bajar el script) |
| Desarrollo / CI        | Clonar repo                        | Sí            |

**Deploy de releases:** En el repo, crear un tag (ej. `v1.0.0`) y hacer push. El workflow de GitHub Actions construye los instaladores y los publica en el Release. Los equipos nuevos descargan desde ahí (opción 1 o 2 según corresponda).
