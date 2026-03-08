# Arquitectura Estratégica Móvil y Redes — TITAN POS

**Documento de Planificación Arquitectónica v2**
**Fecha:** Marzo 2026
**Ecosistema:** TITAN POS (Electron + React / FastAPI / PostgreSQL)
**Topología:** Híbrida (LAN local + Cloudflare Tunnel + Control Plane centralizado)
**Escala objetivo:** 100 → 10,000 tenants activos (~25,000 sucursales)

---

## 1. Visión del Ecosistema

TITAN POS se expande de terminales Electron de escritorio hacia dispositivos móviles
(PDAs industriales y smartphones). La arquitectura debe garantizar:

- **Offline-first**: ventas sin internet en sucursal
- **Zero-config para el cliente**: sin VPNs, sin puertos, sin DNS manual
- **Multi-tenant**: aislamiento total entre empresas clientes
- **Escala horizontal**: de 2 sucursales a cientos sin cambiar arquitectura

### Separación en 2 aplicaciones móviles

| | App 1: Trinchera | App 2: Comando |
|---|---|---|
| **Usuarios** | Cajeros móviles, bodegueros | Dueños, gerentes regionales, auditores |
| **Hardware** | PDAs Android (Sunmi, Zebra) con escáner + impresora BT | Smartphones estándar (iOS/Android) |
| **UX** | Táctil industrial: botones grandes, flujo lineal (Escanear → Cobrar → Imprimir) | Analítico: dashboards KPI, autorizaciones remotas, reportes Z consolidados |
| **Seguridad** | Menús admin bloqueados. Imposible escalar privilegios | Auth biométrica. Conexión al Control Plane |
| **Red** | Prioriza LAN local de sucursal | Siempre vía Cloudflare Tunnel (HTTPS público) |

---

## 2. Topología de Red

### Principio fundamental: Control Plane vs Data Plane

