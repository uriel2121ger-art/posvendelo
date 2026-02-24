# Go/No-Go Produccion - Electron POS

Fecha base: 2026-02-22

## Objetivo

Definir una salida a produccion repetible para `frontend/electron_pos` con criterios claros de bloqueo y aprobacion.

## Gate tecnico obligatorio

Ejecutar:

```bash
npm run verify:release
```

Para validacion completa de salida (incluye placeholders de release config):

```bash
npm run verify:go-live
```

Debe quedar en verde:

- `lint`
- `typecheck`
- `build`
- `audit:full`
- `audit:prod`
- `check:release-config`

## Bloqueos actuales para produccion real (no tecnicos de compilacion)

Estos puntos no se deben inferir automaticamente y requieren decision del equipo:

1. `electron-builder.yml` tiene valores placeholder:
   - `appId: com.electron.app`
   - `maintainer: electronjs.org`
   - `publish.url: https://example.com/auto-updates`
2. Falta definir estrategia de firma de binarios por plataforma.
3. Falta definir canal de actualizaciones (beta/piloto/prod) y endpoint real.
4. Falta plan de rollout por sucursal y rollback operativo.

## Criterio Go

Solo ir a produccion cuando:

- `npm run verify:release` pase completamente.
- `appId`, `maintainer`, `publish.url` esten definidos con valores reales.
- Exista estrategia de firma y distribucion aprobada.
- Se complete smoke test del instalador en plataforma objetivo.

## Criterio No-Go

No liberar si ocurre cualquiera:

- Falla `verify:release`.
- Se mantienen placeholders en config de build/publicacion.
- No hay evidencia de smoke test post-instalacion.

## Evidencia minima a guardar por release

- Salida de `npm run verify:release`.
- Hash/checksum de artefactos generados.
- Capturas o bitacora de smoke test por plataforma.
- Decision Go/No-Go firmada por responsable tecnico.
