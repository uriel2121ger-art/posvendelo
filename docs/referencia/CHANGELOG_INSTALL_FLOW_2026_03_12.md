# POSVENDELO — Changelog Flujo de Instalacion Plug-and-Play
**Fecha:** 2026-03-12
**Sesion:** Instaladores all-in-one, rename titan-pos → posvendelo, wizard first-user, deploy pipeline

---

## Fase 1: Instaladores All-in-One

### Instalador Linux (.deb) — postinst.sh

**Archivo:** `installers/linux/postinst.sh`

El `.deb` ahora incluye un `postinst` que configura todo el backend automaticamente
tras la instalacion del paquete. El usuario solo hace `sudo dpkg -i posvendelo_amd64.deb`.

**Flujo del postinst:**

1. **Seccion 0 (set -e):** Registro Electron — symlink `/usr/bin/posvendelo`, chrome-sandbox
   SUID, AppArmor profile, update-desktop-database. Estas operaciones son criticas y
   deben fallar ruidosamente si algo sale mal.

2. **Seccion 1+ (set +e):** Backend setup — Docker install, `.env` generacion,
   `docker-compose.yml`, systemd service, pull + up, health check, INSTALL_SUMMARY.
   Fallos de red/Docker NO abortan `dpkg` — la app se instala siempre, el backend
   arranca cuando hay internet.

**Decisiones de diseno:**

| Decision | Razon |
|----------|-------|
| `set +e` despues de seccion 0 | `dpkg` aborta el paquete entero si postinst retorna non-zero. Fallos de Docker/red no deben impedir la instalacion de la app. |
| `ADMIN_API_USER=` / `ADMIN_API_PASSWORD=` vacios | El wizard de first-user en la app crea el admin. No se genera password random que nadie lee. |
| `exit 0` al final | Garantia: el postinst NUNCA falla dpkg. |
| Upgrade path con deteccion de containers corriendo | Si ya hay backend, solo pull + restart. No recrea .env ni compose. |
| systemd `posvendelo.service` con `Type=oneshot` | Auto-start de Docker Compose al boot. `RemainAfterExit=yes` para que `systemctl status` lo muestre como active. |

**INSTALL_SUMMARY.txt actualizado:** Ya no muestra credenciales. Dice "Configura tu
usuario al abrir el POS por primera vez."

### Instalador Windows (NSIS + PowerShell)

**Archivos:** `installers/windows/nsis-postinstall.nsh`, `installers/windows/Install-Posvendelo.ps1`

Flujo equivalente al Linux: instala Docker Desktop si no existe, genera `.env`,
`docker-compose.yml`, pull + up, health check.

---

## Fase 2: Rename titan-pos → posvendelo

**Alcance:** Todos los user-facing references renombrados.

| Componente | Antes | Despues |
|-----------|-------|---------|
| package.json name | `titan-pos` | `posvendelo` |
| Ejecutable Linux | `titan-pos` | `posvendelo` |
| Install dir | `/opt/titan-pos` | `/opt/posvendelo` |
| systemd service | `titan-pos.service` | `posvendelo.service` |
| GHCR image | `titan-pos:latest` | `posvendelo:latest` |
| .deb filename | `titan-pos_amd64.deb` | `posvendelo_amd64.deb` |
| .deb conflicts/replaces | — | `titan-pos` (upgrade limpio) |

**No renombrado (intencionalmente):**
- DB de desarrollo: `titan_pos` / `titan_user` (datos existentes, sin migracion)
- localStorage keys: `titan.baseUrl`, `titan.token` (backward compat con installs existentes)

---

## Fase 3: Frontend — Auto-configuracion Desktop

### Desktop ya no muestra "Configurar Servidor"

**Archivo:** `frontend/src/renderer/src/App.tsx`

**Problema:** En la primera ejecucion, `localStorage` no tenia `titan.baseUrl` → la app
redireccionaba a `/configurar-servidor` pidiendo IP del backend. Esto no tiene sentido
en desktop donde el backend siempre esta en `127.0.0.1:8000`.

**Solucion:** `useLayoutEffect` en `RoutedApp` auto-configura la URL para desktop:

