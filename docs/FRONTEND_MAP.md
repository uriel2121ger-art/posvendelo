# TITAN POS — Mapa Completo del Frontend

> Actualizado: 2026-02-26
> Cubre: 16 vistas, ~70 endpoints, ~80 botones, ~60 campos, ~20 filtros

---

## Arquitectura General

- **Framework**: Electron + React (HashRouter)
- **Estilos**: Tailwind CSS (tema zinc oscuro)
- **Estado**: useState local + localStorage persistente
- **API**: `apiFetch()` centralizado en `posApi.ts` (~55 funciones)
- **Timeout**: 3s (AbortController) estándar, 15s (`apiFetchLong`) para fiscal/dashboard
- **RBAC**: `getUserRole()` lee `titan.role` (cashier|manager|owner|admin)
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
| — | `/empleados` | Empleados | `EmployeesTab.tsx` |
| — | `/remoto` | Control Remoto | `RemoteTab.tsx` |
| — | `/fiscal` | Fiscal (8 sub-tabs) | `FiscalTab.tsx` |

Navbar: `TopNavbar.tsx` — 14 tabs horizontales con iconos Lucide, usuario a la derecha.

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
→ Guarda titan.token, titan.user, titan.role en localStorage
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

### Extensiones (nuevo)
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Credito | getCustomerCredit() | `GET /api/v1/customers/{id}/credit` |
| Ventas | getCustomerSales() | `GET /api/v1/customers/{id}/sales` |

Panel expandible al seleccionar cliente: cards Limite/Balance/Disponible + mini-tabla historial ventas.

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

### Extensiones (nuevo)
| Elemento | Acción | Endpoint |
|----------|--------|----------|
| Dropdown categoría | Filtra por categoría | `GET /api/v1/products/categories/list` |
| Input SKU + Escanear | scanProduct() | `GET /api/v1/products/scan/{sku}` |
| Stock Bajo | getLowStockProducts() | `GET /api/v1/products/low-stock` |

Panel colapsable "Stock Bajo" con grid de productos bajo mínimo.

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

### Extensiones (nuevo)
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Ver Alertas Stock | getStockAlerts() | `GET /api/v1/inventory/alerts` |
| Historial Movimientos | getInventoryMovements() | `GET /api/v1/inventory/movements` |

Filtro movimientos: tipo (Todos/Entradas/Salidas) + botón Recargar.
Panel colapsable con tabla: Producto | Tipo | Cant | Razon | Fecha.

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

### Extensiones (nuevo)
| Botón | Acción | Endpoint |
|-------|--------|----------|
| Resumen Backend | getTurnSummary() | `GET /api/v1/turns/{id}/summary` |
| Registrar Mov. | createCashMovement() | `POST /api/v1/turns/{id}/movements` |

Form "Movimiento de Caja" (visible con turno abierto): Tipo (in/out/expense) | Monto | Razón | PIN manager (si no es manager+).
Panel "Resumen Backend" muestra JSON del summary del turno seleccionado.

### API
```
POST /api/v1/turns/open          Body: {initial_cash, branch_id:1, notes}
POST /api/v1/turns/{id}/close    Body: {final_cash, notes}  Resp: {expected_cash, difference}
GET  /api/v1/turns/{id}/summary  Resp: {sales_by_method, cash_in, cash_out, expected_cash}
POST /api/v1/turns/{id}/movements Body: {movement_type, amount, reason, manager_pin?}
GET  /api/v1/sales/search        Query: date_from, date_to, limit:2000  (reconciliación)
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

### Sub-tabs (nuevo)
Barra: `local | daily | ranking | heatmap`

| Sub-tab | Acción | Endpoint |
|---------|--------|----------|
| local | Contenido original (KPIs + top) | `GET /api/v1/sales/search` |
| daily | getDailySummaryReport() | `GET /api/v1/sales/reports/daily-summary` |
| ranking | getProductRanking() | `GET /api/v1/sales/reports/product-ranking` |
| heatmap | getHourlyHeatmap() | `GET /api/v1/sales/reports/hourly-heatmap` |

- **daily**: Tabla fecha/ventas/monto/ticket promedio
- **ranking**: Tabla producto/cantidad/ingreso
- **heatmap**: Grid 24 celdas (horas 0-23) con intensidad por color

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
- **Cancelar Venta** (manager+ only, double confirm) → `POST /api/v1/sales/{id}/cancel`
- **Tabla Eventos** (auto-cargada al seleccionar) → `GET /api/v1/sales/{id}/events`

### API
```
GET  /api/v1/sales/search       Query: folio, date_from, date_to, limit:200
GET  /api/v1/sales/{saleId}     ← Detalle individual
POST /api/v1/sales/{id}/cancel  ← Cancelar venta (manager+)
GET  /api/v1/sales/{id}/events  ← Eventos de la venta
GET  /api/v1/sync/sales         ← Fallback si detail falla (limit:2000)
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

