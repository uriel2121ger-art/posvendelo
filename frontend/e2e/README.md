# E2E en navegador (Playwright) — Suite unificada V7

Todos los tests E2E en navegador están en **un solo archivo**: `e2e-browser-v7.spec.ts`.  
Se ejecutan en un **navegador real** (Chromium), no con scripts que simulan el DOM.

## Requisitos

1. **Backend** en `http://127.0.0.1:8000`:
   ```bash
   cd backend && set -a && source .env && set +a && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```
2. **Frontend** en modo navegador en `http://localhost:5173`:
   ```bash
   npm run dev:browser
   ```
3. Usuario de prueba: `admin` / `admin123` (o el que tengas en la BD).

## Ejecutar

```bash
# Con el frontend ya abierto en otra terminal (recomendado)
npm run test:e2e

# O que Playwright levante el frontend (puerto 5173 libre)
E2E_START_SERVER=1 npm run test:e2e
```

Con navegador visible:

```bash
npm run test:e2e:ui
```

## Qué cubre (e2e-browser-v7.spec.ts)

| Bloque                    | Contenido                                                                                                                                                                                                                                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **E2E-1**                 | Login exitoso/fallido, ruta protegida sin token, cierre de sesión.                                                                                                                                                                                                                                                         |
| **E2E-17**                | Navbar a cada ruta (15 ítems), ruta inexistente → terminal.                                                                                                                                                                                                                                                                |
| **Carga de pestañas**     | Clientes, Productos, Inventario, Turnos, Reportes, Historial, Configuraciones, Estadísticas, Mermas, Gastos, Empleados, Remoto, Fiscal, Hardware (que cada tab cargue y muestre contenido).                                                                                                                                |
| **Flujos E2E-2**          | Terminal: buscador F10, F9 verificador precios, Guardar/Cobrar deshabilitados con carrito vacío.                                                                                                                                                                                                                           |
| **Flujos E2E-3 a E2E-16** | Clientes (Cargar, búsqueda, alta), Productos (Cargar, búsqueda, Stock Bajo), Inventario (Cargar, búsqueda, Alertas), Turnos, Reportes (Local/Daily/Ranking), Historial (Buscar), Configuraciones (Base URL, Sync), Mermas, Gastos (formulario, monto/descripción), Empleados (Cargar, búsqueda), Remoto, Fiscal, Hardware. |

En total, **~49 tests** en un único spec. Todos los flujos se ejecutan en el navegador real contra la app y el API.