```
                    ┌──────────────────────────────────────┐
                    │         CLOUDFLARE EDGE               │
                    │         (router público)               │
                    │                                        │
                    │  sucursal-a.example.pos  ─► Sucursal A │
                    │  sucursal-b.example.pos  ─► Sucursal B │
                    │  cliente-002.example.pos ─► Cliente 2  │
                    │  admin.example.pos       ─► Control LB │
                    └──────────┬─────────────────────────────┘
                               │
              ┌────────────────▼──────────────────────────┐
              │  CONTROL PLANE (Horizontal)                │
              │  admin.example.pos                         │
              │                                            │
              │  ┌─────────────────────────────────────┐   │
              │  │  Load Balancer (nginx / HAProxy)     │   │
              │  │  health checks + round-robin          │   │
              │  └────┬──────────┬──────────┬───────────┘   │
              │       │          │          │               │
              │  ┌────▼───┐ ┌───▼────┐ ┌───▼────┐          │
              │  │ API-1  │ │ API-2  │ │ API-N  │  ← stateless  │
              │  │FastAPI │ │FastAPI │ │FastAPI │  (sin estado   │
              │  │        │ │        │ │        │   en memoria)  │
              │  └────┬───┘ └───┬────┘ └───┬────┘          │
              │       │         │          │               │
              │  ┌────▼─────────▼──────────▼───────────┐   │
              │  │  Redis (sessions, rate limits,        │   │
              │  │         token revocation, pub/sub)    │   │
              │  └─────────────────────────────────────┘   │
              │                                            │
              │  ┌─────────────────────────────────────┐   │
              │  │  PostgreSQL central                  │   │
              │  │  (metadata tenants, licencias, sync) │   │
              │  │  + read replica para dashboards      │   │
              │  │  NO datos de ventas de tenants        │   │
              │  └─────────────────────────────────────┘   │
              └────────────────────────────────────────────┘

┌─ DATA PLANE ─────────────────────────────────────────────┐
│                                                           │
│  ┌─ Sucursal A ──────────┐   ┌─ Sucursal B ──────────┐   │
│  │ FastAPI + PostgreSQL   │   │ FastAPI + PostgreSQL   │   │
│  │ (datos de ESTE local)  │   │ (datos de ESTE local)  │   │
│  │                        │   │                        │   │
│  │ cloudflared ───────► CF│   │ cloudflared ───────► CF│   │
│  │ (túnel saliente)       │   │ (túnel saliente)       │   │
│  │                        │   │                        │   │
│  │ Electron POS           │   │ Electron POS           │   │
│  │ Cajeros móviles (LAN)  │   │ Cajeros móviles (LAN)  │   │
│  └────────────────────────┘   └────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

**Flujo de tráfico — el homelab NO es cuello de botella:**

- Dueño consulta ventas de Sucursal A → Cloudflare → túnel directo a Sucursal A
- Cajero en tienda vende → LAN local, sin internet
- Cajero en ruta con 4G → Cloudflare → túnel a su sucursal
- Sync periódico → Sucursal ↔ Control Plane (homelab inicialmente, luego VPS)

El tráfico pesado (ventas, inventario) nunca pasa por el homelab. Solo metadata
administrativa y sincronización periódica.

### Capa 1: Red local de sucursal (LAN)

La App 1 (Trinchera) opera en la red WiFi de la tienda conectándose directamente
al servidor FastAPI local por IP (`192.168.x.x:8090`).

- Latencia: <2ms
- Si el internet se corta, las PDAs y terminales Electron siguen vendiendo
- La IP local se obtiene mediante **QR de emparejamiento** (ver sección 3)
- Sin dependencia de mDNS/ZeroConf (frágil en Android 12+)

### Capa 2: Acceso remoto via Cloudflare Tunnel

Para acceso fuera de la sucursal (dueño, bodega remota, cajero en ruta),
cada sucursal ejecuta `cloudflared` dentro de su Docker Compose.

```yaml
# docker-compose.yml del cliente (autogenerado por el Control Plane)
services:
  api:
    image: ghcr.io/titan-pos/backend:stable
    ports:
      - "8090:8090"         # LAN local
    environment:
      - DATABASE_URL=postgresql://titan_user:${DB_PASSWORD}@db:5432/titan_pos
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - db
    restart: unless-stopped
    labels:
      - "com.centurylinklabs.watchtower.scope=titan"

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=titan_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=titan_pos
    volumes:
      - pgdata:/var/lib/postgresql/data

  tunnel:
    image: cloudflare/cloudflared:latest
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${CF_TUNNEL_TOKEN}
    depends_on:
      - api
    restart: unless-stopped

  db-backup:
    image: prodrigestivill/postgres-backup-local:15
    environment:
      - POSTGRES_HOST=db
      - POSTGRES_DB=titan_pos
      - POSTGRES_USER=titan_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - SCHEDULE=0 */6 * * *       # cada 6 horas
      - BACKUP_KEEP_DAYS=7
      - POSTGRES_EXTRA_OPTS=-Fc    # formato custom comprimido (~85% reducción)
      - HEALTHCHECK_PORT=8080
    volumes:
      - ./backups:/backups
    depends_on:
      - db

  watchtower:
    image: containrrr/watchtower
    environment:
      - DOCKER_CONTENT_TRUST=1
      - WATCHTOWER_LABEL_ENABLE=true
      - WATCHTOWER_POLL_INTERVAL=3600
      - WATCHTOWER_SCOPE=titan
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped

volumes:
  pgdata:
```

**Ventajas sobre Tailscale para el cliente final:**

| | Tailscale | Cloudflare Tunnel |
|---|---|---|
| El cliente instala algo? | Sí — app + login + aprobar nodos | No — ya está en el Docker Compose |
| Configuración del usuario | Media (consola Tailscale) | Cero |
| Puertos abiertos | Ninguno | Ninguno |
| HTTPS automático | No (solo WireGuard) | Sí (certificado automático) |
| DDoS protection | No | Sí (gratis) |
| Costo (100 tenants) | Gratis | Gratis (free tier: hasta 1,000 túneles; Enterprise si >1,000) |

**Tailscale se mantiene para uso interno:** el equipo de soporte de TITAN usa
Tailscale para acceder a los servidores de clientes para diagnóstico y
mantenimiento. El cliente no lo ve ni lo gestiona.

### Capa 3: Control Plane (Horizontal desde el diseño)

El Control Plane es un servicio separado: **Titan Control Plane**, diseñado
como un cluster horizontal de workers stateless desde el día uno.

Responsabilidades:
- Registro y gestión de tenants (empresas clientes)
- Provisión automática de túneles Cloudflare via API
- Generación de instaladores con tokens inyectados
- Licenciamiento (license.json firmado RSA)
- Sync bidireccional (aggregation de datos de todas las sucursales de un tenant)
- Dashboard multi-tenant para el dueño (consolida KPIs de todas sus sucursales)
- Ingestion de heartbeats de toda la flota (~83 req/seg a 25K sucursales)

#### Arquitectura stateless

```
                     nginx (L7 Load Balancer)
                    /          |          \
               API-1       API-2       API-N      ← FastAPI workers (stateless)
                    \          |          /
                     Redis 7 (session store)       ← sessions, rate limits,
                                                     token blacklist, pub/sub
                     PostgreSQL 15 (shared)        ← metadata tenants, licencias,
                                                     heartbeats, audit_log
                       └─ read replica             ← dashboards, reportes
