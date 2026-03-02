# Pruebas manuales en el navegador — TITAN POS V2

Ejecuta estos pasos **manualmente** en el navegador (http://localhost:5173) con el backend en 8000.

## Ejecución manual en navegador (agente vía MCP)

Pruebas realizadas **por el agente** en el navegador real (cursor-ide-browser):

| Prueba | Acción | Resultado |
|--------|--------|-----------|
| **E2E-1.1** | Login con admin / admin123 → INGRESAR | ✅ Redirige a `#/terminal` |
| **E2E-17.1** | Clic en Clientes, Productos, Inventario | ✅ URL cambia a #/clientes, #/productos, #/inventario; contenido de cada pestaña visible |
| **E2E-17.2** | Navegar a `#/ruta-inexistente-xyz` | ✅ Redirige a `#/terminal` |
| **E2E-1.5** | Clic en Cerrar sesión → Aceptar en el modal | ✅ Vuelve a `#/login` |
| **E2E-17.1 (resto)** | Navegación a Turnos, Reportes, Historial, Ajustes, Stats, Mermas, Gastos, Empleados, Remoto, Fiscal, Hardware | ✅ Cada URL carga (#/turnos, #/reportes, #/historial, #/configuraciones, #/estadisticas, #/mermas, #/gastos, #/empleados, #/remoto, #/fiscal, #/hardware) |

*Nota:* Para que el snapshot del navegador devuelva refs de elementos, hay que usar `browser_snapshot` con `take_screenshot_afterwards: true`. Con esos refs (e0, e1, …) se puede usar `browser_type`, `browser_click`, etc.

---

## Última ejecución automática en navegador (Playwright)

Los tests E2E de Playwright se ejecutan en un **navegador real** (Chromium). Última corrida:

- **Login y navegación:** E2E-1.1, 1.2, 1.4, 1.5, E2E-17.1, 17.2 — ✅ pasan.
- **Pestañas:** Productos, Inventario, Turnos, Reportes, Historial, Mermas, Gastos, Empleados, Remoto — ✅ pasan. Clientes, Configuraciones, Stats, Fiscal, Hardware — criterios de texto ajustados para mayor robustez.

Para repetir en navegador: `cd frontend && npm run test:e2e` (con backend y frontend levantados).

---

## Requisitos

- Frontend: `npm run dev:browser` → http://localhost:5173
- Backend: `cd backend && set -a && source .env && set +a && uvicorn main:app --host 0.0.0.0 --port 8000`
- Usuario: `admin` / `admin123` (o el que tengas en la BD)

---

## E2E-1: Login y arranque

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1.1 | Ir a `http://localhost:5173/#/login`. Escribir usuario y contraseña válidos. Clic en **INGRESAR**. | Redirige a `#/terminal`; puede aparecer modal "Abrir turno". Token y usuario en localStorage. |
| 1.2 | En login, escribir usuario/contraseña incorrectos → **INGRESAR**. | Mensaje de error; no redirige; no se guarda token. |
| 1.3 | Apagar backend, recargar login. | Mensaje tipo "No se encontró el servidor" o "Buscando servidor...". |
| 1.4 | Sin estar logueado, ir a `http://localhost:5173/#/productos`. | Redirige a `#/login`. |
| 1.5 | Logueado, cerrar modal de turno (Continuar turno o Abrir turno con fondo 100). Clic en **Cerrar sesión** (icono rojo) → **Aceptar**. | Vuelve a `#/login`; token y usuario ya no en localStorage. |

---

## E2E-17: Navegación

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 17.1 | Logueado, clic en cada ítem del navbar: Ventas, Clientes, Productos, Inventario, Turnos, Reportes, Historial, Ajustes, Stats, Mermas, Gastos, Empleados, Remoto, Fiscal, Hardware. | La URL cambia a la ruta correcta y la pantalla muestra el contenido de esa pestaña. |
| 17.2 | Con sesión activa, ir a `http://localhost:5173/#/ruta-inexistente`. | Redirige a `#/terminal`. |

---

## E2E-2 a E2E-16: Carga de pestañas

En cada pestaña, comprobar que **la pantalla carga sin error** y se ve texto/controles propios del módulo.

| Pestaña | Qué comprobar |
|---------|----------------|
| **Ventas (F1)** | Carrito, buscador, total, botón Cobrar. |
| **Clientes (F2)** | Texto "Clientes (F2)" o lista/búsqueda de clientes. |
| **Productos (F3)** | "Productos (F3)", lista o búsqueda, SKU/precio. |
| **Inventario (F4)** | "Inventario (F4)", movimientos entrada/salida. |
| **Turnos (F5)** | Turno, abrir/cerrar, efectivo, resumen. |
| **Reportes (F6)** | Local/Daily/Ranking, fechas, ventas. |
| **Historial** | Búsqueda por fechas/folio, lista de ventas. |
| **Ajustes** | Base URL, Terminal ID, perfiles, Guardar. |
| **Stats** | Paneles Quick/Resico o equivalentes. |
| **Mermas** | Pendientes, aprobar/rechazar. |
| **Gastos** | Monto, descripción, resumen mes/año. |
| **Empleados** | Lista, nombre, código. |
| **Remoto** | Estado turno, ventas en vivo. |
| **Fiscal** | Facturación, CFDI, devolución. |
| **Hardware** | Impresora, negocio, escáner, cajón. |

---

## Atajos F1–F11 (opcional)

- Con foco **fuera** de inputs: F1–F6 deben cambiar de pestaña; F7/F8/F9 abren modales (Entrada/Retiro efectivo, Verificador precios); F10/F11 no cambian ruta.
- Con foco **en** un input (p. ej. buscador): F1–F11 no deben cambiar de pestaña.

---

## Registro manual

Anota aquí el resultado (OK / Fallo y nota):

| Fecha | E2E-1.1 | E2E-1.2 | E2E-1.5 | E2E-17.1 | Clientes | Productos | … | Observaciones |
|-------|---------|---------|---------|----------|----------|-----------|---|---------------|
|       |         |         |         |          |          |           |   |               |

---

*Documento para ejecutar las pruebas manuales en el navegador según PLAN_TESTING_V6.*
