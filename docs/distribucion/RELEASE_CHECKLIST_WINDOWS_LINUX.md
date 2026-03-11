# Checklist De Release Windows/Linux

## Objetivo

Checklist operativo para publicar POSVENDELO con apariencia profesional y menor riesgo de regresiones en distribución.

## Pre-release técnico

1. Ejecutar `cd frontend && npm run verify:go-live`.
1. Ejecutar `cd frontend && npm run test:e2e:prod` con `E2E_BASE_URL`, `E2E_API_URL`, `E2E_USER` y `E2E_PASS`.
1. Ejecutar `cd backend && python3 -m pytest tests/ -q` al menos en una base de staging.
1. Verificar `docker compose -f docker-compose.prod.yml config` en el host de despliegue.
1. Confirmar que el `control-plane` responde `bootstrap-config`, `compose-template` y `releases/manifest`.

## Branding y assets

1. Confirmar que existe `frontend/resources/icon.png`.
1. Generar y agregar `frontend/build/icon.ico` para Windows.
1. Generar y agregar `frontend/build/icon.icns` para macOS si se va a distribuir ahí.
1. Verificar que el nombre comercial sea `POSVENDELO` y el ejecutable `titan-pos`.

## Empaquetado

1. Generar `cd frontend && npm run build:linux`.
1. Generar `cd frontend && npm run build:win` desde un runner o equipo Windows.
1. Verificar que los artefactos abran sin depender del entorno de desarrollo.
1. Revisar tamaño de artefactos y hashes antes de publicar.

## Instalación plug-and-play

1. Probar `setup.sh` o `installers/linux/install-titan.sh` en una máquina Linux limpia.
1. Probar `installers/windows/Install-Titan.ps1` en una máquina Windows limpia.
1. Confirmar creación de `titan-agent.json` y conectividad al backend local.
1. Confirmar health local en la URL reportada por `INSTALL_SUMMARY.txt` o `titan-agent.json`.
1. Validar login, apertura de turno, venta, impresión y reinicio del equipo.

## Seguridad y confianza

1. Configurar secretos reales en `.env` y nunca usar placeholders en producción.
1. Configurar firma de binarios para Windows con secretos `WIN_CSC_LINK` y `WIN_CSC_KEY_PASSWORD` en GitHub Actions.
1. Si usarás autofirma propia, documentar y distribuir también el `.cer` de confianza. Ver `docs/referencia/AUTOFIRMA_WINDOWS_CONTROLADA.md`.
1. Si más adelante distribuyes macOS, agregar notarización/firma específica antes de publicar.
1. Configurar `CP_BOOTSTRAP_PUBLIC_KEY` en el control-plane para pinning de bootstrap.
1. Verificar que `npm audit` y los checks de release estén limpios antes de publicar.

## Publicación

1. Subir artefactos a tu canal de distribución o bucket de releases.
1. Publicar metadata en el `control-plane` para `electron-linux`, `electron-windows` y `backend`.
1. Publicar `SHA256SUMS.txt` junto con los artefactos desktop.
1. Validar manifest por sucursal/canal con `releases/manifest`.
1. Hacer smoke final en una sucursal piloto antes de abrir venta general.