### Paneles Avanzados (nuevo)
| Panel | Endpoint | Restricción |
|-------|----------|-------------|
| RESICO | `GET /api/v1/dashboard/resico` (15s) | — |
| Wealth | `GET /api/v1/dashboard/wealth` (15s) | manager+ |
| AI Insights | `GET /api/v1/dashboard/ai` (15s) | — |
| Executive | `GET /api/v1/dashboard/executive` (15s) | manager+ |

Cada panel tiene botón "Cargar" independiente con loading state propio.

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

## 13. Empleados (`/empleados`) — NUEVO

### Campos del Formulario
| Campo | Tipo | Placeholder | Validación |
|-------|------|-------------|------------|
| Código | text | "Código empleado" | required |
| Nombre | text | "Nombre" | required |
| Posición | text | "Posición" | required |
| Salario Base | number | "Salario base" | min:0 |
| Comisión % | number | "Comisión %" | min:0 |
| Teléfono | text | "Teléfono" | — |
| Email | text | "Email" | — |
| Notas | text | "Notas" | — |

### Botones
| Botón | Acción | Endpoint | RBAC |
|-------|--------|----------|------|
| Guardar/Actualizar | createEmployee/updateEmployee | `POST/PUT /api/v1/employees/` | manager+ |
| Cargar | listEmployees() | `GET /api/v1/employees/` | all |
| Nuevo | Limpia form | — | — |
| Eliminar | deleteEmployee() | `DELETE /api/v1/employees/{id}` | manager+ |

### Tabla
**Columnas**: Código | Nombre | Posición | Salario | Teléfono | Email
**Paginación**: 50 por página, búsqueda por nombre/código

---

## 14. Control Remoto (`/remoto`) — NUEVO

### Secciones
1. **Estado del Turno** — Card con `getTurnStatusRemote()` → `GET /api/v1/remote/turn-status`
2. **Ventas en Vivo** — Auto-refresh 10s con `getLiveSales(20)` → `GET /api/v1/remote/live-sales`
3. **Acciones Remotas:**
   - Botón "Abrir Cajón" + confirm → `POST /api/v1/remote/open-drawer`
   - Form "Cambiar Precio": sku + new_price + reason → `POST /api/v1/remote/change-price`
   - Form "Enviar Notificación": title + body + type → `POST /api/v1/remote/notification`
4. **Notificaciones Pendientes** — Tabla + recargar → `GET /api/v1/remote/notifications/pending`

---

## 15. Fiscal (`/fiscal`) — NUEVO (8 sub-tabs)

### Sub-tabs internos
Barra horizontal: `facturacion | inventario | logistica | federation | auditoria | wallet | crypto | seguridad`

### 15.1 Facturación
| Acción | Endpoint |
|--------|----------|
| Generar CFDI | `POST /api/v1/fiscal/generate` |
| CFDI Global | `POST /api/v1/fiscal/global/generate` |
| Procesar Devolución | `POST /api/v1/fiscal/returns/process` |
| Resumen Devoluciones | `GET /api/v1/fiscal/returns/summary` |
| Parse XML (upload) | `POST /api/v1/fiscal/xml/parse` (FormData) |

### 15.2 Inventario Fiscal
| Acción | Endpoint |
|--------|----------|
| Vista SAT | `GET /api/v1/fiscal/shadow/audit-view` |
| Vista Real | `GET /api/v1/fiscal/shadow/real-view` |
| Discrepancias | `GET /api/v1/fiscal/shadow/discrepancy` |
| Reconciliar | `POST /api/v1/fiscal/shadow/reconcile` |

### 15.3 Logística
| Acción | Endpoint |
|--------|----------|
| Crear Transferencia | `POST /api/v1/fiscal/ghost/transfer/create` |
| Recibir Transferencia | `POST /api/v1/fiscal/ghost/transfer/receive` |
| Pendientes | `GET /api/v1/fiscal/ghost/transfer/pending` |

### 15.4 Federation
| Acción | Endpoint |
|--------|----------|
| Dashboard Operacional | `GET /api/v1/fiscal/federation/operational` |
| Inteligencia Fiscal | `GET /api/v1/fiscal/federation/fiscal` |

### 15.5 Auditoría
| Acción | Endpoint |
|--------|----------|
| Ejecutar Auditoría | `POST /api/v1/fiscal/audit/run` |
| Ejecutar Shaper | `POST /api/v1/fiscal/shaper/run` |
| Análisis Proveedor | `POST /api/v1/fiscal/supplier/analyze` |

