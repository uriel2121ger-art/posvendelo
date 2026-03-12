# Mitigación de Riesgos y Daños — POSVENDELO @ 10,000 Tenants

**Documento de Planificación v1**
**Fecha:** Marzo 2026
**Escala objetivo:** 10,000 tenants activos (~25,000 sucursales estimadas)
**Complemento de:** `ARQUITECTURA_MOVIL_REDES.md`

---

## 0. Supuestos de escala

| Métrica | Valor estimado |
|---------|---------------|
| Tenants (empresas) | 10,000 |
| Sucursales (instancias) | ~25,000 (promedio 2.5 sucursales/tenant) |
| Túneles Cloudflare | ~25,000 (1 por sucursal) |
| Tickets diarios por sucursal | 500-2,000 (rango real MiPyME/PyME en México) |
| Ventas diarias totales | ~25M tickets (25K sucursales × 1,000 avg) |
| Crecimiento DB por sucursal | ~2-5GB/mes (a 1,000 tickets/día con items) |
| Storage cloud backup (si 30% contrata) | ~41TB (ver sección 5 para desglose) |
| Usuarios concurrentes pico | ~50,000 (2 cajeros/sucursal promedio) |
| Control Plane requests/seg | ~500 (sync + licencias + dashboard), distribuidos entre N workers stateless |

---

## 1. Matriz de Riesgos — Impacto × Probabilidad

### Riesgo Catastrófico (Afecta >1,000 tenants)

| ID | Riesgo | Probabilidad | Impacto | RPN |
|----|--------|-------------|---------|-----|
| C1 | Update corrupto vía Watchtower a todos los tenants | Media | Catastrófico | **Crítico** |
| C2 | Compromiso de la clave RSA de licencias | Baja | Catastrófico | **Crítico** |
| C3 | Cloudflare Enterprise revoca cuenta o falla global | Muy baja | Catastrófico | **Alto** |
| C4 | Control Plane hackeado — acceso a metadata de todos los tenants | Baja | Catastrófico | **Crítico** |
| C5 | Supply chain attack en imagen Docker base | Baja | Catastrófico | **Crítico** |

### Riesgo Alto (Afecta 1 tenant completo)

| ID | Riesgo | Probabilidad | Impacto | RPN |
|----|--------|-------------|---------|-----|
| A1 | DB corrupta en sucursal — pérdida de ventas | Media | Alto | **Alto** |
| A2 | Tenant comprometido — acceso no autorizado a datos | Media | Alto | **Alto** |
| A3 | Fallo de hardware del servidor local del cliente | Alta | Alto | **Alto** |
| A4 | Internet de sucursal cae por días | Alta | Medio | **Medio** |
| A5 | Empleado deshonesto manipula ventas/inventario | Alta | Alto | **Alto** |

### Riesgo Operativo (Afecta servicio parcialmente)

| ID | Riesgo | Probabilidad | Impacto | RPN |
|----|--------|-------------|---------|-----|
| O1 | Backup automático falla silenciosamente | Alta | Alto | **Alto** |
| O2 | Migración de DB rompe schema en subset de tenants | Media | Alto | **Alto** |
| O3 | Token revocation no propaga a tiempo | Media | Medio | **Medio** |
| O4 | Sync bidireccional crea conflictos de datos | Alta | Medio | **Medio** |
| O5 | Rate limiting insuficiente — DDoS al Control Plane | Media | Alto | **Alto** |

---

## 2. Mitigaciones por Capa

### 2.1 Capa de Distribución de Software (C1, C5)

**Problema a 10K:** Un `docker push` malo + Watchtower = 25,000 sucursales rotas en <1 hora.

#### Canary Pipeline Obligatorio