```

**Principios:**
- **Cero estado en memoria** — sessions JWT en Redis, rate limits en Redis,
  token revocation list en Redis. Cualquier worker puede atender cualquier request.
- **Scale-out lineal** — agregar un worker = +1 container detrás del LB.
  No requiere cambiar código ni schema.
- **Rolling deploys** — nginx drains connections al worker viejo mientras
  el nuevo levanta. Zero-downtime.
- **Health checks** — nginx verifica `/health` cada 5s, retira workers no-healthy.

#### Stack del Control Plane

```yaml
# docker-compose.control-plane.yml
services:
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
    restart: unless-stopped

  api:
    image: ghcr.io/titan-pos/control-plane:stable
    deploy:
      replicas: 2                    # escalar según carga
    environment:
      - DATABASE_URL=postgresql://cp_user:${DB_PASSWORD}@db:5432/titan_cp
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${CP_JWT_SECRET}
      - CF_API_TOKEN=${CF_API_TOKEN}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=cp_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=titan_cp
    volumes:
      - cpdata:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data
    restart: unless-stopped

volumes:
  cpdata:
  redisdata:
```

**Escala progresiva:**

| Tenants | Workers API | Redis | PostgreSQL | Infra |
|---------|-------------|-------|------------|-------|
| 1-500 | 2 (homelab) | 1 (homelab) | 1 (homelab) | Homelab actual |
| 500-2,000 | 3-4 (VPS) | 1 (VPS) | 1 (VPS) | VPS dedicado ~$50/mes |
| 2,000-5,000 | 4-6 (VPS) | 1 (VPS, 512MB) | Primary + 1 read replica | VPS ~$100/mes + replica $50 |
| 5,000-10,000 | 6-10 (2 VPS) | Redis Sentinel (3 nodos) | Primary + 2 read replicas | 2 VPS + DB dedicada ~$300/mes |

> **Nota:** El Data Plane (cada sucursal) ya es horizontal por naturaleza —
> cada tenant es una instancia Docker independiente. El Control Plane es el
> único componente que necesita diseño horizontal explícito.

---

## 3. Vinculación de Dispositivos Móviles (QR Pairing)

En vez de auto-descubrimiento por red (mDNS), los dispositivos se emparejan
escaneando un QR generado por el POS de escritorio.

### Flujo

```
POS Electron (Ajustes → "Vincular dispositivo")
    │
    ▼ genera QR con:
    │
    │  {
    │    "v": 1,
    │    "lan": "http://pos-sucursal.local:8090",
    │    "wan": "https://sucursal-a.example.pos",
    │    "branch": 1,
    │    "pair": "a1b2c3d4e5f6",    ← token temporal (5 min, 1 uso)
    │    "exp": 1741305600
    │  }
    │
    ▼
Dispositivo móvil escanea QR
    │
    ├─ Guarda URLs en AsyncStorage
    ├─ POST /api/v1/auth/pair  {pairing_token, device_id}
    ├─ Backend valida token, registra dispositivo
    └─ Retorna: "Dispositivo vinculado. Inicie sesión."
    │
    ▼
Cajero hace login con usuario/PIN
    │
    ▼
Listo — la app intenta LAN primero, fallback a WAN
```

**Seguridad del QR:**
- El pairing token expira en 5 minutos y es de un solo uso
- El QR no contiene credenciales — solo la dirección del servidor
- Después del pairing, el cajero aún debe autenticarse con su usuario/PIN
- Si alguien fotografía el QR, el token ya expiró

### Escenarios de conexión

| Escenario | URL usada | Ruta |
|-----------|-----------|------|
| Cajero en tienda (WiFi) | `lan` → 192.168.x.x | LAN directa, sin internet |
| Cajero en ruta (4G) | `wan` → dominio público configurado | Cloudflare → túnel → sucursal |
| Bodeguero remoto | `wan` → dominio público configurado | Cloudflare → túnel → sucursal |
| Dueño (App 2) | `wan` → panel administrativo configurado | Cloudflare → Control Plane |

---

## 4. Onboarding Automatizado de Clientes

Cero intervención manual por tenant. Todo via API de Cloudflare.

```
Portal web: portal.example.pos/registro
    │
    ▼
