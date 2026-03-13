# Auditoría: instaladores, control-plane, owner-app y documentación

**Fecha:** 2026-03-12  
**Alcance:** installers/linux, installers/windows, control-plane, owner-app, docs (INSTALL_FLOW, README, CLAUDE.md, AGENTS.md).

---

## Resumen ejecutivo

| Área | Cumplimientos | Discrepancias / Riesgos |
|------|----------------|-------------------------|
| **Instaladores Linux** | postinst: set -e/set +e, exit 0, .env sin ADMIN password, posvendelo-agent.json, INSTALL_SUMMARY sin credenciales, upgrade sin reescribir .env. install-posvendelo.sh: --backend-image, mensajes en español. | Ninguna (token por header aceptado tras fix en control-plane). |
| **Instaladores Windows** | NSIS: ReadEnvStr PROGRAMDATA, PowerShell en archivo temporal, posvendelo-agent.json en %LOCALAPPDATA%\POSVENDELO, mensajes en español. | Ninguna (token por header aceptado). |
| **Control-plane** | bootstrap-config, compose-template, licencias, tenants, cloud; mensajes en español; CP_BASE_URL desde env; CP_PUBLIC_URL en releases. | Ninguna (añadida dependencia _get_install_token: query o header). |
| **Owner-app** | Estructura Electron, ownerAgent.ts con configPath LOCALAPPDATA/POSVENDELO, build scripts, mensajes en español. | Sin discrepancias críticas. |
| **Documentación** | INSTALL_FLOW.md y CHANGELOG coherentes con postinst/NSIS; docs/README índice actualizado; CLAUDE.md y AGENTS.md con precios DB, PINs, manager_pin, sequences. | docs/README no enlaza INSTALL_FLOW como “flujo de instalación”; pequeña incoherencia PINs (CLAUDE: bcrypt + sha256 legacy; AGENTS solo sha256). |

**Acción prioritaria (aplicada):** Se unificó la autenticación en control-plane: `bootstrap-config` y `compose-template` aceptan `install_token` por query **o** por header (Authorization Bearer / X-Install-Token) mediante la dependencia `_get_install_token` en `modules/branches/routes.py`. Los instaladores que solo envían Bearer ya no reciben 422.

---

## 1) Instaladores Linux (`installers/linux/`)

### 1.1 postinst.sh

| Requisito | Estado | Ubicación |
|-----------|--------|-----------|
| Sección 0 con `set -e` (Electron/symlink/sandbox/AppArmor) | Cumple | L.2 `set -e`, L.5–41 bloque Electron |
| Secciones 1+ con `set +e` (Docker/env/compose) | Cumple | L.50 `set +e` |
| `exit 0` al final | Cumple | L.317 |
| Generación de .env sin ADMIN password (wizard first-user) | Cumple | L.169–174 `ADMIN_API_USER=` / `ADMIN_API_PASSWORD=` vacíos |
| Generación de posvendelo-agent.json | Cumple | L.250–291, para usuario real vía REAL_HOME |
| INSTALL_SUMMARY sin credenciales | Cumple | L.296–312, solo texto informativo |
| Upgrade path sin reescribir .env si ya hay contenedores | Cumple | L.116–124: si existe .env y hay contenedores, solo _write_compose, pull, up, exit 0 |

**Notas:**  
- CONTROL_PLANE_URL se lee de .env (L.262–265) para rellenar `controlPlaneUrl` en posvendelo-agent.json; en instalación nueva queda vacío (correcto).  
- Agente config en `~/.config/posvendelo/posvendelo-agent.json` (usuario real), coherente con frontend localAgent y documentación.

### 1.2 install-posvendelo.sh

| Requisito | Estado | Ubicación |
|-----------|--------|-----------|
| Opción `--backend-image` | Cumple | L.106–109, BACKEND_IMAGE_OVERRIDE en .env (L.291) |
| Mensajes en español | Cumple | Uso consistente de `[POSVENDELO]` y textos en español |

**Riesgo (resuelto):** Los instaladores envían solo `Authorization: Bearer`. El control-plane ahora acepta token por query **o** por header (dependencia `_get_install_token` en branches/routes.py), por lo que install-posvendelo.sh e Install-Posvendelo.ps1 funcionan sin cambio.

---

## 2) Instaladores Windows (`installers/windows/`)

### 2.1 NSIS + nsis-postinstall.nsh

| Requisito | Estado | Ubicación |
|-----------|--------|-----------|
| Equivalente a postinst (Docker, .env, compose, health, INSTALL_SUMMARY) | Cumple | customInstall: Docker Desktop, .env, compose, pull/up, health, agent config, INSTALL_SUMMARY |
| $PROGRAMDATA vía ReadEnvStr | Cumple | L.29–31 `ReadEnvStr $POS_DATA_DIR PROGRAMDATA`, fallback `C:\ProgramData` |
| PowerShell como archivo temporal (evitar escape de variables NSIS) | Cumple | L.104–119: escribe `$TEMP\posvendelo-genenv.ps1`, luego nsExec con `-File` y `$POS_ENV` como argumento |
| posvendelo-agent.json en %LOCALAPPDATA%\POSVENDELO | Cumple | L.230–234 `ReadEnvStr $POS_LOCAL_APPDATA LOCALAPPDATA`, L.234 `$POS_AGENT_DIR = "$POS_LOCAL_APPDATA\POSVENDELO"` |

**Notas:**  
- customUnInstall relee PROGRAMDATA (L.297–299).  
- Mismo riesgo que en Linux: si en el futuro se usara control-plane para bootstrap/compose desde Windows (p. ej. script que llame a estas URLs), habría que pasar `install_token` por query o que el API acepte header.