```
CI/CD Pipeline (GitHub Actions)
    │
    ├─ Build + Tests (204 backend + 85 frontend)
    │
    ├─ SAST scan (Trivy container + Bandit python + ESLint security)
    │
    ├─ Firma con cosign (Sigstore keyless)
    │   └─ cosign sign --yes ghcr.io/uriel2121ger-art/posvendelo:${SHA}
    │
    ├─ Push tag: `canary`
    │   └─ 10 tenants beta (~25 sucursales) actualizan
    │   └─ Monitoreo automático 24h: error rate, latencia, crashes
    │
    ├─ Si canary OK → Push tag: `stable-preview`
    │   └─ 500 tenants (~1,250 sucursales, 5% del total) actualizan
    │   └─ Monitoreo automático 48h
    │
    ├─ Si preview OK → Push tag: `stable`
    │   └─ 9,500 tenants restantes actualizan en waves de 1,000 tenants/hora
    │
    └─ Rollback automático:
        └─ Si error rate > 1% en canary → revert tag a versión anterior
        └─ Watchtower de los canary pull el tag anterior en <5 min
```

#### Verificación de Imágenes

Watchtower se incluye en el `docker-compose.yml` canónico (ver ARQ sección 2) con:
- `DOCKER_CONTENT_TRUST=1` — solo pull imágenes firmadas con cosign
- `WATCHTOWER_LABEL_ENABLE=true` — solo actualiza containers con label `titan`
- `WATCHTOWER_POLL_INTERVAL=3600` — check cada hora (no cada 5 min)

#### Supply Chain

- Imagen base: `python:3.13-slim` pinneado por digest (no por tag)
- Dependencias Python: `pip install --require-hashes -r requirements.txt`
- Dependencias Node: `npm ci` con `package-lock.json` commiteado
- Escaneo Trivy en cada PR + bloqueo si vulnerabilidad Critical/High

### 2.2 Capa de Secretos y Criptografía (C2, C4)

**Problema a 10K:** La clave RSA de licencias firma 10,000 `license.json`. Si se compromete, cualquiera genera licencias válidas.

#### Gestión de Secretos

| Secreto | Almacenamiento | Rotación |
|---------|---------------|----------|
| RSA key (licencias) | AWS KMS o Vault — nunca en disco | Yearly + re-sign todas las licencias |
| CF_API_TOKEN (Cloudflare) | Vault / Docker secret en Control Plane | Cada 90 días |
| CF_TUNNEL_TOKEN (por tenant) | Docker secret en cada sucursal — no en .env | Único por tunnel, no se rota (CF lo maneja) |
| JWT_SECRET (por tenant) | Generado en onboarding, almacenado cifrado en DB central | Rotación anual con periodo de gracia (acepta old+new 24h) |
| DB passwords (por tenant) | Generado random 32 chars, en Docker secret | Al crear tenant, no se rota (acceso solo local) |

#### Cifrado en Reposo

```
Control Plane DB:
  - PostgreSQL con pg_tde (Transparent Data Encryption) o LUKS en disco
  - Columnas sensibles (tunnel_tokens, jwt_secrets): cifradas con Fernet (AES-128-CBC)
  - Master key en AWS KMS — nunca en el mismo servidor

Tenant DBs (local):
  - LUKS en el volumen Docker del PostgreSQL (opcional, recomendado)

Módulo cloud backup:
  - Dump cifrado con age (clave pública del TENANT, generada en onboarding) ANTES de enviar
  - En el homelab RAID5 se almacena como blob cifrado — POSVENDELO NO puede leer los datos
  - El tenant conserva su clave privada localmente (en Docker secret)
  - Si el tenant pierde su clave, el backup es irrecuperable (documentar en contrato)
```

#### Acceso al Control Plane (arquitectura horizontal)

- SSH solo via Tailscale (no puerto 22 público)
- 2FA obligatorio (TOTP) para el dashboard admin web
- Audit log de toda acción administrativa (crear tenant, revocar tunnel, emitir licencia)
- Principio de mínimo privilegio: el CF_API_TOKEN tiene scope solo para tunnels+DNS, no para toda la cuenta CF
- **Workers stateless**: sessions y tokens en Redis — no en memoria del proceso
- **Rate limits centralizados**: Redis como backend de slowapi — consistente entre todos los workers
- **Secretos inyectados**: CF_API_TOKEN, JWT_SECRET, RSA key — via Docker secrets o env vars, nunca hardcoded

