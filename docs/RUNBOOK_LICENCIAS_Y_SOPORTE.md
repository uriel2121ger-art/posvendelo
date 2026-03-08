# Runbook De Licencias Y Soporte

## Objetivo

Operar trial, renovación, activación offline y reinstalación sin tocar SQL ni improvisar soporte.

## Requisitos

- `control-plane` disponible.
- `CP_LICENSE_PRIVATE_KEY` configurada en producción.
- `CP_ADMIN_TOKEN` resguardado por soporte/operación.
- `scripts/license_admin.py` disponible en `control-plane/`.

## Casos Operativos

### 1. Emitir licencia mensual

```bash
cd control-plane
python3 scripts/license_admin.py \
  --base-url http://localhost:9090 \
  issue \
  --admin-token "$CP_ADMIN_TOKEN" \
  --tenant-id 1 \
  --license-type monthly \
  --valid-until 2026-04-01T00:00:00 \
  --grace-days 5 \
  --notes "Renovacion abril"
```

### 2. Emitir licencia vitalicia

```bash
cd control-plane
python3 scripts/license_admin.py \
  --base-url http://localhost:9090 \
  issue \
  --admin-token "$CP_ADMIN_TOKEN" \
  --tenant-id 1 \
  --license-type perpetual \
  --support-until 2027-03-31T00:00:00 \
  --notes "Vitalicia con soporte anual"
```

### 3. Exportar activador offline

Pide al cliente:

- `install_token`
- `machine_id`

Luego exporta:

```bash
cd control-plane
python3 scripts/license_admin.py \
  --base-url http://localhost:9090 \
  export-file \
  --install-token TOKEN \
  --machine-id EQUIPO-001 \
  --output titan-license.json
```

Entrega `titan-license.json` al cliente para colocarlo junto a `titan-agent.json`.

## Ubicaciones Del Archivo Offline

- Linux típico: mismo directorio del `titan-agent.json`
- Backend cliente Docker: `/runtime/titan-license.json`
- Wrapper local: archivo hermano del `titan-agent.json`

## Reinstalación En El Mismo Equipo

1. Conservar `install_token`.
2. Reinstalar el nodo.
3. Verificar que el `machine_id` no cambió materialmente.
4. Si el nodo no recupera la licencia por red, volver a exportar `titan-license.json`.

## Cambio Menor De Hardware

Regla recomendada:

- permitir que la licencia sobreviva a cambios menores;
- si cambia el identificador base del equipo, reemitir activador offline;
- no reciclar licencias de otro tenant o sucursal.

## Mensual Vencida

Comportamiento esperado:

- backend entra en restricción comercial;
- login/navbar/settings siguen visibles;
- soporte debe emitir renovación o archivo offline nuevo.

## Vitalicia Con Soporte Vencido

Comportamiento esperado:

- el sistema sigue operando;
- no debe bloquear ventas;
- se suspenden updates y soporte hasta renovar mantenimiento.

## Checklist De Soporte

- Confirmar `tenant_id`, `branch_id`, `install_token` y `machine_id`.
- Verificar estado en `Login` o `Ajustes`.
- Confirmar si el backend local responde en `/health`.
- Confirmar si la licencia está en `titan-agent.json` o `titan-license.json`.
- Si la firma no valida, reemitir desde control-plane.
- Si la mensual venció, renovar y exportar nuevamente.

## Riesgos A Evitar

- No compartir `CP_ADMIN_TOKEN` con clientes.
- No usar clave efímera de desarrollo para producción.
- No ligar la licencia a fingerprints demasiado frágiles.
- No borrar `titan-agent.json` sin respaldo durante soporte.
