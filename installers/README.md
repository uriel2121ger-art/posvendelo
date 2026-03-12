# Instaladores POSVENDELO

**Estado: funcionales.** Los instaladores Linux y Windows están listos para uso: instalan el nodo (backend + Docker), crean icono/acceso directo en escritorio para abrir el POS o la página de descargas, generan `INSTALL_SUMMARY.txt` con credenciales y URLs, y los desinstaladores eliminan también los accesos directos.

---

## Linux

**Instalación para el cliente (sin tocar terminal/código):** el instalador puede ejecutarse sin argumentos. Usa por defecto el servidor central (posvendelo.com) y obtiene el token automáticamente por pre-registro (huella de hardware). El usuario solo descarga, ejecuta y configura en la app.

```bash
bash installers/linux/install-titan.sh
```

Con URL y token explícitos (pruebas o entornos custom):

```bash
bash installers/linux/install-titan.sh --cp-url https://posvendelo.com --install-token TOKEN
```

Opcional:

```bash
bash installers/linux/install-titan.sh --cp-url http://localhost:9090 --install-token TOKEN --api-port 8002 --db-port 15434
```

Desinstalacion (quita el nodo, el icono del escritorio y la entrada del menú):

```bash
bash installers/linux/uninstall-titan.sh
# Si instalaste en otro directorio:
bash installers/linux/uninstall-titan.sh /ruta/instalacion
```

Reinstalación limpia en esta PC (desinstala y vuelve a instalar; no toca el repo ni el entorno de desarrollo):

```bash
cd /home/uriel/Documentos/PUNTO\ DE\ VENTA
bash installers/linux/reinstall-titan.sh --cp-url http://localhost:9090 --install-token TU_TOKEN
# Con directorio custom:
bash installers/linux/reinstall-titan.sh --cp-url http://localhost:9090 --install-token TU_TOKEN --dir "$HOME/.titanpos"
```

Actualizar el backend (cuando publiques una nueva imagen en GHCR):

```bash
cd ~/.titanpos && ./actualizar.sh
```

Si instalaste en otro directorio: `./actualizar.sh --dir /ruta/de/instalacion`. El script hace pull de la imagen y reinicia el contenedor. Watchtower también actualiza automáticamente cada 15 minutos.

## Windows

**Instalación para el cliente (sin tocar código):** el instalador puede ejecutarse sin token ni URL. Por defecto usa posvendelo.com y obtiene el token automáticamente por pre-registro. El usuario solo descarga, ejecuta y configura en la app.

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Titan.ps1
```

Con URL y token explícitos (pruebas o entornos custom):

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Titan.ps1 -CpUrl https://posvendelo.com -InstallToken TOKEN
```

Opcional:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Titan.ps1 -CpUrl http://localhost:9090 -InstallToken TOKEN -ApiPort 8002 -DbPort 15434
```

Si usarás certificado autofirmado controlado, puedes importar confianza durante la instalación:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Titan.ps1 -CpUrl http://localhost:9090 -InstallToken TOKEN -PublisherCertPath ".\titan-selfsigned-codesign.cer"
```

Si el script instala Docker Desktop por primera vez, despues de abrir Docker Desktop continua con:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Continue-Install.ps1 -StateFile "C:\ProgramData\TitanPOS\install-state.json"
```

Desinstalacion (quita el nodo y el acceso directo del escritorio):

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Uninstall-Titan.ps1
# Si instalaste en otro directorio:
powershell -ExecutionPolicy Bypass -File .\installers\windows\Uninstall-Titan.ps1 -InstallDir "C:\Ruta\Personalizada"
```

Actualizar el backend: en el directorio de instalación (por defecto `%LOCALAPPDATA%\TitanPOS`), ejecutar `docker compose pull api` y `docker compose up -d api`, o usar la misma secuencia desde PowerShell con `--env-file .env`.

## Icono / acceso directo tras instalar

- **Linux / Raspberry Pi:** El instalador crea un icono **"POSVENDELO - Punto de venta"** en el escritorio y en el menú de aplicaciones. Doble clic abre la app si está instalada o la página de descargas si aún no tiene el .deb.
- **Windows:** El instalador crea un acceso directo **"POSVENDELO - Punto de venta"** en el escritorio. Doble clic abre la app si está instalada o la página de descargas si aún no tiene el .exe.

## Si el POS no inicia tras instalar

- **Linux / Raspberry Pi:** El instalador solo levanta el backend (Docker). Use el icono del escritorio o del menú; si la app no está instalada, descargue el .deb desde la web (en Raspberry Pi use el .deb para **arm64**, no el de amd64). Luego abra "POSVENDELO" desde el menú o ejecute `titan-pos`. Si la app no abre, ejecútela desde terminal (`titan-pos`) para ver mensajes de error.
- **Windows:** Use el icono del escritorio; si la app no está instalada, descargue el .exe desde la web. Ejecute "POSVENDELO" o "titan-pos" desde el menú Inicio. Si no inicia, ejecútela desde una consola para ver errores.
- En ambos casos, el archivo `INSTALL_SUMMARY.txt` en el directorio de instalación indica cómo abrir el POS y las credenciales iniciales (usuario `admin` y contraseña generada).