### 2.3 Capa de Datos y Backups (A1, A3, O1)

**Principio:** Cada tenant es responsable de sus propios datos. El sistema corre localmente
y siempre está activo — la pérdida de datos por caída del servidor es improbable en
operación normal. Backups locales son automáticos y gratuitos. Backup remoto es un servicio
de pago opcional.

#### Backup Local (incluido — todos los tenants)

```
Capa 1: pg_dump automático cada 6h → /backups/ (mismo disco o USB externo)
  └─ Cronjob dentro del container de PostgreSQL
  └─ Retención: 7 días rolling (28 snapshots)
  └─ Rotación automática: elimina dumps > 7 días
  └─ Costo para el tenant: $0

Capa 2 (opcional): WAL archiving para tenants que lo activen
  └─ RPO ~0 (pérdida máxima: última transacción)
  └─ Solo recomendado para tenants con volumen alto (>500 ventas/día)
```

El pg_dump se configura automáticamente en el `docker-compose.yml` que se entrega al tenant.
No requiere intervención del usuario.

```yaml
# Incluido en docker-compose.yml de cada tenant
services:
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
```

#### Backup Remoto — Módulo de Pago: "Respaldo en la Nube"

```
Servicio premium: el tenant paga por respaldar en el homelab (Control Plane).

Flujo:
  Sucursal → cifra dump con age (clave pública del TENANT, generada en onboarding)
           → POST /api/v1/backup/upload (multipart, blob cifrado)
           → Control Plane almacena en RAID5 como blob opaco (no puede descifrar)

Retención en homelab:
  - 7 diarios + 4 semanales = 11 snapshots por sucursal
  - ~500MB/sucursal × 11 = ~5.5GB por sucursal
  - Capacidad actual RAID5 24TB = ~4,360 sucursales suscritas (~5,800 tenants)
  - Escalar: agregar discos al RAID o segundo servidor storage

Precio sugerido: $99-199 MXN/mes por sucursal (~$5-10 USD)
  - Margen alto: costo real de storage es ~$0.02 USD/GB/mes en disco local
```

#### Monitoreo de Backups

```
Cada sucursal reporta al Control Plane (todos los tenants, gratis):
  POST /api/v1/fleet/heartbeat  (ya incluye backup status)
  {
    ...
    "last_backup_at": "2026-03-06T14:00:00Z",
    "backup_size_mb": 487,
    "backup_count": 28
  }

Control Plane alerta si:
  - Último backup > 12h (debería ser cada 6h)
  - backup_count = 0 (backup script nunca ejecutó)
  - Para tenants con módulo cloud: último upload > 24h
```

#### Disaster Recovery por Escenario

| Escenario | RPO | RTO | Procedimiento |
|-----------|-----|-----|---------------|
| DB corrupta (bug) | 6h | 1h | Restore del último dump local en `/backups/` |
| Disco muere | 6h | 4h | Nuevo disco + restore último dump local (si en USB externo) |
| Servidor muere | 6h | 4h | Nuevo hardware + restore. Si tiene módulo cloud: download del homelab |
| Incendio/robo | **Depende** | 8h | **Sin módulo cloud:** datos perdidos. **Con módulo cloud:** restore desde homelab |
| Ransomware | 6h | 4h | Wipe + restore local (si no cifró backups) o desde homelab |

> **Nota comercial:** El escenario de incendio/robo es el argumento de venta principal
> del módulo "Respaldo en la Nube". Sin él, el tenant asume el riesgo de pérdida total.
> Con él, RPO = 24h máximo, restore desde homelab.

### 2.4 Capa de Red y Disponibilidad (C3, A4, O5)

