# Checklist de Salida a Mercado GA

## Producto

- POS desktop instala y abre sin pasos manuales raros.
- Venta, cancelacion, turno, corte e impresion validados.
- Multiterminal LAN probado con al menos 2 terminales.
- Backup y restore probados en equipo limpio.

## Distribucion

- Artefactos Linux y Windows publicados.
- Checksums generados y verificados.
- Update y rollback de app validados.
- Update y rollback del servidor local validados.

## Plataforma Remota

- Control-plane accesible y estable.
- Heartbeats entrando por sucursal.
- Dashboard resumen, tenant summary y branch health responden.
- Trazabilidad de licencias disponible.

## Comercial

- Trial de 40 dias activo.
- Licencias mensual y perpetua emitibles.
- Renovacion operativa por script o endpoint.
- Checklist de onboarding para nueva sucursal documentado.

## Seguridad

- JWT secret persistente.
- Clave privada de licencias persistente.
- Tokens de pairing expiran y son de un solo uso.
- Revocacion de dispositivo disponible.

## Soporte

- Runbook de flota publicado.
- Flujo de incidente L1/L2/L3 definido.
- Evidencia minima para soporte definida:
  - version
  - branch
  - ultimos heartbeats
  - ultimo backup
  - error dominante

## Go-To-Market

- Material comercial listo.
- Documentacion por perfil lista.
- Hardware soportado listado.
- Piloto controlado cerrado con checklist firmado.
