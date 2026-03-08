# Después de deploy

## Reiniciar servicios (Docker)

En la raíz del proyecto:

```bash
# Rebuild local + recreate del backend real
docker build -t ghcr.io/uriel2121ger-art/titan-pos:latest backend
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate api

# Si solo quieres reiniciar el contenedor ya desplegado:
docker restart puntodeventa-api-1
```

## Verificación mínima post-deploy

Comprobar salud:

```bash
curl http://127.0.0.1:8000/health
```

Comprobar que el runtime cargó el rate-limit esperado:

```bash
docker exec puntodeventa-api-1 /bin/sh -lc 'cd /app && python - <<'"'"'PY'"'"'
from modules.auth import routes
print(routes._login_rate)
PY'
```

En producción debe imprimir `30/minute` salvo que se haya definido otro valor en `LOGIN_RATE_LIMIT`.

## Higiene operativa

- No dejar una API dev escuchando en `8090` cuando se esté validando el runtime real de `8000`.
- Si el frontend usa auto-discovery, en producción preferir discovery acotado a `8000,8080`.
- Tras recrear `api`, ejecutar un smoke corto de login + navegación para confirmar que el contenedor nuevo sí quedó atendiendo tráfico.

## Limpiar caché del navegador / Electron

Para que la app cargue la última versión del frontend sin caché antigua:

- **Electron (app de escritorio):** Cerrar la app por completo y volver a abrirla. Si sigue usando código viejo, eliminar datos de la aplicación:
  - Linux: `~/.config/titan-pos/` (o el nombre de la app) y volver a abrir.
- **Navegador (dev con Vite):** Recarga forzada: `Ctrl+Shift+R` (o `Cmd+Shift+R` en Mac). O en DevTools (F12) → pestaña Application/Storage → "Clear site data" / "Borrar datos del sitio".
- **Chrome/Chromium:** `Ctrl+Shift+Delete` → marcar "Imágenes y archivos en caché" → Borrar datos.

Tras deploy, conviene hacer al menos una recarga forzada (`Ctrl+Shift+R`) en la pestaña del POS.
