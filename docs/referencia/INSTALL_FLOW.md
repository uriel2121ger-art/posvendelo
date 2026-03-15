# Flujo de instalación plug-and-play

## Resumen

POSVENDELO se instala sin necesidad de crear una cuenta. El instalador recolecta
un fingerprint de hardware, se pre-registra en el control plane, y el POS
queda operativo en minutos. La nube es opcional y se activa después.

> **Implementación de referencia:** ver [CHANGELOG_INSTALL_FLOW_2026_03_12.md](CHANGELOG_INSTALL_FLOW_2026_03_12.md)

## PC principal vs caja secundaria (desktop)

En Linux y Windows puede instalarse la misma app como **PC principal** (con base de datos y backend en esta máquina) o como **caja secundaria** (solo app, conecta a un servidor en la red).

| Modo        | Comportamiento |
|-------------|----------------|
| **Principal** | postinst registra Electron; al abrir la app `ensureBackend()` instala Docker + PostgreSQL. La app usa `127.0.0.1:8000`. Wizard de negocio y opcional registro para monitoreo. |
| **Secundaria** | No se instala backend. Se escribe un marcador (`install-mode` = client). Al abrir la app se muestra "Configurar servidor" para indicar la IP del nodo en LAN. |

- **Linux (.deb):** ejecutar con `sudo INSTALL_MODE=client dpkg -i posvendelo*.deb` para modo caja secundaria.
- **Windows (PowerShell):** ejecutar con `-InstallMode Client` para modo caja secundaria.
- **Android (APK):** siempre es cliente; la app pide la dirección del servidor si no hay URL guardada.

## Fases

### Fase 1: Instalación automática (PC principal)

```
posvendelo.com → descarga instalador → ejecuta
    │
    ├── postinst (Sección 0): instala Electron, genera posvendelo-agent.json
    │
    └── abrir app → /seleccionar-modo
          → [PC Principal] → ensureBackend()
                ├── Instala Docker si no está presente
                ├── Recolecta fingerprint de hardware
                │   (board_serial, board_name, cpu_model, mac_primary, disk_serial)
                ├── POST /api/v1/branches/pre-register
                │   └── Fingerprint nuevo → tenant anónimo + branch + trial 40 días
                │   └── Fingerprint conocido → devuelve install_token existente
                ├── GET /api/v1/branches/bootstrap-config
                ├── GET /api/v1/branches/compose-template (sin cloudflared)
                ├── Genera .env y docker-compose.yml
                ├── docker compose up -d
                └── POS funciona local
```

### Fase 2: Dispositivos LAN

```
PC servidor ──UDP broadcast :41520 cada 2s──→
    │
    ├── PC Cajero (Electron) → detecta automáticamente
    ├── Celular cajero (app nativa / PWA) → detecta automáticamente
    └── Tablet cajero → detecta automáticamente

    Todos consultan: GET /api/v1/system/license-status
    → { trial: true, days_remaining: N, features: {...} }
```

### Fase 3: Activar nube (opcional)

```
Desde POS → Configuración > Nube  (o wizard de primera vez)
    │
    ├── email + password
    ├── POST /api/v1/cloud/activate (proxy al CP)
    │   └── Vincula tenant anónimo al cloud_user
    │   └── Provisiona túnel Cloudflare automáticamente
    │
    └── Acceso remoto desde celular del dueño
```

## Fingerprint de hardware

