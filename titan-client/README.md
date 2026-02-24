# TITAN POS — Paquete Cliente

Este directorio contiene **solo lo necesario para instalar y ejecutar un PC cliente** (terminal POS que se conecta al servidor central).

## Instalación

1. Copiar este directorio al PC cliente
2. Editar `config.json` con la IP del servidor central
3. Ejecutar la app Electron (compilada desde `../frontend/`)

## Configuración

Editar `config.json`:
```json
{
  "server_ip": "192.168.1.100",
  "server_port": 8000,
  "terminal_id": 2,
  "branch_name": "Sucursal X"
}
```

## Nota

El código fuente del frontend está en `../frontend/` (desarrollo).
Para compilar: `cd ../frontend && npm install && npm run build`
Este directorio es solo el paquete de despliegue para PCs cliente.
