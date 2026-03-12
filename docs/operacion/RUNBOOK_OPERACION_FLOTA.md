# Runbook de Operacion de Flota

## Objetivo

Operar sucursales POSVENDELO con un flujo repetible para soporte, releases, licencias y recuperacion.

## Monitoreo Diario

1. Revisar `control-plane /dashboard/summary`.
2. Revisar `control-plane /dashboard/tenant-summary`.
3. Revisar `control-plane /dashboard/branch-health`.
4. Confirmar:
   - sucursales offline
   - errores de instalacion
   - errores de tunel
   - backups faltantes
   - disco alto

## Renovacion de Licencias

Listar licencias:

```bash
python3 control-plane/scripts/license_admin.py \
  --base-url http://localhost:9090 \
  list \
  --admin-token TU_TOKEN
```

Renovar una licencia por dias:

```bash
python3 control-plane/scripts/license_admin.py \
  --base-url http://localhost:9090 \
  renew \
  --admin-token TU_TOKEN \
  --license-id 123 \
  --additional-days 30 \
  --notes "Renovacion mensual"
```

Ver historial:

```bash
python3 control-plane/scripts/license_admin.py \
  --base-url http://localhost:9090 \
  events \
  --admin-token TU_TOKEN \
  --license-id 123
```

## Actualizacion de Nodo

Antes:

- confirmar backup reciente
- confirmar sucursal online
- confirmar canal correcto

Durante:

- desde login del nodo, aplicar actualizacion de app o servidor local
- validar `/health`
- validar venta de prueba

Despues:

- revisar heartbeat
- revisar version reportada
- revisar rollback disponible

## Incidentes Comunes

### Sucursal offline

1. Revisar `last_seen`.
2. Validar conectividad local del equipo.
3. Validar servicio Docker y contenedores.
4. Validar tunel si aplica.
5. Si no recupera, usar restore en equipo nuevo.

### Licencia rechazada

1. Resolver licencia otra vez con install token.
2. Verificar clave publica/privada persistente.
3. Exportar `posvendelo-license.json` si el nodo opera offline.
4. Revisar eventos de licencia.

### Update fallido

1. Revisar checksum y artifact publicado.
2. Ejecutar rollback.
3. Mantener el nodo en canal estable.
4. Abrir incidente si el fallo es reproducible.

## Criterios de Escalacion

- Nivel 1: login, impresora, caja, configuracion, licencia simple.
- Nivel 2: update fallido, backup ausente, tunel, pairing, recovery de nodo.
- Nivel 3: corrupcion de datos, restore, bug de release, problema fiscal o falla multi-sucursal.