**Problema a 10K:** Dependencia total de Cloudflare. Si CF cae, 25,000 sucursales pierden acceso remoto.

#### Cloudflare Enterprise

- Free tier: ~1,000 túneles = ~400 tenants. Enterprise necesario a partir de ~400 tenants
- Negociar SLA 99.99% con Cloudflare (estándar Enterprise)
- Tener contacto directo de soporte CF para incidentes
- Multi-account: segmentar tenants en N cuentas CF (blast radius si una cuenta tiene issues)

#### Fallback sin Cloudflare

```
Escenario: Cloudflare falla globalmente (raro pero posible)

1. Sucursales siguen vendiendo por LAN (offline-first) ← 0 impacto en ventas
2. App 2 (Comando) muestra "Sin conexión remota" con último cache
3. Sync se pausa — se acumula en cola local
4. Cuando CF vuelve → sync catchup automático

Plan B (si CF cae >24h):
  - DNS failover a Tailscale Funnel o WireGuard directo
  - Requiere puerto abierto en router del cliente (no ideal pero funcional)
  - Script automatizado: ./failover-to-wireguard.sh
```

#### Rate Limiting Multi-Capa

```
Capa 1: Cloudflare WAF Rules (antes de llegar al servidor)
  - /api/v1/auth/*     → 10 req/min por IP
  - /api/v1/auth/pair  → 5 req/min por IP
  - /api/v1/*          → 100 req/min por IP
  - Bloqueo automático de IPs con >1000 req en 10 min

Capa 2: FastAPI slowapi + Redis (en el servidor)
  - Defensa en profundidad — si CF falla o se bypasea
  - Rate limit por user_id (no solo IP)
  - Backend de slowapi: Redis (compartido entre todos los workers del Control Plane)
  - 429 Too Many Requests con Retry-After header

Capa 3: Control Plane (horizontal)
  - /admin/* → solo IPs de Tailscale (ACL en nginx)
  - /api/v1/sync/* → rate limit por tenant_id (1 sync/min) — Redis key: `rl:sync:{tenant_id}`
  - /api/v1/health/* → rate limit por branch_id (1 report/5min) — Redis key: `rl:hb:{branch_id}`
  - Todos los rate limits son consistentes entre workers porque el estado está en Redis
```

### 2.5 Capa de Integridad de Datos (A5, O2, O4)

**Problema a 10K:** Un cajero deshonesto en 1 de 50,000 usuarios manipula precios. Una migración mala corrompe el 2% de los tenants.

#### Audit Trail Inmutable

```sql
-- Tabla de auditoría en cada tenant (ya parcialmente existe)
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    user_id     INT NOT NULL,
    action      TEXT NOT NULL,      -- 'sale.create', 'sale.cancel', 'product.update_price'
    entity_type TEXT NOT NULL,      -- 'sale', 'product', 'inventory'
    entity_id   INT,
    old_values  JSONB,              -- snapshot antes del cambio
    new_values  JSONB,              -- snapshot después del cambio
    ip_address  INET,
    device_id   TEXT
);

-- Índice para queries de auditoría
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id, timestamp);

-- Política: NUNCA DELETE/UPDATE en audit_log
-- Particionado mensual OBLIGATORIO (a 1,000 tickets/día ≈ 6,000 filas/día ≈ 2.2M filas/año ≈ 1.1GB/año por sucursal)
-- Retención local: 2 años. Particiones anteriores se archivan en backup y se eliminan.
```

#### Migraciones Seguras a 25K Instancias

```
Problema: ALTER TABLE en 25,000 DBs. Si la migración 045 falla en el tenant 8,321,
          los tenants 1-8,320 ya aplicaron. Rollback parcial.

Solución: Migraciones con Feature Flags + Forward-Only

1. Migración siempre es additive (agregar columna, no renombrar/eliminar)
2. Código soporta ambas versiones (old + new schema) por 1 release cycle
3. Despliegue en waves igual que canary:
   - Wave 1: 10 tenants internos/de prueba
   - Wave 2: 5% de tenants
   - Wave 3: 100% restante
4. Si falla en Wave 1 → fix migration + retry
5. Si falla en Wave 2 → rollback del código (no del schema), fix, retry
6. Columnas obsoletas se eliminan 2 releases después (cleanup migration)

Pipeline:
  Migration → Code Deploy (supports old+new) → Verify → Cleanup Migration
```