## Notas

- Los instaladores consumen `bootstrap-config` y `compose-template` del `control-plane`.
- Ambos generan `titan-agent.json` en el directorio de instalacion para que la app desktop y el agente local compartan el mismo contrato de bootstrap.
- Ambos generan `INSTALL_SUMMARY.txt` con URLs, branch y archivos clave para soporte post-instalacion.
- El `bootstrap-config` ya expone `owner_session_url`, `owner_api_base_url`, `companion_entry_url` y `quick_links` para dejar listo el acceso remoto del dueño sin tener que reconstruir rutas a mano.
- Si `8000` o `5434` ya estan ocupados, los instaladores pueden autoasignar puertos locales libres; tambien puedes fijarlos con `--api-port` / `--db-port` en Linux o `-ApiPort` / `-DbPort` en Windows.
- La fuente canonica del compose cliente es `installers/shared/docker-compose.client.yml`; el control-plane sirve ese archivo para evitar drift.
- La ruta Windows soporta instalación asistida: si Docker Desktop no existe, intenta instalarlo con `winget`.
- Para salida a mercado, el pipeline de release debe validar artefactos, checksums y `dist-manifest.json` antes de publicar.
- Para pilotos con firma autofirmada, revisa `docs/referencia/AUTOFIRMA_WINDOWS_CONTROLADA.md`.

## Objetivo Plug-And-Play

- El instalador debe dejar el nodo listo para abrir la app y empezar a operar caja sin editar archivos manualmente.
- El acceso del dueño debe quedar delegado por el agente local, evitando pedir tokens crudos al usuario final.
- `INSTALL_SUMMARY.txt` debe ser suficiente para soporte de primer nivel: URLs, branch, API local y companion.

## Checklist Express Post-Instalacion

1. Abrir `INSTALL_SUMMARY.txt` y confirmar `Branch ID`, `API local`, `Manifest` y `Companion`.
2. Confirmar `http://127.0.0.1:<puerto>/health` responde correctamente.
3. Abrir la app desktop y verificar que la pantalla de acceso muestre nodo local saludable.
4. Verificar que el acceso del dueño aparezca como listo o en preparacion, sin pedir rutas ni tokens manuales.

## Archivos Que Deben Quedar Tras Instalar

- `.env`: secretos locales, puertos y `BACKEND_IMAGE`
- `docker-compose.yml`: compose cliente servido por el `control-plane`
- `titan-agent.json`: contrato compartido entre instalador, agente local y app desktop
- `INSTALL_SUMMARY.txt`: resumen de soporte con branch, health local, manifest, credenciales y comando de actualización
- `actualizar.sh` (Linux): script para actualizar el backend con un solo comando (`./actualizar.sh`)
- `abrir-pos.sh` (Linux) / `Abrir-POS.ps1` (Windows): lanzador usado por el icono del escritorio

## Checklist instalación limpia pre-lanzamiento

Antes de distribuir una release, ejecutar al menos una vez una instalación limpia en Linux y una en Windows para validar los instaladores.

**Requisito:** control-plane en marcha con al menos un tenant y una sucursal (branch) con `install_token` válido.

**Linux (entorno limpio: VM, contenedor o CI con Docker):**

1. `bash installers/linux/install-titan.sh --cp-url <URL_CONTROL_PLANE> --install-token <TOKEN>`
2. Comprobar que se generen en el directorio de instalación: `.env`, `docker-compose.yml`, `titan-agent.json`, `INSTALL_SUMMARY.txt`
3. Opcional: `docker compose up -d` y verificar `http://127.0.0.1:<puerto>/health`

**Windows (VM o runner de CI):**

1. `powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Titan.ps1 -CpUrl <URL> -InstallToken <TOKEN>`
2. Comprobar los mismos artefactos; si se usa Docker Desktop, completar con `Continue-Install.ps1` si aplica
3. Opcional: comprobar health del API local

Si no hay CI para instaladores, este checklist debe ejecutarse de forma manual antes de cada distribución.

## Resumen de scripts

| Script | Uso |
|--------|-----|
| `linux/install-titan.sh` | Instalar nodo (Docker, backend, compose). Crea icono escritorio + menú. |
| `linux/actualizar.sh` | Actualizar backend (pull + restart). Copiado a `INSTALL_DIR` al instalar. |
| `linux/uninstall-titan.sh` | Desinstalar nodo y quitar iconos. |
| `windows/Install-Titan.ps1` | Instalar nodo. Crea acceso directo en escritorio. |
| `windows/Continue-Install.ps1` | Continuar instalación tras instalar Docker Desktop. |
| `windows/Uninstall-Titan.ps1` | Desinstalar nodo y quitar acceso directo. |