1. Dueño llena formulario:
   - Nombre: "Comercio Demo"
   - Sucursales: 2 (Sucursal A, Sucursal B)
   - Plan: Pro
    │
    ▼
2. Control Plane ejecuta automáticamente:
   - Crea tenant en DB central
   - POST api.cloudflare.com/tunnels → tunnel "tenant-demo-001"
   - POST api.cloudflare.com/dns → tenant-demo-001.example.pos
   - Genera JWT_SECRET único para el tenant
   - Genera license.json firmado RSA
   - Genera docker-compose.yml con tokens inyectados
   - Empaqueta instalador (.sh o .zip)
    │
    ▼
3. Dueño descarga y ejecuta:
   $ ./instalar-titan.sh
   → docker compose pull
   → docker compose up -d
   → "TITAN POS listo en la URL local configurada"
   → "Acceso remoto: https://tenant-demo-001.example.pos"
    │
    ▼
4. Abre POS → genera QR → escanea con celular → listo
```

### Automatización Cloudflare (API)

```bash
# Crear túnel
curl -X POST "https://api.cloudflare.com/client/v4/accounts/{id}/tunnels" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -d '{"name": "tenant-demo-001", "tunnel_secret": "auto"}'
# → devuelve tunnel_token

# Crear DNS
curl -X POST "https://api.cloudflare.com/client/v4/zones/{id}/dns_records" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -d '{"type": "CNAME", "name": "tenant-demo-001", "content": "{tunnel_id}.cfargotunnel.com"}'
```

Ambas llamadas se encapsulan en un endpoint del Control Plane:
`POST /api/v1/admin/tenants` → crea todo de un golpe.

---

## 5. Stack Tecnológico Móvil

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Framework | React Native + Expo (EAS) | Reusar React Hooks, TypeScript y lógica del frontend Electron |
| Navegación | React Navigation v7+ | Stack nativo Android/iOS, deep linking |
| Red / API | `@titan/api-client` (extraído de posApi.ts) | Reusar `apiFetch`, `apiFetchLong`, semáforo, error handling. Sin Axios. Requiere adapter pattern para storage (localStorage → AsyncStorage) |
| Validación | Pydantic en backend (ya existe) | No duplicar con Zod — validar en la frontera del servidor |
| Hardware | react-native-ble-manager / expo-print | ESC/POS via Bluetooth para impresoras térmicas |
| Escáner | expo-camera + expo-barcode-scanner | Cámara para QR pairing + códigos de barras |
| UI | NativeWind (Tailwind) | Reutilización parcial (~60%) de clases CSS — Flexbox nativo difiere de CSS Flexbox en defaults |
| Storage | AsyncStorage (config) + SQLite (offline queue) | Persistencia local para cola de ventas offline |

### Decisión: posApi compartido vs Axios

El frontend Electron ya tiene `posApi.ts` con 2,300+ líneas de lógica probada:
- `apiFetch` (3s timeout) / `apiFetchLong` (15s timeout)
- Semáforo de concurrencia (max 20 requests)
- `safeSetItem()` para localStorage resiliente
- Auto-discovery de backend
- Manejo de errores en español

Reescribir esto con Axios + interceptores duplica esfuerzo y diverge. La estrategia
correcta es extraer `posApi.ts` a un paquete compartido `@titan/api-client`
importable tanto por Electron (Vite) como por React Native (Metro).

---

## 6. Hoja de Ruta por Hitos

### HITO 0: Prerequisitos de Backend (antes de cualquier app móvil)

Cambios necesarios en el backend actual para soportar multi-tenant:

| Cambio | Descripción | Esfuerzo |
|--------|-------------|----------|
| JWT con `branch_id` | Token actual solo tiene `sub` y `role`. Agregar `branch_id` y `tenant_id` | 1 día |
| Redis para token revocation | El dict en memoria no sobrevive multi-worker. Migrar a Redis | 1 día |
| Endpoint `POST /auth/pair` | Genera/valida pairing tokens temporales para vincular móviles | 1 día |
| `GET/DELETE /auth/devices` | Lista dispositivos vinculados / revocar dispositivo robado | 1 día |
| `POST /auth/emergency-reset` | Recovery de PIN/contraseña con challenge del Control Plane | 1 día |
| `GET /auth/pair-qr` | Servir QR como imagen PNG (alternativa para POS headless) | 2 horas |
| Tabla `device_pairings` | `device_id, branch_id, user_id, hardware_fingerprint, paired_at, last_seen` | Migración |
| Modelo de tenants | Instancia-por-tenant: cada cliente tiene su propio Docker stack | 1 semana |
| Sync con `node_id` | Reemplazar `synced=0/1` binario por `sync_checkpoints(node_id, table, last_id)` | 1 semana |

### HITO 1: Control Plane + Cloudflare Automation

1. Crear servicio `titan-control-plane` (FastAPI separado) en el homelab
2. DB central PostgreSQL con tablas: `tenants`, `branches`, `licenses`, `tunnel_configs`
3. API de onboarding: `POST /admin/tenants` → crea tunnel CF + DNS + instalador
4. Dashboard web admin para gestionar tenants (React simple)

> **Nota:** Hito 1 y Hito 2 son independientes — pueden ejecutarse en paralelo.

### HITO 2: Paquete Compartido `@titan/api-client`

1. Crear monorepo o carpeta `/packages/api-client`
2. Extraer de posApi.ts: tipos, funciones API, auth helpers, error handling
3. Implementar `StorageAdapter` interface para abstraer storage (`localStorage` en Electron, `AsyncStorage` en React Native)
4. Adaptar para funcionar con `fetch` nativo (compatible Node, Electron, React Native)
5. Smart URL selector: `tryFetch(lanUrl) → catch → tryFetch(wanUrl)`
6. Publicar como paquete interno (npm workspace o path import)

### HITO 3: App 1 — Trinchera (Cajero/Bodeguero)

1. Login con PIN táctil (teclado numérico grande)
2. Escáner de código de barras + búsqueda por nombre
3. Carrito + cobro (efectivo/tarjeta/mixto) con teclado numérico
4. Impresión Bluetooth ESC/POS del ticket
5. Vista de bodega: inventario con colores verde (entrada) / rojo (salida)
6. QR scanner para pairing inicial

### HITO 4: App 2 — Comando (Dueño/Gerente)

**Prerequisito:** Configurar proyecto Firebase + FCM (Cloud Messaging) antes de iniciar push notifications.

1. Dashboard KPIs: efectivo vivo, ventas del día, diferencia Z por sucursal
2. Selector de sucursal/tenant en header (re-enruta toda la app)
3. Push notifications via Firebase Cloud Messaging para alertas de cancelación
4. Autorización remota: "Aprobar/Rechazar cancelación del ticket #1391"
5. Reportes Z consolidados multi-sucursal

---

## 7. Seguridad por Capas

| Capa | Mecanismo |
|------|-----------|
| Transporte | HTTPS automático via Cloudflare (sin certificados manuales) |
| Autenticación | JWT con `tenant_id` + `branch_id` + PIN hash SHA-256 |
| Device binding | Pairing token de un solo uso + registro de `device_id` + hardware fingerprint |
| DDoS | Cloudflare absorbe en la capa de red (gratis) |
| Zero-trust | Cloudflare Access opcional (2FA antes de llegar al API) |
| Puertos | Cero puertos abiertos en la red del cliente (túnel saliente) |
| Tenant isolation | Instancia-por-tenant: DB separada, JWT_SECRET separado |
| Soporte remoto | Tailscale (solo equipo interno, invisible para el cliente) |
| CORS | Configurar `CORS_ALLOWED_ORIGINS` por tenant (no usar `*` ni `null`) |

### Gaps de seguridad a resolver antes de producción

| Gap | Riesgo | Mitigación propuesta | Estado |
|-----|--------|---------------------|--------|
| CF_TUNNEL_TOKEN en docker-compose.yml | Expuesto si acceden al FS del cliente | Usar Docker secrets o archivo `.env` con permisos `600` | Pendiente |
| Instalador `.sh` sin firma | Supply chain attack — reemplazo del script | Firmar con GPG, verificar checksum antes de ejecutar | Pendiente |
| Rate limiting en `/auth/pair` | Fuerza bruta del pairing token | Rate limit: 5 intentos/min por IP | Pendiente |
| Device binding sin hardware ID | Un device_id puede clonarse | Bind a ANDROID_ID/identifierForVendor además de UUID | Pendiente |
| Watchtower sin verificar imagen | Imagen maliciosa en GHCR | Docker Content Trust (DCT) para firmar imágenes | Pendiente |
| ~~CORS `null` en whitelist~~ | ~~Peticiones desde `file://`~~ | ~~Eliminado del whitelist~~ | **Resuelto** |
| Token revocation en memoria | Funciona en single-process pero no en multi-worker ni sobrevive restarts | Redis SET con TTL = token expiry (ya incluido en arquitectura horizontal del Control Plane) | Parcial |
| Recovery de PIN/contraseña perdida | Dueño queda fuera de su POS | Endpoint `POST /auth/emergency-reset` con challenge-response via RSA del Control Plane, o reset vía soporte Tailscale | Pendiente |
| Desvinculación de dispositivo robado | JWT válido sigue funcionando hasta expirar | Endpoints `GET/DELETE /auth/devices/{id}` + invalidar todos los JTI del device | Pendiente |
| QR pairing en POS headless/kiosk | No hay pantalla para mostrar el QR | Alternativa: `GET /api/v1/auth/pair-qr` sirve QR como PNG, o imprimirlo en ticket | Pendiente |