```typescript
useLayoutEffect(() => {
  const saved = localStorage.getItem('titan.baseUrl')
  if (saved != null && saved.trim() !== '') return
  if (!isNativePlatform()) {
    // Desktop: auto-set default URL
    const defaultUrl = POSVENDELO_API_URL ?? 'http://127.0.0.1:8000'
    localStorage.setItem('titan.baseUrl', defaultUrl)
    return
  }
  // Mobile: show server config screen
  navigate('/configurar-servidor', { replace: true })
}, [location.pathname, navigate])
```

**`/configurar-servidor` solo se muestra en mobile** (Capacitor/APK) donde el usuario
debe escribir la IP del servidor LAN.

---

## Fase 4: Wizard First-User (antes de Login)

### Flujo completo primera ejecucion

```
Abrir app → splash (1-2s) → /setup-inicial-usuario → crear cuenta
→ auto-login → /setup-inicial → config negocio → /terminal
```

### Implementacion en App.tsx

**Estados:**
```typescript
const [firstUserChecked, setFirstUserChecked] = useState(false)
const [firstUserNeeded, setFirstUserNeeded] = useState(false)
```

**Check asincrono al montar:**
- Si hay token en localStorage → skip (usuario ya logueado)
- Si no hay token → llama `checkNeedsFirstUser(cfg)` al backend
- Si el backend dice `needs_first_user: true` → redirect a `/setup-inicial-usuario`
- Si falla la llamada (backend no levantado) → deja pasar a `/login`

**Splash screen:** Mientras el check async esta en progreso y no hay token,
se muestra un spinner con logo POSVENDELO para evitar flash de pantalla incorrecta.

**Ruta `/login` protegida:** Si `firstUserNeeded === true`, la ruta `/login` redirige
automaticamente a `/setup-inicial-usuario`:
```tsx
<Route path="/login" element={
  firstUserNeeded ? <Navigate to="/setup-inicial-usuario" replace /> : <Login />
} />
```

### Backend endpoints de soporte

**`GET /api/v1/auth/needs-setup`** — Publico, sin auth
- Retorna `{ needs_first_user: bool }` basado en `COUNT(*) FROM users`

**`POST /api/v1/auth/setup-owner`** — Publico, sin auth
- Solo funciona si hay 0 usuarios en la DB (sino 409 Conflict)
- Crea admin con bcrypt, retorna JWT
- Rate limited: 5/minute

### Componente FirstUserSetup.tsx

**Archivo:** `frontend/src/renderer/src/tabs/FirstUserSetup.tsx`

- Patron similar a `InitialSetupWizard.tsx`
- Campos: username, password, confirmar password, nombre (opcional)
- On submit: `setupOwnerUser()` → guarda token → navigate `/setup-inicial`
- On 409: redirect a `/login` (alguien ya creo el usuario)

### Login.tsx actualizado

**Archivo:** `frontend/src/renderer/src/Login.tsx`

- Auto-configura URL default para desktop (mismo patron que App.tsx)
- Texto de ayuda cambiado: "Si es la primera vez, crea tu usuario en la pantalla
  de configuracion inicial." (antes decia buscar INSTALL_SUMMARY.txt)

---

## Fase 5: Deploy Pipeline

### Homelab auto-deploy

- **Servidor homelab (nodo central):** 192.168.10.90; alias SSH `prod`. Ver [docs/operacion/HOMELAB.md](../../operacion/HOMELAB.md).
- **Script en el homelab:** `/opt/posvendelo/auto-deploy.sh` (cron cada 5 min). En el repo hay una plantilla: `scripts/homelab-auto-deploy.example.sh`.
- **Flujo:** git fetch → detecta commits nuevos → pull → rebuild control-plane → (opcional) Watchtower --run-once
- **Watchtower:** auto-pulls `ghcr.io/uriel2121ger-art/posvendelo:latest`

### Control-plane downloads

- Bind mount `./downloads:/app/downloads` — archivos visibles sin rebuild
- Nombres: `posvendelo_amd64.deb`, `posvendelo.AppImage`
- Tamanos dinamicos via `_file_size_mb()`
- Headers: `Cache-Control: no-cache, must-revalidate` + ETag

### Build artifacts (copia manual al homelab .90)

```bash
export HOMELAB_HOST="${HOMELAB_HOST:-192.168.10.90}"
cd frontend && npm run build:linux
scp dist/posvendelo_amd64.deb "user@${HOMELAB_HOST}:/path/to/control-plane/downloads/"
scp dist/posvendelo.AppImage "user@${HOMELAB_HOST}:/path/to/control-plane/downloads/"
```