#### Resolución de Conflictos de Sync

```
Problema: Sucursal A y Sucursal B modifican el mismo producto offline.
          Cuando sync ejecuta, hay conflicto.

Política: Last-Write-Wins con preservación del conflicto

1. Cada registro tiene updated_at TIMESTAMPTZ
2. Sync compara timestamps — el más reciente gana
3. El registro perdedor se guarda en sync_conflicts:

CREATE TABLE sync_conflicts (
    id          SERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    record_id   INT NOT NULL,
    winner      JSONB NOT NULL,     -- registro que ganó
    loser       JSONB NOT NULL,     -- registro que perdió
    resolved_at TIMESTAMPTZ,
    resolved_by INT,                -- user_id que revisó manualmente (si aplica)
    auto_resolved BOOLEAN DEFAULT TRUE
);

4. Dashboard del dueño muestra conflictos no revisados
5. Para datos financieros (ventas, movimientos de caja): NO hay conflicto
   posible — cada sucursal genera sus propios IDs con prefijo de branch
```

### 2.6 Capa Legal y Cumplimiento (México)

**Problema a 10K:** Manejas datos personales y fiscales de 10,000 empresas. Un breach te expone legalmente.

#### LFPDPPP (Ley Federal de Protección de Datos Personales)

| Obligación | Implementación |
|------------|---------------|
| Aviso de privacidad | Mostrar en primer login del POS + aceptación registrada en audit_log |
| Consentimiento | Checkbox explícito al registrar clientes con nombre/teléfono/email |
| Acceso/Rectificación/Cancelación (ARCO) | Endpoint `DELETE /api/v1/customers/{id}/data` que anonimiza (no elimina — conservar para SAT) |
| Transferencia de datos | Control Plane solo recibe metadata de sync — no datos personales de clientes finales |
| Breach notification | 72h para notificar al INAI. Template de notificación pre-escrito |

#### SAT / Datos Fiscales

- Los CFDI, RFC de clientes, y datos fiscales **nunca salen de la sucursal**
- El Control Plane no tiene acceso a datos fiscales de ningún tenant
- Backups cifrados end-to-end — ni POSVENDELO (la empresa) puede leer los datos fiscales del cliente

#### Contrato de Servicio (SaaS)

```
Términos clave para el contrato con cada tenant:

1. SLA: 99.5% uptime del Control Plane (acceso remoto y dashboard).
   No aplica a operaciones de venta en sucursal, que son 100% locales y offline-first.
   Respaldado por arquitectura horizontal: múltiples API workers + Redis + PG replica (ver Fase 2).
   Si un worker cae, nginx redirige al resto — zero-downtime en operación normal.
2. RPO: máximo 6h de datos perdidos en caso de desastre total
3. RTO: máximo 8h para restaurar servicio completo
4. Propiedad de datos: los datos son 100% del tenant, exportables en cualquier momento
5. Terminación: a la cancelación, se entrega dump SQL + eliminación en 30 días
6. Responsabilidad: limitada al monto anual de la licencia
7. Seguro: póliza de responsabilidad civil profesional (errores y omisiones)
   - Cobertura mínima: $5M MXN
   - Costo estimado: $15,000-30,000 MXN/año
```

---

## 3. Infraestructura de Monitoreo (a 10K tenants es obligatorio)

### Stack de Observabilidad

