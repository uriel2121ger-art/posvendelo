# Plan: Nube PosVendelo — App del Dueño + Backend Cloud

## Contexto

Los dueños de negocio necesitan monitorear y controlar sus sucursales/bodegas remotamente. "Nube PosVendelo" es una cuenta (email+password) que vincula múltiples sucursales. El dueño usa una **app separada** (Electron desktop + PWA móvil) que se conecta al control-plane vía CF Tunnel privado. No es un portal web público.

### Decisiones confirmadas
- **Registro**: Desde el instalador del POS (o después desde configuración de la app POS)
- **App del dueño**: App React separada empaquetada como Electron (desktop) + PWA (móvil)
- **Comunicación**: Vía control-plane con cola de comandos (no directo al nodo)
- **Acceso WAN**: CF Tunnel privado al control-plane — URL resuelta automáticamente
- **Alcance**: Control total remoto (monitoreo + acciones)
- **Vinculación**: Código al instalar + regenerar desde la app POS

---

## Arquitectura

```
┌──────────────────┐     ┌──────────────────┐
│  App Dueño       │     │  App POS         │
│  (Electron/PWA)  │     │  (Electron)      │
│  email+password  │     │  cajero/gerente   │
└────────┬─────────┘     └────────┬─────────┘
         │ HTTPS                   │ LAN
         │                         │ autodiscovery
         ▼                         ▼
┌─────────────────────┐    ┌─────────────┐
│  Control Plane      │    │  Nodo POS   │
│  (homelab)          │◄───│  (sucursal) │
│                     │    │  heartbeat  │
│  CF Tunnel privado  │    │  poll cmds  │
│  titancloud.dominio │    └─────────────┘
│                     │
│  - cloud auth       │
│  - owner portfolio  │
│  - command queue    │
│  - discovery        │
└─────────────────────┘
```

### Flujo del dueño
1. Instala POSVENDELO en sucursal → el instalador le invita a crear cuenta Nube PosVendelo (email+password)
2. El instalador crea la cuenta, registra la sucursal y la vincula automáticamente
3. El dueño descarga la **App Dueño** en su PC o instala la PWA en su celular
4. Abre la app → pone email+password → la app resuelve la URL del CP vía `GET https://api.titanpos.mx/discover` → se conecta al CP
5. Ve todas sus sucursales, ventas, alertas, y puede enviar comandos remotos

### Flujo LAN (sin cambios)
- El cajero abre la App POS → autodiscovery en la LAN → se conecta directo al nodo local

---

## Fase 1: DB + Auth Backend

### 1.1 Migración `control-plane/db/migrations/002_cloud_accounts.sql`

```sql
CREATE TABLE IF NOT EXISTS cloud_accounts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,          -- bcrypt
    full_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    email_verified INTEGER NOT NULL DEFAULT 0,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cloud_accounts_tenant ON cloud_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cloud_accounts_email ON cloud_accounts(email);

CREATE TABLE IF NOT EXISTS link_codes (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_link_codes_code ON link_codes(code);
```

### 1.2 Dependencia
- `control-plane/requirements.txt`: agregar `bcrypt>=4.0.0`

### 1.3 Nuevo módulo `control-plane/modules/cloud/`

**Archivos**: `__init__.py`, `schemas.py`, `routes.py`

