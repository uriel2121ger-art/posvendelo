# TITAN POS — Mapa Completo del Frontend

> Generado: 2026-02-26
> Cubre: 13 vistas, 16 endpoints, ~40 botones, ~30 campos, ~10 filtros

---

## Arquitectura General

- **Framework**: Electron + React (HashRouter)
- **Estilos**: Tailwind CSS (tema zinc oscuro)
- **Estado**: useState local + localStorage persistente
- **API**: `apiFetch()` centralizado en `posApi.ts`
- **Timeout**: 3s (AbortController) en todas las llamadas
- **Headers**: `Authorization: Bearer {token}`, `X-Terminal-Id: {terminalId}`, `Content-Type: application/json`
- **Error 401**: Limpia token, redirige a `/login`
- **Iconos**: Lucide React

---

## Routing (F-Keys)

| Tecla | Ruta | Vista | Archivo |
|-------|------|-------|---------|
| — | `/login` | Login | `Login.tsx` |
| F1 | `/terminal` | Punto de Venta | `Terminal.tsx` |
| F2 | `/clientes` | Clientes | `CustomersTab.tsx` |
| F3 | `/productos` | Productos | `ProductsTab.tsx` |
| F4 | `/inventario` | Inventario | `InventoryTab.tsx` |
| F5 | `/turnos` | Turnos | `ShiftsTab.tsx` |
| F6 | `/reportes` | Reportes | `ReportsTab.tsx` |
| F7 | `/historial` | Historial Ventas | `HistoryTab.tsx` |
| F8 | `/configuraciones` | Ajustes | `SettingsTab.tsx` |
| F9 | `/estadisticas` | Dashboard Stats | `DashboardStatsTab.tsx` |
| F10 | `/mermas` | Mermas | `MermasTab.tsx` |
| F11 | `/gastos` | Gastos | `ExpensesTab.tsx` |

Navbar: `TopNavbar.tsx` — tabs horizontales con iconos Lucide, usuario a la derecha.

---

## 1. Login (`/login`)

### Campos
| Campo | Tipo | Placeholder | Validación |
|-------|------|-------------|------------|
| username | text | "Nombre de usuario" | required, trim |
| password | password | "••••••••" | required |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| INGRESAR | handleLogin → POST login | `POST /api/v1/auth/login` |

### API
```
POST /api/v1/auth/login
Body: {username, password}
Resp: {token} o {access_token}
→ Guarda titan.token, titan.user en localStorage
→ Navega a /terminal
```

---

## 2. Terminal / Ventas (`/terminal`)

### Layout: 3 paneles (productos | carrito | pago)

### Panel Izquierdo — Búsqueda de Productos
| Campo | Tipo | Placeholder |
|-------|------|-------------|
| Buscar producto | text | "Buscar producto por nombre o SKU" |
| Categoría | dropdown | Categorías dinámicas |

**Tabla productos**: Imagen | SKU | Nombre | Precio | Stock
**Clic en fila** → agrega al carrito

### Panel Centro — Carrito
**Tabla carrito**: SKU | Nombre | Qty | Precio | Descuento% | Subtotal

| Elemento | Tipo | Acción |
|----------|------|--------|
| +/- qty | botones | Incrementa/decrementa cantidad |
| Descuento | input % | Descuento por ítem |
| Eliminar | botón X | Quita ítem del carrito |

**Totales**: Subtotal, Descuento, IVA 16%, Total

| Botón | Acción |
|-------|--------|
| Descontar % | Descuento global al ticket |
| Vaciar carrito | Limpia todos los ítems |
| Pausa | Guarda ticket en `titan.pendingTickets` |
| Retomar | Carga ticket pendiente |

### Panel Derecho — Cobro
| Campo | Tipo | Placeholder |
|-------|------|-------------|
| Cliente | text | "Nombre cliente (opcional)" |
| Método pago | dropdown | Efectivo / Tarjeta / Transferencia / Mixto |
| Efectivo recibido | number | "Monto recibido" (solo cash/mixto) |
| Splits (mixto) | 3x number | Efectivo / Tarjeta / Transferencia |

| Botón | Acción | Endpoint |
|-------|--------|----------|
| **COBRAR** | handleCharge → createSale | `POST /api/v1/sales/` |
| Pendiente | Guarda a localStorage | — |

### API
```
GET  /api/v1/sync/products          ← Carga productos (mount)
POST /api/v1/sales/
Body: {items: [{product_id, qty, price, discount, is_wholesale, price_includes_tax}],
       payment_method, customer_id, turn_id, branch_id, cash_received, notes,
       mixed_cash, mixed_card, mixed_transfer}
Resp: {folio, total, data}
```