---

## 8. Escalabilidad

### Data Plane (horizontal por naturaleza)

Cada tenant nuevo = un Docker Compose más. No requiere cambios en schema ni código.
Las actualizaciones se distribuyen via GHCR + Watchtower (auto-pull con DCT).

| Escala tenants | Infra por tenant | Cloudflare |
|----------------|-----------------|------------|
| 1-400 | Docker stack local por sucursal | Free tier (~1,000 túneles) |
| 400+ | Docker stack local | Enterprise (>1,000 túneles) |

### Control Plane (horizontal por diseño)

| Escala | Workers API | Redis | PostgreSQL | Infra | Costo/mes |
|--------|-------------|-------|------------|-------|-----------|
| 1-500 | 2 réplicas | 1 instancia | 1 instancia | Homelab | $0 |
| 500-2,000 | 3-4 réplicas | 1 instancia | 1 instancia | VPS dedicado | ~$50 |
| 2,000-5,000 | 4-6 réplicas | 1 (512MB) | Primary + 1 read replica | VPS + DB réplica | ~$150 |
| 5,000-10,000 | 6-10 réplicas | Sentinel (3 nodos) | Primary + 2 read replicas | 2 VPS + DB dedicada | ~$300 |

**Escalamiento en la práctica:** para pasar de 2,000 a 5,000 tenants solo se necesita:
1. `docker compose up -d --scale api=6` (más workers)
2. Configurar read replica PostgreSQL (streaming replication)
3. Actualizar nginx upstream — zero-downtime

