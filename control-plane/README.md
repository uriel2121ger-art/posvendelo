# TITAN Control Plane

Servicio central para gestionar flota de sucursales TITAN POS.

## Incluye

- registro de tenants y sucursales
- bootstrap config por token de instalacion
- compose template para nodos cliente
- contrato de bootstrap para agente local (`titan-agent.json`)
- heartbeats de sucursales
- dashboard HTML simple
- releases y asignaciones por sucursal
- manifest de releases por sucursal/canal
- publicacion autenticada de releases desde CI
- provision simulada de tunnels
- provision real opcional con Cloudflare API
- audit log basico de acciones admin
- licenciamiento local-first firmado

## Arranque local

1. Copiar `.env.example` a `.env`
1. Ajustar `POSTGRES_PASSWORD`, `CP_ADMIN_TOKEN` y `CP_BASE_URL`
1. Ejecutar:

```bash
docker compose up -d
```

1. Verificar:

```bash
curl http://localhost:9090/health
```

## Flujo minimo

1. Crear tenant:

```bash
ADMIN_HEADER="X-Admin-Token"
curl -X POST http://localhost:9090/api/v1/tenants/ \
  -H "${ADMIN_HEADER}: ${CP_ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Cliente Demo","slug":"cliente-demo"}'
```

1. Tomar `install_token` de la sucursal bootstrap.
1. Obtener config:

```bash
curl "http://localhost:9090/api/v1/branches/bootstrap-config?install_token=TOKEN"
```

La respuesta de bootstrap ahora incluye tambien:

- `release_manifest_url`
- `compose_template_url`
- `register_url`
- `install_report_url`
- `bootstrap_public_key`
- `companion_url`
- `companion_entry_url`
- `license_resolve_url`
- `owner_session_url`
- `owner_api_base_url`
- `quick_links`
- `license`

Esos campos permiten que el instalador y el agente local compartan el mismo contrato de aprovisionamiento.

## Companion y Acceso Del Dueño

Flujo recomendado:

1. El instalador consume `bootstrap-config` y guarda `titan-agent.json`.
2. El agente local usa `install_token` para pedir `POST /api/v1/owner/session`.
3. La app desktop consume al agente local, no al `install_token` crudo.
4. El companion usa las rutas ya publicadas por `companion_entry_url` y `quick_links`.

Endpoints relevantes:

- `POST /api/v1/owner/session`
- `GET /api/v1/owner/portfolio`
- `GET /api/v1/owner/alerts`
- `GET /api/v1/owner/events`
- `GET /api/v1/owner/branches/{branch_id}/timeline`
- `GET /api/v1/owner/commercial`
- `GET /api/v1/owner/health-summary`
- `GET /api/v1/owner/audit`

Objetivo:

- no pedir al usuario final rutas manuales
- no exponer el `install_token` como credencial de uso diario
- dejar listo el companion para soporte, dueño y operación multi-sucursal

## Licencias

Rutas disponibles:

- `GET /api/v1/licenses/resolve` con `X-Install-Token: ...`
- `POST /api/v1/licenses/activate-device`
- `POST /api/v1/licenses/refresh`
- `POST /api/v1/licenses/revoke`
- `POST /api/v1/licenses/issue`

Emitir o renovar una licencia:

```bash
ADMIN_HEADER="X-Admin-Token"
curl -X POST http://localhost:9090/api/v1/licenses/issue \
  -H "${ADMIN_HEADER}: ${CP_ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":1,"license_type":"monthly","valid_until":"2026-04-01T00:00:00","grace_days":5}'
```

Exportar `titan-license.json` para un cliente offline:

```bash
python3 scripts/license_admin.py \
  --base-url http://localhost:9090 \
  export-file \
  --install-token TOKEN \
  --machine-id EQUIPO-001 \
  --output titan-license.json
```

1. Descargar compose:

```bash
curl "http://localhost:9090/api/v1/branches/compose-template?install_token=TOKEN"
```

1. Registrar heartbeat:

```bash
curl -X POST http://localhost:9090/api/v1/heartbeat/ \
  -H "Content-Type: application/json" \
  -d '{"branch_id":1,"status":"ok","sales_today":0}'
```

1. Publicar metadata de release desde CI o manual:

```bash
RELEASE_HEADER="X-Release-Token"
curl -X POST http://localhost:9090/api/v1/releases/publish \
  -H "${RELEASE_HEADER}: ${CP_RELEASES_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"platform":"desktop","artifact":"electron-linux","version":"2.0.0","channel":"stable","target_ref":"https://github.com/ORG/REPO/releases/download/v2.0.0/titan-pos-2.0.0.AppImage","source":"manual"}'
```

1. Resolver manifest de releases para una sucursal:

```bash
curl "http://localhost:9090/api/v1/releases/manifest" \
  -H "X-Install-Token: TOKEN"
```

Para rollout y rollback operativo, consulta `../docs/ROLLOUT_UPDATES_Y_ROLLBACK.md`.

1. Reportar estado de instalacion desde un bootstraper:

```bash
curl -X POST http://localhost:9090/api/v1/branches/install-report \
  -H "Content-Type: application/json" \
  -d '{"install_token":"TOKEN","status":"success","pos_version":"2.0.0"}'
```

## Notas

- `tunnel/provision` usa `CF_TUNNEL_MODE=simulate` por defecto. Cambialo a `cloudflare` y configura `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_ZONE_ID` y `CF_PUBLIC_BASE_DOMAIN` para provision real.
- `alarms/telegram.py` incluye la logica base para detectar sucursales offline, backups vencidos y disco alto.
- Configura `CP_RELEASES_TOKEN` para separar permisos de CI y admin.
- El pipeline de release puede publicar `target_ref` directo a assets de GitHub Releases por plataforma.
- El manifest de releases también expone `checksums_manifest_url` para desktop cuando el `target_ref` apunta a assets HTTP/HTTPS.
- `CP_LICENSE_PRIVATE_KEY` debe configurarse en producción. Si falta, el control-plane usa una clave efímera solo válida para desarrollo.
- `CP_COMPANION_URL` permite anunciar la URL del companion movil/web desde el control-plane.
- `CP_OWNER_SESSION_SECRET` permite separar la firma de sesiones del dueño del `CP_ADMIN_TOKEN`.
- `db/migrations/` permite aplicar cambios incrementales del schema en despliegues existentes.