**Endpoints**:

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/v1/cloud/register` | Ninguna (rate limit 5/h) | Crea tenant + cloud_account + branch + trial license |
| POST | `/api/v1/cloud/login` | Ninguna (rate limit 10/min) | Email+password → session token HMAC |
| GET | `/api/v1/cloud/me` | cloud session | Perfil + resumen tenant |
| POST | `/api/v1/cloud/link-node` | cloud session | Vincular nodo por código de 6 dígitos |
| POST | `/api/v1/cloud/link-install-token` | cloud session | Vincular nodo por install_token directo |
| PUT | `/api/v1/cloud/password` | cloud session | Cambiar contraseña |
| GET | `/api/v1/cloud/discover` | Ninguna | Retorna URL base del CP (para la app del dueño) |

#### Flujo de registro desde instalador
```
POST /api/v1/cloud/register
Body: {email, password, full_name, business_name}
→ Crea tenant (name=business_name, slug=auto)
→ Crea cloud_account (email, bcrypt(password), tenant_id)
→ Crea branch (name="Sucursal Principal", tenant_id)
→ Crea trial license (ensure_trial_license existente)
→ Retorna {tenant_id, branch_id, install_token, session_token}
```

El instalador recibe el `install_token` y lo usa para el bootstrap normal del nodo.

### 1.4 Endpoint de vinculación en branches
- `POST /api/v1/branches/generate-link-code` (auth: install_token)
- Genera código 6 chars alfanumérico uppercase, TTL 15 min, single-use
- Retorna `{code, expires_at}`

### 1.5 Extensión de `security.py`
- Agregar `hash_password(plain)` y `verify_password(plain, hashed)` con bcrypt
- `sign_owner_session` ya funciona — se usa con claims `{auth_type: "cloud-account", cloud_account_id, tenant_id, scopes}`
- `verify_owner_access` ya reconoce owner-session tokens sin cambios

### 1.6 Extensión de `modules/owner/routes.py`
- `_resolve_owner_context`: aceptar `auth_type == "cloud-account"` donde `tenant_id` viene del token y `branch_id` es None (ve TODAS las sucursales del tenant)

### 1.7 Endpoint de discovery
- `GET /api/v1/cloud/discover` — público, sin auth
- Retorna `{cp_url: "https://titancloud.dominio.com", version: "1.0", status: "ok"}`
- Este endpoint también se puede servir desde un dominio público mínimo (DNS o static site)

### Archivos a modificar
- `control-plane/requirements.txt`
- `control-plane/main.py` (registrar router cloud)
- `control-plane/security.py` (bcrypt helpers)
- `control-plane/modules/owner/routes.py` (_resolve_owner_context)
- `control-plane/modules/branches/routes.py` (generate-link-code)

### Archivos a crear
- `control-plane/db/migrations/002_cloud_accounts.sql`
- `control-plane/modules/cloud/__init__.py`
- `control-plane/modules/cloud/schemas.py`
- `control-plane/modules/cloud/routes.py`
- `control-plane/tests/test_cloud_auth.py`

---

## Fase 2: Cola de Comandos

### 2.1 Migración `003_command_queue.sql`

```sql
CREATE TABLE IF NOT EXISTS command_queue (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    command_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    result JSONB,
    created_by BIGINT REFERENCES cloud_accounts(id),
    created_at TIMESTAMP DEFAULT NOW(),
    picked_at TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cmd_queue_branch_pending
    ON command_queue(branch_id, status) WHERE status = 'pending';
```

### 2.2 Tipos de comando MVP

| command_type | payload | Acción en el nodo |
|---|---|---|
| `update_product_price` | `{product_id, new_price}` | PUT /api/v1/products/{id} |
| `create_product` | `{name, sku, price, ...}` | POST /api/v1/products/ |
| `update_stock` | `{product_id, quantity, reason}` | Ajuste de inventario |
| `toggle_user` | `{user_id, is_active}` | Activar/desactivar usuario |
| `create_user` | `{username, password, role}` | Crear usuario en sucursal |
| `sync_request` | `{}` | Forzar sync de datos al CP |

### 2.3 Endpoints

**Portal → CP (cloud session auth)**:
- `POST /api/v1/cloud/commands` — Encolar comando para una sucursal
- `GET /api/v1/cloud/commands?branch_id=X` — Historial de comandos

**Nodo → CP (install_token auth)**:
- `GET /api/v1/commands/pending?install_token=X` — Nodo recoge comandos pendientes
- `POST /api/v1/commands/{id}/ack` — Nodo reporta resultado

### 2.4 Poll de comandos en el nodo
- En `backend/main.py`, agregar `_command_poll_loop()` junto al `_heartbeat_loop()` existente
- Intervalo: `COMMAND_POLL_INTERVAL_SECONDS` (default 30s)
- El nodo ejecuta cada comando contra su propia API local y reporta resultado al CP

### Archivos a crear
- `control-plane/db/migrations/003_command_queue.sql`
- `control-plane/modules/commands/__init__.py`
- `control-plane/modules/commands/routes.py`
- `control-plane/modules/commands/schemas.py`
- `control-plane/tests/test_commands.py`

### Archivos a modificar
- `control-plane/main.py` (registrar commands router)
- `backend/main.py` (agregar _command_poll_loop)

---

## Fase 3: App del Dueño (`owner-app/`)

### 3.1 Estructura del proyecto

```
owner-app/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── index.html
├── electron-builder.yml         # empaquetado Electron
├── vite.config.pwa.ts           # config PWA con vite-plugin-pwa
├── src/
│   ├── main/
│   │   └── index.ts             # Electron main process (mínimo)
│   ├── preload/
│   │   └── index.ts             # Preload para Electron
│   └── renderer/
│       ├── main.tsx
│       ├── App.tsx              # HashRouter
│       ├── api.ts               # fetch wrapper → CP
│       ├── auth.ts              # session management
│       ├── pages/
│       │   ├── LoginPage.tsx
│       │   ├── RegisterPage.tsx     # solo si no vino del instalador
│       │   ├── DashboardPage.tsx    # portfolio + alertas + fleet health
│       │   ├── BranchDetailPage.tsx # detalle sucursal + timeline + comandos
│       │   ├── ProductsPage.tsx     # CRUD productos remoto (vía comandos)
│       │   ├── UsersPage.tsx        # gestión usuarios remota
│       │   └── SettingsPage.tsx     # perfil, cambiar password
│       └── components/
│           ├── BranchCard.tsx
│           ├── AlertBanner.tsx
│           ├── HealthBadge.tsx
│           ├── CommandStatus.tsx
│           └── Navbar.tsx
```

### 3.2 Stack
- React 19 + Vite + TypeScript + TailwindCSS (mismo que frontend POS)
- Electron para desktop (electron-builder)
- vite-plugin-pwa para PWA móvil
- Sin más dependencias pesadas

### 3.3 Conexión al CP
- Al abrir la app: `GET https://api.titanpos.mx/discover` → obtiene `cp_url`
- Guarda `cp_url` en localStorage
- Todas las llamadas van a `{cp_url}/api/v1/cloud/*` y `{cp_url}/api/v1/owner/*`
- Headers: `Authorization: Bearer {session_token}`

### 3.4 Reutilización del frontend POS
- Adaptar `OwnerPortfolioTab.tsx` → `DashboardPage.tsx` (80% del código)
- Adaptar estilos TailwindCSS existentes
- Los endpoints `/api/v1/owner/*` ya devuelven todo para el dashboard

### 3.5 Builds
- **Desktop**: `electron-builder` genera .AppImage (Linux), .exe (Windows), .dmg (Mac)
- **PWA**: `vite build` con service worker para instalar desde el navegador móvil
- Ambos desde el mismo código fuente

---

## Fase 4: Integración con Instalador + App POS

### 4.1 Flujo del instalador actualizado

```
┌───────────────────────────────────────────────┐
│  Instalador POSVENDELO                         │
│                                               │
│  ... (instala Docker, descarga imágenes) ...  │
│                                               │
│  ═══ Nube PosVendelo ═══                           │
│  ¿Deseas vincular esta sucursal a             │
│   una cuenta Nube PosVendelo?                      │
│                                               │
│  [1] Crear cuenta nueva                       │
│      → pedir email + password + nombre negocio│
│      → POST /api/v1/cloud/register            │
│      → recibe install_token                   │
│      → continúa instalación normal            │
│                                               │
│  [2] Ya tengo cuenta                          │
│      → pedir email + password                 │
│      → POST /api/v1/cloud/login               │
│      → POST /api/v1/cloud/register-branch     │
│      → recibe install_token para esta sucursal│
│      → continúa instalación normal            │
│                                               │
│  [3] Omitir                                   │
│      → instalación sin Nube PosVendelo             │
│      → muestra código de vinculación          │
│      → se puede vincular después desde la app │
└───────────────────────────────────────────────┘
```

### 4.2 Endpoint adicional para opción [2]
- `POST /api/v1/cloud/register-branch` (cloud session auth)
- Crea nueva branch en el tenant del dueño
- Retorna `{branch_id, install_token}` para que el instalador continúe

### 4.3 Desde la app POS (configuración)
- Nueva sección "Nube PosVendelo" en la pestaña de configuración
- Botón "Vincular con Nube PosVendelo" → genera código de 6 dígitos (POST /branches/generate-link-code)
- Muestra el código + instrucciones para ingresarlo en la App Dueño
- IPC nuevo: `agent:generateLinkCode` en localAgent.ts

### Archivos a modificar
- `installers/linux/install-titan.sh` (sección Nube PosVendelo interactiva)
- `installers/windows/Install-Titan.ps1` (lo mismo en PowerShell)
- `frontend/src/main/localAgent.ts` (nuevo IPC generateLinkCode)
- `frontend/src/preload/index.ts` (exponer método)
- `frontend/src/renderer/src/tabs/` (sección config Nube PosVendelo)

---

## Fase 5: Despliegue

### 5.1 Dominio
- Comprar dominio en Cloudflare (ej: `titanpos.mx`, ~$10/año)
- Subdominio `api.titanpos.mx` → endpoint `/api/v1/cloud/discover` (puede ser Cloudflare Worker o Pages con JSON estático)

### 5.2 CF Tunnel para el control-plane
- Crear tunnel `titan-cloud` en Zero Trust
- Ruta: `titancloud.titanpos.mx` → `http://control-plane-api-1:9090`
- En `control-plane/docker-compose.yml` agregar servicio `cloudflared`:
  ```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CF_TUNNEL_TOKEN}
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped
  ```

### 5.3 Variables de entorno nuevas (control-plane)
```env
CP_CLOUD_SESSION_TTL_SECONDS=86400
CP_CLOUD_REGISTRATION_ENABLED=true
CP_PUBLIC_URL=https://titancloud.titanpos.mx
```

### 5.4 Discover endpoint
- `api.titanpos.mx/discover` retorna:
  ```json
  {"cp_url": "https://titancloud.titanpos.mx", "version": "1.0"}
  ```
- Esto puede ser un Cloudflare Worker (gratis) o un JSON en Cloudflare Pages

### 5.5 CORS del control-plane
- Agregar los orígenes de la App Dueño a `CP_CORS_ALLOWED_ORIGINS`
- En Electron: `file://` y `app://`
- En PWA: el dominio desde donde se sirve la PWA

---

## Modelo de seguridad

| Capa | Mecanismo |
|------|-----------|
| Passwords | bcrypt rounds=12 |
| Sessions cloud | HMAC-SHA256 (mismo `sign_owner_session`), TTL 24h |
| Rate limiting | 5 registros/h, 10 logins/min (slowapi existente) |
| Link codes | 6 chars uppercase, TTL 15min, single-use |
| Cola de comandos | Solo cloud_account del mismo tenant puede encolar |
| Tenant isolation | Todos los queries filtran por tenant_id del token firmado |
| CF Tunnel | URL no publicada, solo la app la conoce vía discover |
| Auditoría | Todos los eventos en `audit_log` vía `log_audit_event` |
| Comandos | Validación de tipos permitidos, payload sanitizado |

---

## Secuencia de implementación

| # | Fase | Entregable | Dependencias |
|---|------|------------|--------------|
| 1 | DB + Auth Backend | cloud_accounts, login, register, link-node, discover | Ninguna |
| 2 | Cola de Comandos | command_queue, poll desde nodo, endpoints | Fase 1 |
| 3 | App del Dueño | React app con Electron + PWA | Fases 1 y 2 |
| 4 | Integración Instalador | Registro Nube PosVendelo en instalador + config tab | Fase 1 |
| 5 | Despliegue | Dominio, CF Tunnel, discover endpoint | Fase 3 |

Fases 3 y 4 pueden trabajarse en paralelo ya que son frontend independientes.

---

## Verificación

### Tests backend
```bash
cd control-plane && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && \
  python3 -m pytest tests/test_cloud_auth.py tests/test_commands.py tests/test_security.py tests/test_owner.py -q
```

### Tests App Dueño
```bash
cd owner-app && npx vitest run
```

### Smoke test E2E
1. `POST /cloud/register` con email+password → crear cuenta + tenant + branch
2. `POST /cloud/login` → obtener session token
3. `GET /owner/portfolio` con token cloud → ver sucursales
4. `POST /branches/generate-link-code` (install_token del nodo) → código de 6 dígitos
5. `POST /cloud/link-node` (token cloud + código) → vincular segunda sucursal
6. `POST /cloud/commands` → encolar comando remoto
7. Nodo poll `GET /commands/pending` → ejecuta → `POST /commands/{id}/ack`
8. App Dueño muestra resultado del comando

### Funciones existentes a reutilizar
- `sign_owner_session` / `verify_owner_session_token` → `control-plane/security.py`
- `ensure_trial_license` → `control-plane/license_service.py`
- `log_audit_event` → `control-plane/audit.py`
- `_heartbeat_loop` (patrón para command_poll) → `backend/main.py`
- `OwnerPortfolioTab.tsx` (UI base) → `frontend/src/renderer/src/tabs/OwnerPortfolioTab.tsx`
- Tenant/branch creation lógica → `control-plane/modules/tenants/routes.py`