---

## Fase 6: postinst.sh Resilience Fix

### Problema original

El `postinst.sh` original usaba `set -e` en todo el script. Si `docker compose pull`
fallaba (sin internet, Docker no instalado, etc.), el postinst retornaba non-zero
y **dpkg abortaba la instalacion completa del paquete**.

### Solucion

Dividir el script en dos zonas:

| Zona | Modo | Razon |
|------|------|-------|
| Seccion 0: Electron registration | `set -e` | Symlink, sandbox, AppArmor son criticos para que la app funcione |
| Seccion 1+: Backend Docker | `set +e` | Red/Docker pueden fallar; la app debe instalarse siempre |

El `exit 0` final garantiza que dpkg nunca falla por problemas del backend.

---

## Tests

### Frontend tests actualizados

**Archivo:** `frontend/src/renderer/src/__tests__/app-routing.test.tsx`

- Mock de `checkNeedsFirstUser` agregado (retorna `false` por default)
- Test "redirige a /configurar-servidor" → "auto-configura URL y redirige a /login"
- Test "redirige a /setup-inicial-usuario cuando no hay usuarios" (con mock `completed: false`)
- 85 tests frontend pasando

### Backend tests

- 204+ tests backend pasando
- Tests de `setup-owner` y `needs-setup` en `test_auth.py`

---

## Resumen de Impacto

### Archivos modificados/creados

| Archivo | Tipo | Descripcion |
|---------|------|-------------|
| `installers/linux/postinst.sh` | MOD | set +e resilience, .env sin password, INSTALL_SUMMARY sin credenciales |
| `installers/windows/nsis-postinstall.nsh` | MOD | Equivalente Windows del postinst |
| `installers/windows/Install-Posvendelo.ps1` | MOD | PowerShell backend setup |
| `frontend/src/renderer/src/App.tsx` | MOD | Auto-config URL, splash screen, first-user check, redirect logic |
| `frontend/src/renderer/src/Login.tsx` | MOD | Auto-config URL desktop, texto ayuda actualizado |
| `frontend/src/renderer/src/tabs/FirstUserSetup.tsx` | NUEVO | Wizard creacion primer usuario |
| `frontend/src/renderer/src/posApi.ts` | MOD | `checkNeedsFirstUser()`, `setupOwnerUser()` |
| `frontend/src/renderer/src/__tests__/app-routing.test.tsx` | MOD | Tests actualizados para nuevo flujo |
| `frontend/electron-builder.yml` | MOD | Rename, conflicts/replaces titan-pos |
| `frontend/package.json` | MOD | name: posvendelo |
| `backend/modules/auth/routes.py` | MOD | Endpoints setup-owner, needs-setup |
| `control-plane/` | MOD | Downloads page, bind mount, deploy scripts |

### Flujo end-to-end resultante

```
Desktop Linux:
  dpkg -i posvendelo.deb → postinst (Docker + backend) → abrir app
  → splash → /setup-inicial-usuario → crear admin → auto-login
  → /setup-inicial → config negocio → /terminal

Desktop (re-apertura):
  abrir app → /login → credenciales → /terminal

Mobile (APK cajero):
  abrir app → /configurar-servidor → IP del servidor LAN
  → /login → /terminal
```

---

---

## Fase 7: UX Login + NSIS Fix + Builds Multiplataforma (2026-03-12 tarde)

### Login UX — Eliminacion de jerga tecnica

**Archivo:** `frontend/src/renderer/src/Login.tsx`

**Problema:** Tras el wizard de primer usuario, el login mostraba un panel de 220+ lineas con:
- "La firma local de la licencia no pudo validarse"
- "El agente local no tiene bootstrap cargado. Revisa `posvendelo-agent.json`"
- Status de licencia, companion URLs, controles de rollback/update

El usuario final no sabe que es bootstrap, licencia, ni companion.

**Solucion:** Reemplazo completo del panel tecnico por indicador simple:

```tsx
{backendHealthy != null && (
  <div className="mb-4 flex items-center justify-center gap-2 text-xs text-zinc-500">
    <Wifi className={`h-3.5 w-3.5 ${backendHealthy ? 'text-emerald-400' : 'text-rose-400'}`} />
    <span>{backendHealthy ? 'Servidor conectado' : 'Conectando al servidor...'}</span>
  </div>
)}
```

