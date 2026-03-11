# POSVENDELO — Checklist de seguridad

Referencia rápida para revisión y despliegue seguro. Ver también `.cursor/rules/security.mdc`.

## Herramientas de seguridad (SAST, dependencias, secretos)

En CI (GitHub Actions) se ejecuta el workflow **Security** (`.github/workflows/security.yml`) en cada push/PR a `master`:

| Herramienta | Qué hace | Config |
|-------------|----------|--------|
| **Bandit** | SAST Python (inyección, crypto débil, pickle, etc.) | `backend/.bandit.yaml` |
| **pip-audit** | Vulnerabilidades conocidas en dependencias Python | — |
| **Semgrep** | SAST multi-lenguaje (Python, TypeScript, React) | `--config auto` + p/python, p/typescript, p/react |
| **Gitleaks** | Detección de secretos en el repo | `.gitleaks.toml` |
| **npm audit** | Vulnerabilidades en deps Node (solo producción) | `--omit=dev --audit-level=high` |

**Ejecución local:**

```bash
# Todo (backend: Bandit + pip-audit; frontend: npm audit)
make security

# Solo backend
make security-backend

# Solo frontend
make security-frontend
```

Para **Semgrep** y **Gitleaks** en local (opcional):

```bash
pip install semgrep && semgrep scan --config auto backend/ frontend/src/
# Gitleaks: descargar binario desde https://github.com/gitleaks/gitleaks/releases
gitleaks detect --config .gitleaks.toml --source . --verbose
```

## Antes de producción

- [ ] **DEBUG=false** — No exponer `/docs` ni relajar rate limits.
- [ ] **JWT_SECRET** — Variable de entorno con valor aleatorio largo (no el de `.env.example`).
- [ ] **DATABASE_URL** — Credenciales fuertes; no usar la de desarrollo.
- [ ] **.env** — Nunca en git; verificar que está en `.gitignore`.
- [ ] **CORS** — Orígenes explícitos; no `*` con credentials.

## Auditoría de dependencias

- **Backend:** en CI se usa `pip-audit`. En local: `cd backend && pip install -r requirements.txt pip-audit && pip-audit`.
- **Frontend:** en CI se usa `npm audit --omit=dev --audit-level=high`. En local: `cd frontend && npm audit --omit=dev`.

Si hay vulnerabilidades, actualizar paquetes afectados y volver a ejecutar hasta que no se reporten.

**Dependencia xlsx (frontend):** Se usa SheetJS Community Edition 0.20.3 desde el CDN oficial (`https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz`) en lugar del paquete `xlsx` de npm (sin mantenimiento y con vulnerabilidades). Uso: export/import Excel en `ProductsTab.tsx` y `CustomersTab.tsx`. No cambiar a la versión de npm; mantener la URL en `frontend/package.json`.

## Controles ya implementados

| Control | Ubicación |
|--------|-----------|
| Precios desde DB en ventas | `modules/sales/routes.py` — `_calculate_item()` usa `prod.get("price")` para ítems con `product_id`. |
| SQL parametrizado | `db/connection.py` — parámetros nombrados `:name` → posicionales; sin concatenar input. |
| Escape LIKE/ILIKE | `db/connection.escape_like()`; usado en productos, clientes, empleados, ventas, SAT, xml_ingestor. |
| Null bytes | `main.py` — middleware `NullByteSanitizer` elimina `\x00` y `%00`. |
| Login rate limit | `modules/auth/routes.py` — 5/min (prod) o 25/min (DEBUG). |
| PIN rate limit | `modules/shared/rate_limit.py` — 5 intentos / 5 min por IP. |
| PIN en cancelación | `modules/sales/routes.py` — `SaleCancelRequest.manager_pin` + `verify_manager_pin()`. |
| Health sin fuga | `main.py` — 503 con mensaje genérico; solo en DEBUG se registra causa. |

## Reportar vulnerabilidades

Si encuentras un fallo de seguridad, no abras un issue público. Contacta al mantenedor del proyecto de forma privada.