### Atajos de Teclado
| Atajo | Acción |
|-------|--------|
| F10 | Focus en búsqueda |
| F12 | Ejecutar cobro |
| +/- | Aumentar/disminuir qty |
| Delete/Backspace | Quitar ítem |
| Ctrl+P | Producto genérico |
| Ctrl+D | Descuento por producto |
| Ctrl+G | Descuento global |
| Ctrl+N | Nuevo ticket activo |

---

## 3. Clientes (`/clientes`)

### Campos del Formulario
| Campo | Tipo | Placeholder | Validación |
|-------|------|-------------|------------|
| Nombre | text | "Nombre cliente" | required |
| Teléfono | text | "Telefono" | opcional |
| Email | text | "Email" | opcional |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Guardar/Actualizar | syncTable('customers') | `POST /api/v1/sync/customers` |
| Cargar | pullTable('customers') | `GET /api/v1/sync/customers` |
| Nuevo | Limpia formulario | — |
| Eliminar | sync con deleted:true | `POST /api/v1/sync/customers` |

### Filtro
| Filtro | Tipo | Busca en |
|--------|------|----------|
| Buscar cliente | text | nombre, teléfono, email |

### Tabla
**Columnas**: Nombre | Teléfono | Email
**Paginación**: 50 por página, botones Anterior/Siguiente
**Selección**: clic en fila → carga en formulario

---

## 4. Productos (`/productos`)

### Campos del Formulario
| Campo | Tipo | Placeholder | Validación |
|-------|------|-------------|------------|
| SKU | text | "SKU" | required, disabled al editar |
| Nombre | text | "Nombre producto" | required |
| Precio | number | "Precio" | required, min:0 |
| Stock | number | "Stock" | min:0 |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Guardar/Actualizar | syncTable('products') | `POST /api/v1/sync/products` |
| Cargar | pullTable('products') | `GET /api/v1/sync/products` |
| Nuevo | Limpia formulario | — |
| Eliminar | sync con deleted:true | `POST /api/v1/sync/products` |

### Filtro
| Filtro | Tipo | Busca en |
|--------|------|----------|
| Buscar producto | text | SKU, nombre |

### Tabla
**Columnas**: SKU | Nombre | Precio | Stock
**Paginación**: 50 por página

---

## 5. Inventario (`/inventario`)

### Campos
| Campo | Tipo | Placeholder | Validación |
|-------|------|-------------|------------|
| SKU | text | "SKU para movimiento" | required |
| Tipo | dropdown | Entrada / Salida | — |
| Cantidad | number | "Cantidad" | min:1 |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| **Aplicar** | adjustStock() | `POST /api/v1/inventory/adjust` |
| Cargar | pullTable('products') | `GET /api/v1/sync/products` |

### API
```
POST /api/v1/inventory/adjust
Body: {product_id, quantity (signed: + entrada, - salida), reason: "Ajuste manual..."}
Resp: {data: {new_stock}}
```

### Filtro
| Filtro | Tipo | Busca en |
|--------|------|----------|
| Buscar por SKU o nombre | text | SKU, nombre |

### Tabla
**Columnas**: SKU | Nombre | Stock
**Paginación**: 50 por página

---

## 6. Turnos (`/turnos`)

### Campos — Apertura
| Campo | Tipo | Placeholder | Default |
|-------|------|-------------|---------|
| Operador | text | "Operador" | "Cajero 1" |
| Efectivo inicial | number | "Efectivo inicial" | 0 |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| **Abrir turno** | openTurn() | `POST /api/v1/turns/open` |
| **Cerrar turno** | closeTurn() | `POST /api/v1/turns/{id}/close` |
| Conciliar con backend | searchSales → filtrar | `GET /api/v1/sales/search` |
| Exportar corte CSV | downloadCsv() | — (local) |
| Imprimir corte | window.open + print() | — (local) |
| Aplicar esperado sugerido | Calcula cierre sugerido | — |

### Selector
| Selector | Tipo | Opciones |
|----------|------|----------|
| Turno | dropdown | "Turno activo" + historial |

### Cards de Estado (3 columnas)
- Estado (Abierto/Sin turno)
- Operador actual
- Duración (HH:MM, actualiza cada 60s)

### Cards de Totales (4 columnas)
- Ventas turno (count)
- Total turno ($)
- Efectivo acumulado ($)
- Esperado sugerido cierre ($)

### Cards Conciliación (3 columnas)
- Ventas backend
- Diferencia total backend vs local ($)
- Diferencia efectivo backend vs local ($)

### Tabla Historial
**Columnas**: Apertura | Cierre | Operador | Inicial | Ventas | Total | Efectivo | Cierre | Esperado | Diferencia
**Límite**: 100 turnos recientes

