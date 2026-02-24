# Cuarta etapa — Seguridad y compliance (sin tocar código)

Evaluación documental y estática de exposición de secretos, manejo de credenciales y postura básica de cumplimiento.

## Alcance

- Archivos revisados para patrones sensibles: **951**
- Hallazgos totales: **14**
- Anexo detallado: `ANEXO_CAPA_4_HALLAZGOS_SEGURIDAD.csv`

## Resumen por severidad

- CRITICA: 0
- ALTA: 6
- MEDIA: 2
- BAJA: 6

## Resumen por tipo de hallazgo

- `pgpassword_export`: 6
- `db_password_literal`: 4
- `hardcoded_admin_token`: 2
- `generic_api_key`: 2

## Hallazgos relevantes

- [ALTA] `backend/scripts/backup_postgresql.sh:42` | db_password_literal | `export PGPASSWORD="$PASSWORD"`
- [ALTA] `backend/scripts/restore_postgresql.sh:52` | db_password_literal | `export PGPASSWORD="$PASSWORD"`
- [ALTA] `backend/server/instalar_sucursal.sh:31` | hardcoded_admin_token | `ADMIN_TOKEN="sOha_F4JGLhkCB7ERzgqrmLAQmJsX4NMISXyNHrjV6Y"`
- [MEDIA] `backend/server/instalar_sucursal.sh:31` | generic_api_key | `ADMIN_TOKEN="sOha_F4JGLhkCB7ERzgqrmLAQmJsX4NMISXyNHrjV6Y"`
- [ALTA] `frontend/scripts/backup_postgresql.sh:42` | db_password_literal | `export PGPASSWORD="$PASSWORD"`
- [ALTA] `frontend/scripts/restore_postgresql.sh:52` | db_password_literal | `export PGPASSWORD="$PASSWORD"`
- [ALTA] `frontend/server/instalar_sucursal.sh:31` | hardcoded_admin_token | `ADMIN_TOKEN="sOha_F4JGLhkCB7ERzgqrmLAQmJsX4NMISXyNHrjV6Y"`
- [MEDIA] `frontend/server/instalar_sucursal.sh:31` | generic_api_key | `ADMIN_TOKEN="sOha_F4JGLhkCB7ERzgqrmLAQmJsX4NMISXyNHrjV6Y"`

## Evaluación de postura de compliance (heurística)

- `backup scripts` detectados: **sí**
- `restore scripts` detectados: **sí**
- `.env.example` detectado: **no**
- documentos explícitos de policy/compliance: **sí**

## Recomendaciones (sin cambios de código aún)

1. Validar manualmente cada hallazgo del anexo y clasificarlo en: secreto real / falso positivo / aceptado temporal.
2. Definir matriz de secretos por entorno (sucursal, server central, cajas): dueño, rotación, vencimiento y ubicación segura.
3. Establecer política de no hardcode de tokens y credenciales en scripts.
4. Definir estándar de respaldo/restauración con evidencia de prueba periódica.
5. Preparar checklist de auditoría mínima (accesos, facturación, sync, logs, backups).

## Dictamen etapa 4

- Se confirma exposición potencial de credenciales/tokens en scripts operativos.
- Antes de refactor técnico, conviene cerrar brechas de higiene de secretos y formalizar compliance operativo.