**Resultado:** -534 lineas, Login limpio e intuitivo. Detalles tecnicos disponibles en SettingsTab para admins.

### NSIS — Fix $PROGRAMDATA y PowerShell escaping

**Archivo:** `installers/windows/nsis-postinstall.nsh`

**Problema 1:** NSIS no tiene `$PROGRAMDATA` como variable built-in → error `warning 6000`.
**Solucion:** `ReadEnvStr $POSVENDELO_DATA_DIR PROGRAMDATA` con fallback `C:\ProgramData`.

**Problema 2:** PowerShell embebido en NSIS: variables como `$content`, `$dbPass` se interpretan como variables NSIS.
**Solucion:** Escribir script PowerShell como archivo temporal (`$TEMP\posvendelo-genenv.ps1`) y ejecutar con `-File`.

### Builds multiplataforma

| Artefacto | Tamano | Estado |
|-----------|--------|--------|
| `posvendelo_1.0.0_amd64.deb` | 113 MB | OK — subido a homelab |
| `posvendelo-1.0.0-setup.exe` | 119 MB | OK — NSIS fix, subido a homelab |
| `app-debug.apk` (cajero) | 4.3 MB | OK — subido a homelab |
| Docker GHCR | — | Pusheado `ghcr.io/uriel2121ger-art/posvendelo:latest` |

### Tests verificados

- Backend: **142/142** pasando
- Frontend: **60/60** pasando (test de login actualizado para verificar UX limpio)

### Commit

`bb16c49` — `fix: clean Login UX + fix NSIS $PROGRAMDATA build error`

---

## Fase 8: Auto-Update — Agent Config Generation (2026-03-12 noche)

### Problema

El sistema de auto-update en `localAgent.ts` estaba 100% implementado pero desconectado:
el agente local busca `posvendelo-agent.json` para saber donde hacer polling de manifests,
pero los instaladores no generaban este archivo.

### Solucion

Ambos instaladores ahora generan `posvendelo-agent.json` en la primera instalacion:

| Plataforma | Ruta | Generado por |
|-----------|------|-------------|
| Linux | `~/.config/posvendelo/posvendelo-agent.json` | `postinst.sh` seccion 9 |
| Windows | `%LOCALAPPDATA%\POSVENDELO\posvendelo-agent.json` | `nsis-postinstall.nsh` seccion 7 |

**Contenido del agent config:**

```json
{
  "controlPlaneUrl": "",
  "localApiUrl": "http://127.0.0.1:8000",
  "backendHealthUrl": "http://127.0.0.1:8000/health",
  "appArtifact": "electron-linux|electron-windows",
  "backendArtifact": "backend",
  "releaseChannel": "stable",
  "pollIntervals": {
    "healthSeconds": 30,
    "manifestSeconds": 300,
    "licenseSeconds": 3600
  }
}
```

**Flujo auto-update end-to-end:**

```
localAgent.ts inicia → busca posvendelo-agent.json
→ lee controlPlaneUrl → poll manifest cada 5 min
→ detecta nueva version → descarga artefacto
→ verifica SHA256 → stage en directorio temporal
→ usuario aplica → reemplaza binario → reinicia app
```

**Decisiones:**

| Decision | Razon |
|----------|-------|
| `controlPlaneUrl` vacio por default | Se configura despues via bootstrap o manualmente. Sin URL, el agente solo hace health checks |
| Linux: `~/.config/posvendelo/` | Coincide con `app.getPath('userData')` de Electron en Linux |
| Windows: `$LOCALAPPDATA\POSVENDELO\` | Coincide con la busqueda de `localAgent.ts` en `process.env.LOCALAPPDATA` |
| Solo genera si no existe | Nunca sobreescribe config del usuario con sus tokens/URLs |
| `chown` para el usuario real (Linux) | `postinst.sh` corre como root via dpkg, pero el archivo es del usuario |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `installers/linux/postinst.sh` | +seccion 9: genera posvendelo-agent.json |
| `installers/windows/nsis-postinstall.nsh` | +seccion 7: genera posvendelo-agent.json |

---

*Ultima actualizacion: 2026-03-12 21:00*