### API
```
POST /api/v1/turns/open        Body: {initial_cash, branch_id:1, notes}
POST /api/v1/turns/{id}/close  Body: {final_cash, notes}  Resp: {expected_cash, difference}
GET  /api/v1/sales/search      Query: date_from, date_to, limit:2000  (reconciliación)
```

---

## 7. Reportes (`/reportes`)

### Campos
| Campo | Tipo | Default |
|-------|------|---------|
| Desde | date | hace 7 días |
| Hasta | date | hoy |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Recalcular | searchSales(500) | `GET /api/v1/sales/search` |
| Exportar resumen CSV | local | — |
| Exportar top CSV | local | — |

### KPIs (2 cards)
**Card izquierdo**: Ventas (count), Monto total ($), Ticket promedio ($)
**Card derecho**: Desglose por método de pago (dinámico)

### Tabla Top Productos
**Columnas**: SKU/Nombre | Cantidad | Importe
**Límite**: Top 10 por cantidad

---

## 8. Historial (`/historial`)

### Campos / Filtros
| Campo | Tipo | Placeholder | Default |
|-------|------|-------------|---------|
| Folio | text | "Folio" | — |
| Desde | date | — | hace 7 días |
| Hasta | date | — | hoy |
| Método pago | dropdown | Todos / Efectivo / Tarjeta / Transferencia | Todos |
| Total min | number | "Total min" | — |
| Total max | number | "Total max" | — |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Buscar | searchSales(200) + filtros locales | `GET /api/v1/sales/search` |
| Exportar CSV | local | — |

### Lista de Ventas (panel izquierdo)
**Columnas**: Folio | Fecha | Cliente | Total
**Selección**: clic → carga detalle

### Panel Detalle (derecha)
- Folio, Cliente, Método, Total
- JSON completo de la venta (pre-formatted)

### API
```
GET /api/v1/sales/search    Query: folio, date_from, date_to, limit:200
GET /api/v1/sales/{saleId}  ← Detalle individual
GET /api/v1/sync/sales      ← Fallback si detail falla (limit:2000)
```

---

## 9. Configuraciones (`/configuraciones`)

### Campos — Conexión
| Campo | Tipo | Placeholder | Default |
|-------|------|-------------|---------|
| Base URL | text | "Base URL" | `http://127.0.0.1:8000` |
| Token | password | "Token" | localStorage |
| Terminal ID | number | "Terminal ID" | 1 |

### Campos — Perfiles
| Campo | Tipo | Placeholder |
|-------|------|-------------|
| Nombre perfil | text | "Nombre del perfil (ej. Caja 1)" |
| Seleccionar perfil | dropdown | Lista de perfiles guardados |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Guardar | saveRuntimeConfig() | — (localStorage) |
| Probar conexión | getSystemInfo + getSyncStatus | `GET /api/v1/remote/system-status` + `GET /api/v1/sync/status` |
| Guardar perfil | Crea/actualiza perfil | — (localStorage) |
| Eliminar perfil | Borra perfil | — (localStorage) |

### Paneles Info (read-only)
- **Info del sistema**: JSON de system-status
- **Estado sincronización**: JSON de sync/status

---

## 10. Estadísticas (`/estadisticas`)

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Actualizar | fetchStats() | `GET /api/v1/dashboard/quick` |

### Auto-refresh: cada 30 segundos

### Cards (3 columnas)
| Card | Icono | Color | Valor |
|------|-------|-------|-------|
| Ventas Hoy | TrendingUp | emerald | ventas_hoy |
| Ingreso Hoy | DollarSign | blue | $total_hoy |
| Mermas Pendientes | AlertTriangle | amber/zinc | mermas_pendientes |

### Anti-race condition
Usa `requestIdRef` para ignorar respuestas obsoletas.

---

## 11. Mermas (`/mermas`)

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Recargar | fetchMermas() | `GET /api/v1/mermas/pending` |

### Tabla Mermas Pendientes
**Columnas**: Producto | Cantidad | Valor | Tipo | Razón | Fecha | Notas | Acciones

### Campos por fila
| Campo | Tipo | Propósito |
|-------|------|-----------|
| Notas | text | Nota antes de aprobar/rechazar |

### Botones por fila
| Botón | Acción | Endpoint |
|-------|--------|----------|
| ✓ Aprobar | approveMerma(id, true, notes) | `POST /api/v1/mermas/approve` |
| ✗ Rechazar | approveMerma(id, false, notes) | `POST /api/v1/mermas/approve` |

Ambos requieren confirmación (confirm dialog).

### API
```
GET  /api/v1/mermas/pending   Resp: {data: {mermas: [...]}}
POST /api/v1/mermas/approve   Body: {merma_id, approved: bool, notes}
```