### 15.6 Wallet & Extracción
| Acción | Endpoint |
|--------|----------|
| Crear Wallet | `POST /api/v1/fiscal/wallet/create` |
| Agregar Puntos | `POST /api/v1/fiscal/wallet/add` |
| Redimir Puntos | `POST /api/v1/fiscal/wallet/redeem` |
| Stats Wallet | `GET /api/v1/fiscal/wallet/stats` |
| Extracción Disponible | `GET /api/v1/fiscal/extraction/available` |
| Plan Extracción | `POST /api/v1/fiscal/extraction/plan` |
| Extracción Óptima | `GET /api/v1/fiscal/extraction/optimal` |

### 15.7 Crypto
| Acción | Endpoint |
|--------|----------|
| Fondos Disponibles | `GET /api/v1/fiscal/crypto/available` |
| Convertir | `POST /api/v1/fiscal/crypto/convert` |
| Wealth Total | `GET /api/v1/fiscal/crypto/wealth` |

### 15.8 Seguridad
| Acción | Endpoint | RBAC |
|--------|----------|------|
| Verificar PIN | `POST /api/v1/fiscal/stealth/verify-pin` | all |
| Configurar PINs | `POST /api/v1/fiscal/stealth/configure-pins` | admin+ |
| Surgical Delete | `POST /api/v1/fiscal/stealth/surgical-delete` | admin+ (2x confirm) |
| Panic | `POST /api/v1/fiscal/evasion/panic` | admin+ (2x confirm) |
| Fake Screen | `POST /api/v1/fiscal/evasion/fake-screen` | admin+ |

Todos los endpoints fiscales usan `apiFetchLong` (15s timeout).

---

## 16. TopNavbar (global)

### Elementos
- 14 tabs de navegación con iconos Lucide (F1-F11 + 3 nuevos sin F-key)
- Display "Le atiende: {usuario}" (lee `titan.user`)
- Botón Logout (icono LogOut, color rose)

### Logout Flow
1. Verifica `titan.pendingTickets` → warning si hay tickets
2. Verifica `titan.currentShift` → warning si hay turno abierto
3. Limpia: `titan.token`, `titan.user`, `titan.role`, `titan.currentShift`, `titan.pendingTickets`, `titan.activeTickets`
4. Navega a `/login`

---

## Resumen de Endpoints Frontend → Backend (~70 endpoints)

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
| POST | `/api/v1/sales/{id}/cancel` | Historial (manager+) |
| GET | `/api/v1/sales/{id}/events` | Historial |
| GET | `/api/v1/sales/reports/daily-summary` | Reportes |
| GET | `/api/v1/sales/reports/product-ranking` | Reportes |
| GET | `/api/v1/sales/reports/hourly-heatmap` | Reportes |

### Turnos
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/turns/open` | Turnos |
| POST | `/api/v1/turns/{id}/close` | Turnos |
| GET | `/api/v1/turns/{id}/summary` | Turnos |
| POST | `/api/v1/turns/{id}/movements` | Turnos |

### Inventario
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/inventory/adjust` | Inventario |
| GET | `/api/v1/inventory/alerts` | Inventario |
| GET | `/api/v1/inventory/movements` | Inventario |

### Dashboard
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/dashboard/quick` | Estadísticas (30s refresh) |
| GET | `/api/v1/dashboard/resico` | Estadísticas (15s) |
| GET | `/api/v1/dashboard/wealth` | Estadísticas (15s, manager+) |
| GET | `/api/v1/dashboard/ai` | Estadísticas (15s) |
| GET | `/api/v1/dashboard/executive` | Estadísticas (15s, manager+) |

### Clientes Extendido
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/customers/{id}/credit` | Clientes |
| GET | `/api/v1/customers/{id}/sales` | Clientes |

### Productos Extendido
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/products/categories/list` | Productos |
| GET | `/api/v1/products/scan/{sku}` | Productos |
| GET | `/api/v1/products/low-stock` | Productos |
| POST | `/api/v1/products/stock` | RemoteTab |

### Empleados
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/employees/` | Empleados |
| POST | `/api/v1/employees/` | Empleados |
| PUT | `/api/v1/employees/{id}` | Empleados |
| DELETE | `/api/v1/employees/{id}` | Empleados |

