# Instaladores TITAN POS

## Linux

Instalador Linux del nodo TITAN:

```bash
bash installers/linux/install-titan.sh --cp-url http://localhost:9090 --install-token TOKEN
```

Opcional:

```bash
bash installers/linux/install-titan.sh --cp-url http://localhost:9090 --install-token TOKEN --api-port 8002 --db-port 15434
```

Desinstalacion:

```bash
bash installers/linux/uninstall-titan.sh
```

## Windows

Instalador Windows del nodo TITAN:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Titan.ps1 -CpUrl http://localhost:9090 -InstallToken TOKEN
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

Desinstalacion:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Uninstall-Titan.ps1
```

## Notas

- Los instaladores consumen `bootstrap-config` y `compose-template` del `control-plane`.
- Ambos generan `titan-agent.json` en el directorio de instalacion para que la app desktop y el agente local compartan el mismo contrato de bootstrap.
- Ambos generan `INSTALL_SUMMARY.txt` con URLs, branch y archivos clave para soporte post-instalacion.
- El `bootstrap-config` ya expone `owner_session_url`, `owner_api_base_url`, `companion_entry_url` y `quick_links` para dejar listo el acceso remoto del dueño sin tener que reconstruir rutas a mano.
- Si `8000` o `5434` ya estan ocupados, los instaladores pueden autoasignar puertos locales libres; tambien puedes fijarlos con `--api-port` / `--db-port` en Linux o `-ApiPort` / `-DbPort` en Windows.
- La fuente canonica del compose cliente es `installers/shared/docker-compose.client.yml`; el control-plane sirve ese archivo para evitar drift.
- La ruta Windows soporta instalación asistida: si Docker Desktop no existe, intenta instalarlo con `winget`.
- Para salida a mercado, el pipeline de release debe validar artefactos, checksums y `dist-manifest.json` antes de publicar.
- Para pilotos con firma autofirmada, revisa `docs/AUTOFIRMA_WINDOWS_CONTROLADA.md`.

## Objetivo Plug-And-Play

- El instalador debe dejar el nodo listo para abrir la app y empezar a operar caja sin editar archivos manualmente.
- El acceso del dueño debe quedar delegado por el agente local, evitando pedir tokens crudos al usuario final.
- `INSTALL_SUMMARY.txt` debe ser suficiente para soporte de primer nivel: URLs, branch, API local y companion.

## Checklist Express Post-Instalacion

1. Abrir `INSTALL_SUMMARY.txt` y confirmar `Branch ID`, `API local`, `Manifest` y `Companion`.
2. Confirmar `http://127.0.0.1:<puerto>/health` responde correctamente.
3. Abrir la app desktop y verificar que la pantalla de acceso muestre nodo local saludable.
4. Verificar que el acceso del dueño aparezca como listo o en preparacion, sin pedir rutas ni tokens manuales.

## Archivos Que Deben Quedar

- `.env`: secretos locales, puertos y `BACKEND_IMAGE`
- `docker-compose.yml`: compose cliente servido por el `control-plane`
- `titan-agent.json`: contrato compartido entre instalador, agente local y app desktop
- `INSTALL_SUMMARY.txt`: resumen de soporte con branch, health local, manifest y companion