```
Cada sucursal (ligero):
  └─ Vector.dev (agent) → métricas + logs comprimidos → Control Plane
  └─ Métricas: CPU, RAM, disco, pg connections, backup status, error rate
  └─ Logs: solo errores y warnings (no debug — ancho de banda)
  └─ Bandwidth estimado: ~1KB/heartbeat × 25K sucursales / 5min ≈ 83 req/seg, ~5MB/seg ingestion
  └─ VictoriaMetrics: ~16K puntos/seg (manejable con 1-2GB RAM)

Control Plane (horizontal):
  └─ Victoria Metrics (time-series DB, compatible Prometheus, 10x menos RAM)
  └─ Redis Exporter → métricas de Redis (memory, connections, keys)
  └─ nginx Exporter → métricas del LB (requests/sec, latencia, 5xx)
  └─ Grafana dashboards:
      ├─ Fleet Overview: 25,000 sucursales en mapa de calor
      ├─ Control Plane Health: workers activos, Redis memory, PG connections
      ├─ Alertas activas por tenant
      ├─ Backup compliance (% de tenants con backup <6h)
      ├─ Update rollout progress (canary → stable)
      └─ Sync lag por tenant

Alerting:
  └─ Grafana → Alertmanager → Telegram bot para el equipo ops
  └─ Severidades:
      - P1 (Telegram + llamada): Control Plane down, >100 tenants sin backup >24h
      - P2 (Telegram): tenant individual sin backup >12h, error rate >5%
      - P3 (daily digest): sync lag >1h, disco >80%
```

### Health Check Automático

```
Cada sucursal ejecuta cada 5 minutos (± 30 seg de jitter aleatorio para evitar thundering herd):

POST {control_plane}/api/v1/fleet/heartbeat
{
  "tenant_id": "lupita",
  "branch_id": 1,
  "version": "2.4.1",
  "uptime_seconds": 86400,
  "db_connections": 8,
  "disk_free_gb": 120,
  "last_sale_at": "2026-03-06T14:32:00Z",
  "last_backup_at": "2026-03-06T12:00:00Z",
  "pending_sync_rows": 42,
  "error_count_1h": 0
}

Control Plane marca como "offline" si no recibe heartbeat en 15 min.
Dashboard muestra: 24,892/25,000 online (99.6%)
```

---

## 4. Plan de Respuesta a Incidentes

### Clasificación

| Nivel | Criterio | Tiempo de respuesta | Ejemplo |
|-------|----------|--------------------| --------|
| **SEV-1** | >1% de tenants afectados o datos comprometidos | 15 min | Update corrupto, Control Plane hackeado |
| **SEV-2** | 1 tenant completo afectado | 1 hora | DB corrupta, servidor muerto |
| **SEV-3** | Feature parcialmente degradada | 4 horas | Sync retrasado, backup fallido |
| **SEV-4** | Cosmético o edge case | Next business day | UI glitch, label incorrecto |

### Runbooks Pre-escritos

| Incidente | Runbook |
|-----------|---------|
| Rollback de update | `./ops/rollback-canary.sh` → revierte tag en GHCR, notifica Watchtower |
| Restore de tenant | `./ops/restore-tenant.sh {tenant_id} {backup_date}` → download desde homelab RAID5 + restore |
| Revocar tunnel | `./ops/revoke-tunnel.sh {tenant_id}` → CF API delete + notifica tenant |
| Rotar JWT_SECRET | `./ops/rotate-jwt.sh {tenant_id}` → genera nuevo secret, dual-accept 24h |
| Tenant comprometido | `./ops/isolate-tenant.sh {tenant_id}` → revoca tunnel + bloquea sync |
| Offboarding tenant | `./ops/offboard-tenant.sh {tenant_id}` → notifica, espera 30d, elimina backups RAID5, revoca tunnel CF, archiva metadata |
| Exportar datos tenant | `GET /api/v1/export/tenant-data` → trigger pg_dump descargable + CSV de ventas/inventario |

### Simulacros (Chaos Engineering Lite)

