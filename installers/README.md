# Instaladores TITAN POS

## Linux

Instalador piloto:

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

Instalador piloto controlado:

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
- Si `8000` o `5434` ya estan ocupados, los instaladores pueden autoasignar puertos locales libres; tambien puedes fijarlos con `--api-port` / `--db-port` en Linux o `-ApiPort` / `-DbPort` en Windows.
- La fuente canonica del compose cliente es `installers/shared/docker-compose.client.yml`; el control-plane sirve ese archivo para evitar drift.
- La ruta Windows esta pensada como piloto: si Docker Desktop no existe, intenta instalarlo con `winget`.
- Para pilotos con firma autofirmada, revisa `docs/AUTOFIRMA_WINDOWS_CONTROLADA.md`.
