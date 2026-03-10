# GitHub — TITAN POS

## Workflows

| Workflow | Disparador | Uso |
|----------|------------|-----|
| `release.yml` | Push de tag `v*` o manual | Genera instaladores (Windows, Linux) y los sube a GitHub Release. |
| `deploy.yml` | Según configuración | Despliegue del backend/servicios. |
| `security.yml` | Según configuración | Escaneo de seguridad (dependencias, secretos). |

## Rama por defecto

- **master**: rama principal. Todo el trabajo se integra aquí.