---

## 12. Gastos (`/gastos`)

### Cards Resumen (2 columnas)
| Card | Icono | Color | Valor |
|------|-------|-------|-------|
| Total este mes | Receipt | blue | $monthTotal |
| Total este año | Receipt | purple | $yearTotal |

### Formulario "Registrar Gasto"
| Campo | Tipo | Placeholder | Validación |
|-------|------|-------------|------------|
| Monto ($) | number | "0.00" | required, min:0.01, step:0.01 |
| Descripción | text | "Ej: Luz, Agua, Insumos..." | required |
| Razón (opcional) | text | "Detalles adicionales..." | opcional |

### Botones
| Botón | Acción | Endpoint |
|-------|--------|----------|
| **Registrar** | registerExpense() | `POST /api/v1/expenses/` |
| Recargar | getExpensesSummary() | `GET /api/v1/expenses/summary` |

### API
```
GET  /api/v1/expenses/summary  Query: month, year  Resp: {data: {month, year}}
POST /api/v1/expenses/         Body: {amount, description, reason}
```

---

## 13. TopNavbar (global)

### Elementos
- 11 tabs de navegación con iconos y F-key labels
- Display "Le atiende: {usuario}" (lee `titan.user`)
- Botón Logout (icono LogOut, color rose)

### Logout Flow
1. Verifica `titan.pendingTickets` → warning si hay tickets
2. Verifica `titan.currentShift` → warning si hay turno abierto
3. Limpia: `titan.token`, `titan.user`, `titan.currentShift`, `titan.pendingTickets`, `titan.activeTickets`
4. Navega a `/login`

---

## Resumen de Endpoints Frontend → Backend

### Autenticación
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/auth/login` | Login |

### Sincronización (CRUD)
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/sync/products` | Terminal, Productos, Inventario |
| POST | `/api/v1/sync/products` | Productos |
| GET | `/api/v1/sync/customers` | Terminal, Clientes |
| POST | `/api/v1/sync/customers` | Clientes |
| GET | `/api/v1/sync/sales` | Historial (fallback) |

### Ventas
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/sales/` | Terminal (cobrar) |
| GET | `/api/v1/sales/search` | Historial, Reportes, Turnos |
| GET | `/api/v1/sales/{id}` | Historial (detalle) |

### Turnos
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/turns/open` | Turnos |
| POST | `/api/v1/turns/{id}/close` | Turnos |

### Inventario
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/inventory/adjust` | Inventario |

### Dashboard
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/dashboard/quick` | Estadísticas (30s refresh) |

### Mermas
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/mermas/pending` | Mermas |
| POST | `/api/v1/mermas/approve` | Mermas |

### Gastos
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/expenses/summary` | Gastos |
| POST | `/api/v1/expenses/` | Gastos |

### Sistema
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/remote/system-status` | Configuraciones |
| GET | `/api/v1/sync/status` | Configuraciones |

**Total**: 16 endpoints únicos (11 GET, 5 POST)

---

## localStorage Keys

| Key | Tipo | Usado por |
|-----|------|-----------|
| `titan.baseUrl` | string | Todos (config API) |
| `titan.token` | string | Todos (auth header) |
| `titan.terminalId` | string | Todos (X-Terminal-Id) |
| `titan.user` | string | TopNavbar (display) |
| `titan.currentShift` | JSON | Turnos, Terminal |
| `titan.shiftHistory` | JSON array | Turnos (max 100) |
| `titan.pendingTickets` | JSON array | Terminal (pausar tickets) |
| `titan.activeTickets` | JSON array | Terminal (multi-ticket) |
| `titan.configProfiles` | JSON array | Configuraciones (max 20) |

---

## Patrones Comunes

### Requests
- Timeout 3s con AbortController
- Headers: `Authorization: Bearer`, `X-Terminal-Id`, `Content-Type: application/json`
- 401 → clear token → redirect `/login`

### Responses
- Wrapper flexible: `{data: {...}}` o campos en raíz
- Error detail: string | array [{msg, loc}] | {error} | {message}
- Normalización de campos (sku/code/codigo, name/nombre, etc.)

### Estado
- `requestIdRef` para evitar race conditions (Stats, terminal)
- Datos cargados en mount, mantenidos en state local
- Paginación: 50 ítems/página con botones Anterior/Siguiente

### Validación
- Client-side: trim, number validation, required checks
- Todas las acciones destructivas requieren `confirm()` dialog
- Botones disabled durante loading
- Acumulación en centavos para evitar drift de flotantes (Reportes)

### Exports
- CSV generados client-side (downloadCsv helper)
- Impresión: `window.open()` con HTML table + `print()`
