# E2E en navegador (Playwright) — Suite unificada V7

Todos los tests E2E en navegador están en **un solo archivo**: `e2e-browser-v7.spec.ts`.  
Se ejecutan en un **navegador real** (Chromium), no con scripts que simulan el DOM.

## Requisitos

1. **Backend** en la URL configurada en `POSVENDELO_API_URL` o `POSVENDELO_TEST_API_URL`:

   ```bash
   cd backend && set -a && source .env && set +a && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Frontend** en modo navegador en la URL configurada en `POSVENDELO_BROWSER_URL` o `E2E_BASE_URL`:

   ```bash
   npm run dev:browser
   ```

3. Credenciales E2E exportadas:

   ```bash
   export E2E_USER=<usuario_valido>
   export E2E_PASS=<password_valido>
   ```

## Ejecutar

```bash
# Con el frontend ya abierto en otra terminal (recomendado)
npm run test:e2e

# O que Playwright levante el frontend (puerto 5173 libre)
E2E_START_SERVER=1 npm run test:e2e
```

## Ejecutar En Modo Producción

Para validar el artefacto compilado contra el backend desplegado:

```bash
# 1. Generar build browser de producción
npm run build:browser

# 2. Servir el build compilado en un origen permitido por CORS
cd src/renderer/dist-browser && python3 -m http.server 8080

# 3. Ejecutar Playwright contra el build estático y el backend real
cd ../../..
E2E_BASE_URL=http://127.0.0.1:8080 \
E2E_API_URL=http://127.0.0.1:8000 \
E2E_USER=admin \
E2E_PASS=admin \
npx playwright test
```

Los helpers E2E siembran `pos.baseUrl` y `pos.discoverPorts` antes del login para que los tests no dependan del proxy de desarrollo ni del auto-discovery implícito.

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
