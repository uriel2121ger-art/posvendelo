# Rollout De Updates Y Rollback

## Objetivo

Definir como publicar fixes de `backend` y `desktop`, como desplegarlos por canal/sucursal y como responder si una version falla.

## Tipos de update

- `backend`: imagen Docker publicada en GHCR. Se distribuye por `target_ref` tipo `ghcr.io/...:VERSION`.
- `desktop`: artefacto descargable por plataforma (`electron-linux`, `electron-windows`).
- `licencia/config`: refresh desde `control-plane`; no requiere reinstalar.

## Contrato actual

- El `control-plane` expone `releases/manifest` por sucursal.
- Cada release incluye:
  - `version`
  - `target_ref`
  - `checksums_manifest_url` para desktop si viene de assets HTTP/HTTPS
  - `rollback_supported`
  - `rollout_strategy`
- El agente local:
  - detecta updates,
  - descarga el desktop update,
  - verifica SHA256 si existe `SHA256SUMS.txt`,
  - deja el update en estado `staged`,
  - permite aplicar o descartar,
  - en Linux AppImage crea backup local y habilita rollback automático.

## Flujo recomendado de rollout

1. Publicar artefactos y metadata de release.
1. Asignar primero un canal piloto o una sucursal piloto.
1. Esperar confirmacion operativa:
   - login
   - apertura de turno
   - venta
   - impresion
   - reinicio de app/equipo
1. Promover a `stable`.
1. Monitorear heartbeats, health local y errores de instalacion.

## Actualización fácil para clientes

- **Automática:** Watchtower en cada nodo hace pull cada **15 minutos** (`WATCHTOWER_POLL_INTERVAL=900`). Al publicar una nueva imagen en GHCR, los nodos se actualizan solos en ese margen.
- **Inmediata (Linux):** En el nodo, ejecutar `cd /opt/posvendelo && ./actualizar.sh` (o `./actualizar.sh --dir /ruta/instalacion`). El script hace `docker compose pull api` y `docker compose up -d api`.
- **Inmediata (Windows):** En el directorio de instalación, ejecutar `docker compose --env-file .env pull api` y `docker compose --env-file .env up -d api`.
- El instalador Linux copia `actualizar.sh` al directorio de instalación y deja el comando en `INSTALL_SUMMARY.txt`.

## Publicacion de fixes

### Rollback backend

1. Publicar imagen `ghcr.io/...:VERSION`.
1. Publicar metadata `artifact=backend`.
1. Asignar por sucursal/canal si es necesario.
1. Permitir que Watchtower haga pull/restart.

### Rollback desktop

1. Publicar artefacto por plataforma.
1. Publicar `SHA256SUMS.txt`.
1. Publicar metadata `electron-linux` y/o `electron-windows`.
1. El nodo detecta el update y lo deja en `staged`.
1. Aplicar manualmente en piloto; luego abrir rollout masivo.

## Rollback

### Backend

La via mas segura es repinear la sucursal o canal a una version previa:

1. Identificar ultima version sana.
1. Actualizar `release_assignments` o canal a esa version.
1. Esperar refresh del nodo y restart del backend.

### Desktop

Rollback actual:

1. No aplicar el update si el staging falla o el checksum no coincide.
1. Si el update ya fue descargado, usar `Descartar`.
1. En Linux AppImage, usar `Rollback app` para restaurar el binario previo.
1. En Windows/instaladores externos, volver a publicar/asignar una version previa como release vigente.

Rollback siguiente recomendado:

- guardar puntero fuerte al binario anterior instalado,
- confirmar health posterior al update,
- si falla, relanzar instalador/binario previo automaticamente.

## Criterios para promover a estable

- health local correcto
- login correcto
- licenciamiento correcto
- venta simple correcta
- no errores nuevos en instalacion
- sin alertas relevantes en sucursal piloto

## Riesgos a evitar

- publicar release sin checksum de desktop
- mover todas las sucursales a la vez
- mezclar cambios de backend y desktop sin piloto
- depender de `latest` en hotfixes criticos cuando conviene version fija

## Estado actual

- `backend`: listo para rollout por metadata/canal/asignacion
- `desktop`: listo para deteccion, descarga, verificacion SHA256, staging y aplicacion
- `rollback AppImage Linux`: listo con backup local y relanzamiento
- `rollback Windows instalador`: asistido por control-plane/canal, pendiente de endurecer al siguiente nivel