```
Mensualmente:
  1. "Game day": simular restauración de backup aleatorio (verificar que funciona)
  2. Cortar Cloudflare en tenant de prueba (verificar que LAN sigue funcionando)
  3. Push versión intencionalmente rota a canary (verificar que rollback automático funciona)
  4. Matar un worker API del Control Plane (verificar que nginx redirige tráfico a los demás)

Trimestralmente:
  5. Simular pérdida total de VPS-1 (verificar failover a VPS-2 réplica)
  6. Simular pérdida de Redis (verificar que workers re-conectan y rate limits se restauran)
  7. Pen-test externo en Control Plane
```

---

## 5. Costos Estimados de Mitigación a 10K Tenants

### Costos fijos (los paga POSVENDELO)

| Concepto | Costo mensual estimado |
|----------|----------------------|
| Cloudflare Enterprise (25K túneles) | ~$5,000 USD/mes (negociable) |
| VPS-1 Control Plane (API workers + nginx + Redis) | ~$150 USD/mes |
| VPS-2 Control Plane réplica (HA) | ~$150 USD/mes |
| DB dedicada PostgreSQL (primary + read replica) | ~$100 USD/mes |
| Victoria Metrics + Grafana (self-hosted en VPS) | $0 (incluido en VPS) |
| Key management (AWS KMS ~$3 o HashiCorp Vault self-hosted $0) | ~$3 USD/mes |
| Seguro responsabilidad civil | ~$125 USD/mes ($30K MXN/año) |
| Pen-test trimestral (externo) | ~$500 USD/mes (prorrateado) |
| **Total operativo fijo** | **~$6,028 USD/mes** |
| **Costo fijo por tenant** | **~$0.60 USD/mes** |

### Costos de storage (solo si se vende el módulo cloud backup)

Con 500-2,000 tickets/día por sucursal, cada DB crece ~2-5GB/mes en raw.
Usando `pg_dump -Fc` (formato custom con compresión zlib integrada), la reducción es ~85%:

| Tickets/día | DB raw/mes | Dump comprimido (-Fc) | × 11 snapshots (retención) |
|-------------|-----------|----------------------|---------------------------|
| 500 | ~2GB | ~300MB | ~3.3GB por sucursal |
| 1,000 | ~3.5GB | ~500MB | ~5.5GB por sucursal |
| 2,000 | ~5GB | ~750MB | ~8.2GB por sucursal |

Promedio estimado: **~5.5GB por sucursal suscrita** con retención completa (11 snapshots).

| Tenants totales | Sucursales totales | Suscritas al módulo (30%) | Storage necesario | Infra |
|-----------------|-------------------|--------------------------|------------------|-------|
| 100 | ~250 | ~75 | ~412GB | Homelab actual (RAID5 24TB) — sobra |
| 500 | ~1,250 | ~375 | ~2TB | Homelab actual — sobra |
| 1,000 | ~2,500 | ~750 | ~4.1TB | Homelab actual — sobra |
| 3,000 | ~7,500 | ~2,250 | ~12.4TB | Homelab actual — cabe |
| 5,000 | ~12,500 | ~3,750 | ~20.6TB | Homelab al 86% (24TB) |
| **5,800** | **~14,500** | **~4,360** | **~24TB** | **Límite del RAID5 actual** |
| 10,000 | ~25,000 | ~7,500 | ~41TB | NAS adicional (~$2,000 USD con 4×20TB) |

**Fórmula:** tenants × 2.5 sucursales/tenant × 30% adopción × 5.5GB/sucursal = storage total.

**El RAID5 de 24TB alcanza hasta ~4,360 sucursales suscritas** (~5,800 tenants a 30% adopción) sin inversión adicional.
Esto cubre holgadamente las Fases 1-3.

**Ingreso del módulo cloud backup:** si 30% de las 25,000 sucursales contratan a $149 MXN/mes:
- 7,500 sucursales suscritas × $149 = **$1,117,500 MXN/mes** (~$55,875 USD)
- Costo del storage hasta 4,000 suscriptores: $0 (hardware ya amortizado)
- Costo a 10,000 suscriptores: NAS $2,000 USD único + ~$50 USD/mes electricidad
- **Margen: >99%**