### Remoto
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/remote/live-sales` | Remoto |
| GET | `/api/v1/remote/turn-status` | Remoto |
| POST | `/api/v1/remote/open-drawer` | Remoto |
| POST | `/api/v1/remote/change-price` | Remoto |
| POST | `/api/v1/remote/notification` | Remoto |
| GET | `/api/v1/remote/notifications/pending` | Remoto |

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

### Fiscal (~30 endpoints, todos 15s timeout)
| Método | Endpoint | Componente |
|--------|----------|------------|
| POST | `/api/v1/fiscal/generate` | Fiscal > Facturación |
| POST | `/api/v1/fiscal/global/generate` | Fiscal > Facturación |
| POST | `/api/v1/fiscal/returns/process` | Fiscal > Facturación |
| GET | `/api/v1/fiscal/returns/summary` | Fiscal > Facturación |
| POST | `/api/v1/fiscal/xml/parse` | Fiscal > Facturación |
| POST | `/api/v1/fiscal/audit/run` | Fiscal > Auditoría |
| POST | `/api/v1/fiscal/shaper/run` | Fiscal > Auditoría |
| POST | `/api/v1/fiscal/supplier/analyze` | Fiscal > Auditoría |
| GET | `/api/v1/fiscal/shadow/audit-view` | Fiscal > Inv. Fiscal |
| GET | `/api/v1/fiscal/shadow/real-view` | Fiscal > Inv. Fiscal |
| GET | `/api/v1/fiscal/shadow/discrepancy` | Fiscal > Inv. Fiscal |
| POST | `/api/v1/fiscal/shadow/reconcile` | Fiscal > Inv. Fiscal |
| POST | `/api/v1/fiscal/ghost/transfer/create` | Fiscal > Logística |
| POST | `/api/v1/fiscal/ghost/transfer/receive` | Fiscal > Logística |
| GET | `/api/v1/fiscal/ghost/transfer/pending` | Fiscal > Logística |
| GET | `/api/v1/fiscal/federation/operational` | Fiscal > Federation |
| GET | `/api/v1/fiscal/federation/fiscal` | Fiscal > Federation |
| POST | `/api/v1/fiscal/wallet/create` | Fiscal > Wallet |
| POST | `/api/v1/fiscal/wallet/add` | Fiscal > Wallet |
| POST | `/api/v1/fiscal/wallet/redeem` | Fiscal > Wallet |
| GET | `/api/v1/fiscal/wallet/stats` | Fiscal > Wallet |
| GET | `/api/v1/fiscal/extraction/available` | Fiscal > Wallet |
| POST | `/api/v1/fiscal/extraction/plan` | Fiscal > Wallet |
| GET | `/api/v1/fiscal/extraction/optimal` | Fiscal > Wallet |
| GET | `/api/v1/fiscal/crypto/available` | Fiscal > Crypto |
| POST | `/api/v1/fiscal/crypto/convert` | Fiscal > Crypto |
| GET | `/api/v1/fiscal/crypto/wealth` | Fiscal > Crypto |
| POST | `/api/v1/fiscal/stealth/verify-pin` | Fiscal > Seguridad |
| POST | `/api/v1/fiscal/stealth/configure-pins` | Fiscal > Seguridad |
| POST | `/api/v1/fiscal/stealth/surgical-delete` | Fiscal > Seguridad |
| POST | `/api/v1/fiscal/evasion/panic` | Fiscal > Seguridad |
| POST | `/api/v1/fiscal/evasion/fake-screen` | Fiscal > Seguridad |

### Sistema
| Método | Endpoint | Componente |
|--------|----------|------------|
| GET | `/api/v1/remote/system-status` | Configuraciones |
| GET | `/api/v1/sync/status` | Configuraciones |

**Total**: ~70 endpoints únicos (~35 GET, ~35 POST/PUT/DELETE)

---

## localStorage Keys

| Key | Tipo | Usado por |
|-----|------|-----------|
| `titan.baseUrl` | string | Todos (config API) |
| `titan.token` | string | Todos (auth header) |
| `titan.terminalId` | string | Todos (X-Terminal-Id) |
| `titan.user` | string | TopNavbar (display) |
| `titan.role` | string | RBAC (cashier/manager/owner/admin) |
| `titan.currentShift` | JSON | Turnos, Terminal |
| `titan.shiftHistory` | JSON array | Turnos (max 100) |
| `titan.pendingTickets` | JSON array | Terminal (pausar tickets) |
| `titan.activeTickets` | JSON array | Terminal (multi-ticket) |
| `titan.configProfiles` | JSON array | Configuraciones (max 20) |

---

## Patrones Comunes

### Requests
- `apiFetch()`: Timeout 3s con AbortController (endpoints estándar)
- `apiFetchLong()`: Timeout 15s (endpoints fiscal/dashboard)
- Headers: `Authorization: Bearer`, `X-Terminal-Id`, `Content-Type: application/json`
- 401 → clear token → redirect `/login`
- RBAC: `getUserRole()` lee `titan.role` para condicionar UI (manager+, admin+)

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
