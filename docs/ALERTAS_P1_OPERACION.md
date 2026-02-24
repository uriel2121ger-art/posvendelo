# Alertas P1 Operación Sucursal

## Eventos P1
- API gateway no responde (`/health` fallando)
- Falla de facturación repetida (>= 3 errores en 5 minutos)
- Backlog de sync creciendo sin drenar
- Error de conexión DB en servidor

## Respuesta operativa
1. Confirmar impacto en cajas activas.
2. Congelar despliegues en curso.
3. Aplicar rollback si hay degradación post-release.
4. Abrir incidente y registrar evidencia.

## Evidencia mínima
- timestamp inicio/fin
- sucursales afectadas
- terminal_id afectados
- causa preliminar y acción aplicada