> **Nota:** `pg_dump -Fc` es preferible a `.sql.gz` o `.tar.gz` porque:
> 1. Comprime igual o mejor (zlib nativo)
> 2. Soporta restore selectivo (`pg_restore -t tabla`)
> 3. Es más rápido que SQL plano + gzip externo
> 4. Es el formato recomendado por PostgreSQL para backups programáticos

### Resumen económico

| Concepto | Mensual |
|----------|---------|
| Costo operativo fijo | ~$6,028 USD |
| Ingreso licencias (10K × $35 USD avg) | ~$350,000 USD |
| Ingreso módulo cloud (estimado) | ~$55,875 USD |
| **Margen bruto** | **>98%** |

El costo de mitigación de riesgos es **<1.5%** del ingreso total.

---

## 6. Hoja de Ruta de Implementación (Mitigaciones)

### Fase 1: Antes del primer tenant externo (Hito 0)

- [x] ~~Eliminar CORS `null` del whitelist~~ (ya implementado en `main.py`)
- [ ] Rate limiting en `/auth/pair` y `/auth/login` (slowapi)
- [ ] Docker secrets para CF_TUNNEL_TOKEN
- [ ] pg_dump automático cada 6h incluido en docker-compose.yml del tenant
- [ ] Audit log básico (sale.create, sale.cancel, product.update_price)
- [ ] Heartbeat endpoint en el POS (`POST /api/v1/fleet/heartbeat`)
- [ ] Endpoint `GET /api/v1/export/tenant-data` (clausula contractual de exportación)
- [ ] Endpoint `POST /auth/emergency-reset` (recovery de PIN/contraseña)
- [ ] Endpoints `GET/DELETE /auth/devices` (desvinculación de dispositivos)
- [ ] Contrato SaaS + aviso de privacidad

### Fase 2: 1-100 tenants (Hito 1-2)

- [ ] Control Plane horizontal: nginx LB + 2 workers FastAPI + Redis + PostgreSQL — prerequisito para SLA
- [ ] HA: réplica del stack en segundo VPS (PostgreSQL streaming replication + Redis Sentinel)
- [ ] Token revocation migrado a Redis (eliminar dict en memoria)
- [ ] Rate limiting con backend Redis (slowapi + redis)
- [ ] Canary deployment pipeline en GitHub Actions
- [ ] Cosign para firmar imágenes Docker
- [ ] GPG para firmar instaladores
- [ ] Grafana + Victoria Metrics en Control Plane (self-hosted)
- [ ] Alertas P1/P2 via Telegram
- [ ] Módulo cloud backup: endpoint de upload + almacenamiento en RAID5

### Fase 3: 100-1,000 tenants (Hito 3)

- [ ] Cloudflare Enterprise (contratar antes de ~400 tenants / 1,000 túneles)
- [ ] Migrar RSA key a AWS KMS o HashiCorp Vault
- [ ] Sync conflict resolution + dashboard
- [ ] Runbooks automatizados (restore, rollback, isolate)
- [ ] Primer pen-test externo
- [ ] Seguro de responsabilidad civil

### Fase 4: 1,000-10,000 tenants (Hito 4+)

- [ ] Scale-out Control Plane: 6-10 API workers distribuidos en 2+ VPS
- [ ] PostgreSQL read replicas (2+) para dashboards y reportes
- [ ] Redis Sentinel (3 nodos) para HA de sessions/rate limits
- [ ] Chaos engineering mensual (game days)
- [ ] Segmentar cuentas CF (blast radius)
- [ ] Segundo servidor storage para cloud backups (>4,000 sucursales)
- [ ] Cumplimiento LFPDPPP formal (auditoría externa)

---

*Fin del documento — complementa ARQUITECTURA_MOVIL_REDES.md*