No se reescribe código, no se cambia schema, no se migra nada.

> **Nota:** El free tier de Cloudflare soporta hasta ~1,000 túneles por cuenta.
> A ~400 tenants (×2.5 sucursales = 1,000 túneles) se requiere Cloudflare Enterprise.

---

## Apéndice: Decisiones Descartadas y Razones

| Opción descartada | Razón |
|-------------------|-------|
| mDNS / ZeroConf para discovery | Frágil en Android 12+, no funciona con AP isolation |
| Tailscale para clientes | Requiere instalación y gestión por parte del usuario |
| Axios + interceptores | Duplica la lógica probada de posApi.ts |
| Zod para validación | Duplica Pydantic del backend, mantenimiento doble |
| Multi-tenant single-DB | Requiere refactoring masivo del schema (15+ tablas). Instancia-por-tenant mantiene el código actual intacto |
| Traefik en homelab como proxy de tráfico | El homelab no debe ser cuello de botella de tráfico. Cloudflare hace el routing |
| WebSocket para push notifications | No escala a 10K conexiones desde un homelab. Firebase/FCM es la opción correcta para push a escala |
| React Navigation v6 | Desactualizada (v7 disponible desde enero 2025) |

---

## Documentos Complementarios

- **[MITIGACION_RIESGOS_10K.md](MITIGACION_RIESGOS_10K.md)** — Matriz de riesgos, backups, DR, legal, monitoreo y costos a escala 10K tenants

---
*Fin del documento v2.*
