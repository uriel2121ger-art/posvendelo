# Plan de hardening de dependencias (Electron POS)

## Objetivo

Reducir vulnerabilidades de la toolchain sin romper compilacion, empaquetado ni flujo de trabajo.

## Estado base

- Runtime production deps: 0 vulnerabilidades (`npm audit --omit=dev`)
- Full tree: 26 high (raiz: `minimatch` transitive)
- `npm audit fix` sin `--force`: no reduce hallazgos

## Estado actual (ultima verificacion)

- Runtime production deps: 0 vulnerabilidades (`npm audit --omit=dev`)
- Full tree: 0
- Calidad tecnica: `lint`, `typecheck`, `build` en verde
- `electron-builder` actualizado a `26.8.1`
- `overrides` aplicados: `minimatch ^10.2.2`, `tar ^7.5.8`
- Hardening de seguridad Electron aplicado en `src/main/index.ts`

## Decision vigente

- Se mantiene **ESLint v9** como linea estable.
- Motivo: `eslint-plugin-react` actual declara peer compatibility hasta ESLint 9.x y no soporta ESLint 10 en este momento.
- Implicacion: no se fuerza upgrade a ESLint 10 hasta que el ecosistema de plugins lo soporte de forma oficial.

## Fases propuestas

## Fase A - Preparacion (bajo riesgo)

1. Congelar baseline:
   - `npm run typecheck`
   - `npm run build`
2. Ejecutar smoke desktop:
   - abrir app
   - validar arranque renderer/main/preload
3. Definir criterio de aceptacion:
   - build verde
   - empaquetado verde
   - rutas basicas funcionales

## Fase B - Upgrade controlado de lint stack

1. Actualizar en branch aislada:
   - `eslint` (major)
   - `eslint-plugin-react` (version compatible con el nuevo eslint)
2. Ajustar reglas/config necesarias.
3. Revalidar build completo.

## Fase C - Upgrade controlado de packaging stack

1. Actualizar `electron-builder` y dependencias asociadas.
2. Revalidar:
   - build linux
   - build windows (si aplica pipeline cruzado)
3. Ejecutar prueba de instalador.

## Fase D - Cierre

1. Re-ejecutar:
   - `npm audit --json`
   - `npm audit --omit=dev --json`
2. Documentar diferencias en `CHANGELOG.md`.
3. Dejar evidencia de no regresion funcional.

## Riesgos y mitigaciones

- Riesgo: incompatibilidades por upgrades mayores.
  - Mitigacion: branch dedicada + validacion por fases.
- Riesgo: cambios en reglas de ESLint que rompan CI.
  - Mitigacion: ajustar config incrementalmente.
- Riesgo: cambios en empaquetado Electron.
  - Mitigacion: smoke tests de instalador por plataforma objetivo.
