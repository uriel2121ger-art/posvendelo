# TITAN POS — Deploy & Auto-Update

## Arquitectura

```
┌─────────────┐     push master     ┌──────────────────┐
│  Developer   │ ──────────────────→ │  GitHub Actions   │
└─────────────┘                      │  lint → test →    │
                                     │  build & push     │
                                     └────────┬─────────┘
                                              │ docker push
                                              ▼
                                     ┌──────────────────┐
                                     │  GHCR (ghcr.io)  │
                                     │  :latest + :sha  │
                                     └────────┬─────────┘
                                              │ poll cada 30min
                                              ▼
┌─────────────────────────────────────────────────────────┐
│  Sucursal (docker-compose.prod.yml)                     │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────────┐│
│  │ PostgreSQL │  │ Watchtower │→│ API container         ││
│  │ (no auto- │  │ (pull new  │ │ entrypoint.sh:        ││
│  │  update)  │  │  images)   │ │  1. wait postgres     ││
│  └───────────┘  └───────────┘ │  2. schema bootstrap  ││
│                                │  3. migrate.py        ││
│                                │  4. uvicorn           ││
│                                └──────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

## Setup primera vez (producción)

### 1. Prerrequisitos
- Docker + Docker Compose instalados
- Acceso a internet para pull de imágenes

### 2. Autenticación con GHCR
```bash
# Generar Personal Access Token en GitHub con scope: read:packages
docker login ghcr.io -u <tu-usuario-github>
# Pega el token como password
```

### 3. Configurar variables de entorno
```bash
cd /ruta/titan-pos
cp .env.example .env
# Editar .env con valores de producción:
#   POSTGRES_PASSWORD=<password-seguro>
#   JWT_SECRET=<secret-seguro>
#   ADMIN_API_PASSWORD=<password-admin>
```

### 4. Iniciar servicios
```bash
docker compose -f docker-compose.prod.yml up -d
```

El API container automáticamente:
1. Espera a que PostgreSQL esté listo
2. Si la DB está vacía, aplica el schema base
3. Ejecuta todas las migraciones pendientes
4. Inicia uvicorn

### 5. Verificar
```bash
# Logs del API
docker compose -f docker-compose.prod.yml logs api

# Debe mostrar:
# [ENTRYPOINT] PostgreSQL is ready
# [MIGRATE] Database up to date
# [ENTRYPOINT] Starting uvicorn...

# Health check
curl http://localhost:8000/health
```

## Migraciones automáticas

### Cómo funcionan
- `entrypoint.sh` ejecuta `db/migrate.py` cada vez que el contenedor arranca
- `migrate.py` lee `backend/migrations/*.sql` y aplica las que falten
- Cada migración se registra en la tabla `schema_version`
- Las migraciones son **idempotentes** (IF NOT EXISTS, ON CONFLICT DO NOTHING)

### Cada sucursal es independiente
Cada sucursal tiene su propia base de datos con su propia tabla `schema_version`. Las migraciones viajan **dentro de la imagen Docker** (archivos `.sql` empaquetados en el contenedor). Cuando el contenedor arranca, `migrate.py` resuelve localmente qué migraciones faltan.

```
Sucursal A (v1-v28) + imagen con v29 → aplica solo v29
Sucursal B (v1-v20) + imagen con v29 → aplica v21-v29
Sucursal C (offline 1 semana)       → al prender, aplica todas las pendientes
```

No hay servidor central de migraciones. No se requiere conectividad entre sucursales.

### Agregar una nueva migración
1. Crear archivo `backend/migrations/NNN_descripcion.sql`
   - `NNN` = siguiente número disponible (ej: `029`)
   - Usar IF NOT EXISTS / ON CONFLICT DO NOTHING / ADD COLUMN IF NOT EXISTS
2. Terminar con:
   ```sql
   INSERT INTO schema_version (version, description, applied_at)
   VALUES (29, 'descripcion_corta', NOW())
   ON CONFLICT (version) DO NOTHING;
   ```
3. Commit + push a master
4. GitHub Actions testea la migración contra DB fresca (schema.sql + todas las migraciones)
5. Watchtower la despliega automáticamente en cada sucursal

### Migraciones con transacciones explícitas
Si tu migración usa `BEGIN;`...`COMMIT;`, `migrate.py` lo detecta y no envuelve en transacción adicional. Si no tiene `BEGIN;`, se envuelve automáticamente.

## Watchtower

### Cómo funciona
- Watchtower revisa GHCR cada 30 minutos buscando nuevas imágenes
- Solo actualiza contenedores con label `com.centurylinklabs.watchtower.enable=true`
- PostgreSQL **nunca** se auto-actualiza (no tiene el label)
- Usa rolling restart para minimizar downtime
- Limpia imágenes viejas automáticamente

### Verificar que Watchtower funciona
```bash
docker compose -f docker-compose.prod.yml logs watchtower
```

### Forzar check inmediato
```bash
docker compose -f docker-compose.prod.yml exec watchtower \
  /watchtower --run-once
```

## Rollback

### Opción 1: Pin a un SHA específico
```bash
# Buscar SHA del commit bueno en GitHub o con:
docker images ghcr.io/uriel2121ger-art/titan-pos --format "{{.Tag}}"

# Editar docker-compose.prod.yml:
# image: ghcr.io/uriel2121ger-art/titan-pos:sha-abc1234

# Recrear:
docker compose -f docker-compose.prod.yml up -d api
```

### Opción 2: Revertir en Git
```bash
git revert <commit-malo>
git push origin master
# GitHub Actions construye imagen nueva → Watchtower la despliega
```

### Nota sobre migraciones
Las migraciones SQL son **solo hacia adelante** (no hay rollback automático). Si una migración necesita revertirse, crear una nueva migración que deshaga los cambios.

## Troubleshooting

### El API no arranca
```bash
docker compose -f docker-compose.prod.yml logs api
```
- `PostgreSQL not available after 30 attempts` → PostgreSQL no está corriendo o las credenciales son incorrectas
- `[MIGRATE] PostgreSQL error:` → Error en una migración. Revisar el SQL del archivo indicado

### Watchtower no actualiza
```bash
docker compose -f docker-compose.prod.yml logs watchtower
```
- `unauthorized` → Re-ejecutar `docker login ghcr.io`
- Verificar que `~/.docker/config.json` existe y tiene credenciales GHCR

### La imagen no se publica en GHCR
- Verificar que GitHub Actions pasó: `https://github.com/uriel2121ger-art/titan-pos/actions`
- El repo debe tener packages habilitado (Settings → Packages)

### Base de datos corrupta / quiero empezar de cero
```bash
docker compose -f docker-compose.prod.yml down
docker volume rm <nombre-proyecto>_pgdata
docker compose -f docker-compose.prod.yml up -d
# El entrypoint detecta DB vacía y aplica schema + migraciones
```
