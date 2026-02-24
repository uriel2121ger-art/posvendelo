# TITAN POS — Paquete Servidor

Este directorio contiene **solo lo necesario para instalar y ejecutar un PC servidor** (servidor central con PostgreSQL + gateway de sincronización).

## Contenido

- `server/` — Gateway FastAPI (sincronización multi-sucursal)
- `migrations/` — Migraciones SQL para PostgreSQL
- `scripts/` — Scripts operativos (backups, fixes)
- `data/` — Configuración local + catálogo SAT
- `instalar.sh` — Instalador principal
- `titan_pos.sh` — Script de arranque
- `requirements.txt` — Dependencias Python

## Instalación

```bash
chmod +x instalar.sh
./instalar.sh
```

## Nota

El código fuente completo del proyecto está en `../backend/` (desarrollo).
Este directorio es solo el paquete de despliegue para PCs servidor.
