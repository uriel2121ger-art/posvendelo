# TITAN Gateway - Servidor Central Multi-Sucursal

Este servidor centraliza los datos de todas las sucursales de TITAN POS.

## Instalación Rápida

```bash
# 1. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar servidor
python titan_gateway.py
```

## Endpoints Principales

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/status` | GET | Estado del servidor y sucursales |
| `/api/branches/register` | POST | Registrar nueva sucursal |
| `/api/sync` | POST | Recibir datos de sincronización |
| `/api/sync/products` | GET | Obtener actualizaciones de productos |
| `/api/products/update` | POST | Actualizar producto (propaga a todas) |
| `/api/backup/upload` | POST | Subir backup de sucursal |
| `/api/backups` | GET | Listar backups disponibles |
| `/api/reports/sales` | GET | Reporte consolidado de ventas |
| `/api/reports/branches` | GET | Estado de todas las sucursales |

## Autenticación

Todos los endpoints (excepto `/health`) requieren token Bearer:

```
Authorization: Bearer <token>
```

El token de administrador se genera automáticamente la primera vez que se ejecuta el servidor.

## Configuración para Producción

1. Usar HTTPS (nginx como reverse proxy)
2. Configurar Tailscale para acceso seguro
3. Habilitar backups automáticos del directorio `gateway_data/`

## Estructura de Datos

```
gateway_data/
├── config.json          # Configuración del servidor
├── tokens.json          # Tokens de autenticación por sucursal
├── product_updates.json # Actualizaciones de productos
├── backups/             # Backups recibidos de sucursales
│   ├── 1/               # Sucursal 1
│   └── 2/               # Sucursal 2
├── sales/               # Ventas recibidas
│   ├── 1_20241228.jsonl # Ventas sucursal 1
│   └── 2_20241228.jsonl # Ventas sucursal 2
└── branches/            # Info de sincronización por sucursal
    ├── 1_last_sync.json
    ├── 1_inventory.json
    └── 1_customers.json
```