### 2.2 Install-Posvendelo.ps1

- Mensajes en español y flujo equivalente a install-posvendelo.sh (bootstrap, .env, compose, posvendelo-agent.json, INSTALL_SUMMARY).  
- Mismo punto de integración: L.287 y L.429 usan solo header `Authorization: Bearer $InstallToken` para bootstrap-config y compose-template; el API espera query → 422.

---

## 3) Control-plane

| Requisito | Estado | Ubicación / Notas |
|-----------|--------|-------------------|
| bootstrap-config, compose-template | Cumple | modules/branches/routes.py L.349–458 |
| Licencias, tenants, cloud | Cumple | modules/licenses, modules/tenants, modules/cloud |
| Mensajes en español | Cumple | HTTPException(detail="...") en español en branches, owner, licenses, releases, tunnel, heartbeat |
| URLs desde env (CP_BASE_URL, CP_PUBLIC_URL) | Cumple | CP_BASE_URL: branches/routes.py L.397, tenants L.135, tunnel/cloudflare L.13; CP_PUBLIC_URL: releases/routes.py L.361, cloud/routes.py L.64 |

**Discrepancia (resuelta):** Se añadió la dependencia `_get_install_token` que devuelve `install_token` desde Query (opcional) o desde header (Authorization Bearer / X-Install-Token). Ambos endpoints la usan, así que aceptan query o header.

---

## 4) Owner-app

| Requisito | Estado | Ubicación / Notas |
|-----------|--------|-------------------|
| Estructura (Electron + React/Vite, electron/main.ts, ownerAgent) | Cumple | electron/main.ts, electron/ownerAgent.ts, src/App.tsx, package.json |
| Uso de bootstrap/agente (posvendelo-agent.json) | Cumple | ownerAgent.ts configPath(): Linux `~/.config/posvendelo/posvendelo-agent.json`, Windows `%LOCALAPPDATA%\POSVENDELO\posvendelo-agent.json` (L.55–61) |
| Build Electron | Cumple | package.json "build:electron", "build:desktop", "build:linux", "build:win"; electron-builder.yml |

Mensajes de ownerAgent en español (“Control-plane no configurado”, “Verificando actualizaciones...”, “Actualización disponible”, etc.). Sin discrepancias críticas detectadas.

---

## 5) Documentación

### 5.1 docs/referencia/INSTALL_FLOW.md y CHANGELOG_INSTALL_FLOW_2026_03_12.md

- INSTALL_FLOW describe fases (pre-register, bootstrap-config, compose-template, discovery, activar nube), fingerprint, rutas de posvendelo-agent.json (Linux/Windows) y archivos clave. Coherente con la implementación de postinst y NSIS.  
- CHANGELOG detalla postinst (set -e/set +e), .env sin ADMIN password, INSTALL_SUMMARY, upgrade path, NSIS (PROGRAMDATA, PowerShell temporal), generación de posvendelo-agent.json.  
- **Pequeña mejora:** En INSTALL_FLOW o CHANGELOG mencionar que bootstrap-config/compose-template en la API actual exigen `install_token` por query y que los instaladores que usan solo header deben pasar también query o que el API acepte ambos.

### 5.2 docs/README.md

- Índice actualizado: distribucion/, operacion/, testing/, referencia/, informes/, otros/. INSTALL_FLOW.md y CHANGELOG_INSTALL_FLOW_2026_03_12.md listados en referencia/.  
- No hay entrada explícita tipo “Flujo de instalación plug-and-play” en la tabla; ya está cubierto por INSTALL_FLOW.md. Opcional: añadir una línea en la descripción del índice que diga “Flujo de instalación” para INSTALL_FLOW.

### 5.3 CLAUDE.md y AGENTS.md vs reglas

- **Precios desde DB:** CLAUDE.md y AGENTS.md indican no confiar en item.price del cliente si hay product_id. Coherente.  
- **PINs:** CLAUDE.md: “bcrypt (rounds=12) para hashes nuevos; sha256 hex legacy via pin_auth.py”. AGENTS.md: “PINs en users.pin_hash con sha256 hex”. AGENTS no menciona bcrypt; conviene añadir “bcrypt para nuevos, sha256 hex legacy” para alineación.  
- **manager_pin / cancelaciones:** Ambos dicen que las cancelaciones requieren manager_pin. Coherente.  
- **Sequences:** CLAUDE “fix_all_sequences()”; AGENTS “setval() cuando aplique”. Mismo criterio.  
- **postinst:** “set -e solo sección 0, set +e secciones 1+” documentado en ambos. Coherente con postinst.sh.

---

## Resumen de acciones recomendadas

1. ~~**Crítico:** Aceptar install_token por query o header en bootstrap-config/compose-template.~~ **Hecho:** dependencia `_get_install_token` en control-plane/modules/branches/routes.py.  
2. **Documentación:** En AGENTS.md, precisar PINs: “bcrypt para nuevos, sha256 hex legacy”.  
3. **Opcional:** En docs/README.md, indicar junto a INSTALL_FLOW.md que cubre el “Flujo de instalación plug-and-play”.

---

*Auditoría generada el 2026-03-12. Archivos revisados: installers/linux/postinst.sh, installers/linux/install-posvendelo.sh, installers/windows/nsis-postinstall.nsh, installers/windows/Install-Posvendelo.ps1, control-plane/main.py, control-plane/modules/branches/routes.py, control-plane/security.py, owner-app/electron/main.ts, owner-app/electron/ownerAgent.ts, docs/referencia/INSTALL_FLOW.md, docs/referencia/CHANGELOG_INSTALL_FLOW_2026_03_12.md, docs/README.md, CLAUDE.md, AGENTS.md.*