| Componente     | Peso | Linux                            | Windows                                |
|----------------|------|----------------------------------|----------------------------------------|
| board_serial   | 3    | /sys/class/dmi/id/board_serial   | Get-CimInstance Win32_BaseBoard        |
| cpu_model      | 2    | /proc/cpuinfo                    | Get-CimInstance Win32_Processor        |
| mac_primary    | 2    | /sys/class/net/*/address         | Get-NetAdapter -Physical               |
| disk_serial    | 2    | lsblk -ndo SERIAL                | Get-CimInstance Win32_DiskDrive        |
| board_name     | 1    | /sys/class/dmi/id/board_name     | Get-CimInstance Win32_BaseBoard        |
| **Umbral**     | ≥5   |                                  |                                        |

- Cada campo se almacena hasheado (SHA-256) en la DB del control plane
- Matching por puntaje: si score ≥ 5 de 10, se considera la misma máquina
- Reinstalar no reinicia el período de prueba

## Post-trial (día 41+)

| Feature      | Estado       |
|--------------|-------------|
| Ventas       | Activo      |
| Productos    | Activo      |
| Inventarios  | Activo      |
| Historial    | Activo      |
| Fiscal/CFDI  | Desactivado |
| Clientes     | Desactivado |
| Reportes     | Desactivado |

## Endpoints nuevos

### Control Plane

| Método | Ruta                                    | Auth           | Descripción                        |
|--------|-----------------------------------------|----------------|------------------------------------|
| POST   | /api/v1/branches/pre-register           | Público        | Pre-registro con fingerprint       |
| POST   | /api/v1/branches/reprovision-tunnel     | install_token  | Re-provisionar túnel               |
| GET    | /api/v1/branches/compose-template       | install_token  | Template dinámico (con/sin CF)     |

### Backend POS

| Método | Ruta                                    | Auth    | Descripción                        |
|--------|-----------------------------------------|---------|------------------------------------|
| GET    | /api/v1/system/license-status           | Público | Estado de trial y features         |
| POST   | /api/v1/cloud/activate                  | Público | Proxy para activar nube            |
| GET    | /api/v1/cloud/status                    | Público | Estado de conexión a nube          |

### Discovery LAN

| Protocolo | Puerto | Intervalo | Payload                              |
|-----------|--------|-----------|--------------------------------------|
| UDP       | 41520  | 2s        | `{service, api_url, branch_name}`    |

## Auto-update (Electron desktop)

El agente local (`localAgent.ts`) gestiona actualizaciones automáticas:

```
localAgent.ts inicia → busca posvendelo-agent.json
→ lee controlPlaneUrl → poll manifest cada 5 min
→ detecta nueva version → descarga artefacto
→ verifica SHA256 → stage en directorio temporal
→ usuario aplica → reemplaza binario → reinicia app
```

### Agent config

Los instaladores generan `posvendelo-agent.json` en la primera instalación:

| Plataforma | Ruta |
|-----------|------|
| Linux | `~/.config/posvendelo/posvendelo-agent.json` |
| Windows | `%LOCALAPPDATA%\POSVENDELO\posvendelo-agent.json` |

El agente busca en este orden: env var, `userData`, `~/.posvendelo/`, `%LOCALAPPDATA%`.

### Manifest endpoint

`GET /api/v1/releases/manifest?install_token=TOKEN` retorna artefactos con:
- `version`, `target_ref`, `channel`
- `checksums_manifest_url` (para verificación SHA256)
- `rollback_supported`, `rollback.version`

## Archivos clave

```
control-plane/
├── db/migrations/005_hardware_fingerprints.sql
├── modules/branches/fingerprint.py          # matching por pesos
├── modules/branches/routes.py               # pre-register, compose dinámico
├── modules/tunnel/service.py                # ensure_tunnel_provisioned
└── modules/cloud/routes.py                  # vincular tenant anónimo

backend/
├── modules/system/routes.py                 # license-status
├── modules/cloud/routes.py                  # activate proxy
└── modules/discovery/broadcast.py           # UDP broadcast

installers/
├── linux/postinst.sh                        # Electron registration + agent.json (NO Docker)
└── windows/nsis-postinstall.nsh             # Electron registration + agent.json (NO Docker)

frontend/
└── src/main/autoSetup.ts                    # ensureBackend(): Docker + PostgreSQL al elegir PC Principal
```
