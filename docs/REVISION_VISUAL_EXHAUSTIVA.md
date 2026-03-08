# Revisión visual exhaustiva — TITAN POS

Auditoría de cambios visuales/UI y estado de consistencia.

---

## Índice

1. [Referencia rápida](#referencia-rápida) — Patrón de tablas y elementos eliminados  
2. [Navegación](#navegación) — TopNavbar  
3. [Ventas](#ventas) — Terminal  
4. [Configuración](#configuración) — SettingsTab  
5. [Pestañas con tablas de datos](#pestañas-con-tablas-de-datos) — Productos, Inventario, Historial, Clientes, Mermas, Reportes, Remoto  
6. [Pestañas sin tablas](#pestañas-sin-tablas) — Turnos, Empleados, Gastos, Fiscal, Estadísticas  
7. [Resumen por archivo](#resumen-por-archivo)

---

## Referencia rápida

### Patrón canónico de tablas

Usado en todas las tablas de datos del POS:

| Parte | Clases |
|-------|--------|
| Contenedor | `rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden` |
| thead | `sticky top-0 bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold z-10` |
| th / td | `px-6 py-4` (preview: `px-4 py-3`) |
| tbody | `divide-y divide-zinc-800/50` |
| tr (datos) | `hover:bg-zinc-800/40 transition-colors` |
| table | `w-full text-left border-collapse` |

### Elementos eliminados

- **Terminal**: dropdown "Pendientes (N)" — sustituido por chips de tickets activos.
- **Modal cobro**: párrafo helper "Efectivo sin marcar → Serie B…" — eliminado.

---

## Navegación

**Archivo:** `TopNavbar.tsx`

| Revisión | Estado |
|----------|--------|
| Clientes en barra principal | OK — `PRIMARY_PATHS` incluye `/clientes` |
| Historial en barra principal | OK — `PRIMARY_PATHS` incluye `/historial` |
| Ajustes en barra principal | OK — `PRIMARY_PATHS` incluye `/configuraciones` |
| Conjunto visible | Terminal, Productos, Clientes, Inventario, Turnos, Historial, Reportes, Ajustes |

---

## Ventas

**Archivo:** `Terminal.tsx`

| Revisión | Estado |
|----------|--------|
| Alerta stock/catálogo | OK — texto corto, 3 variantes (stock, catálogo, ambos) |
| Checkbox factura | OK — "El cliente solicita factura para esta compra" |
| Sin helper Serie A/B | OK — eliminado |
| Sin dropdown Pendientes | OK — eliminado |
| Botón "Ticket pendiente" | OK — al guardar abre nuevo ticket (`openNewAfterPending` + `createNewActiveTicket`) |
| Método Mixto | OK — desglose Efectivo/Tarjeta/Transferencia, validación suma = total |
| Referencia pago | OK — campo para Tarjeta y Transferencia |
| Cards vacío | OK — `rounded-2xl border-zinc-800` |

---

## Configuración

**Archivo:** `SettingsTab.tsx`

| Revisión | Estado |
|----------|--------|
| TABS sidebar | OK — Conexión, Mi negocio, Impresora de tickets, Cajón, Lector de códigos |
| Subtítulo | OK — "Conecta tu caja con el servidor, configura impresora, cajón y datos de tu negocio." |
| Opciones avanzadas | OK — sección colapsable "Opciones para técnicos" |
| Régimen fiscal | OK — input con `datalist` (601, 603, 606, 612, …) |
| Vista previa ticket (Mi negocio) | OK — bloque con datos del negocio |
| Vista previa ticket (Impresora) | OK — según `paper_width` y modo fiscal/básico |
| Tabla impresoras | OK — card + thead canónico + divide-y + hover |

---

## Pestañas con tablas de datos

Todas usan el [patrón canónico](#patrón-canónico-de-tablas).

### Productos — `ProductsTab.tsx`

| Revisión | Estado |
|----------|--------|
| Helper lista | OK — "Clic en producto para editar o reponer. Si hay más de 50, usa la tabla y el filtro." |
| Tabla principal | OK |
| Panel stock bajo | OK — `rounded-2xl`, borde amber |
| Vista previa importación | OK — card + thead + celdas px-4 py-3 |

### Inventario — `InventoryTab.tsx`

| Revisión | Estado |
|----------|--------|
| Panel Alertas | OK — siempre visible al activar; mensaje si no hay alertas |
| Mensaje sin alertas | OK — "No hay productos con stock bajo en este momento." |
| Tipo movimiento | OK — "Entrada" / "Salida" (no IN/OUT) |
| Filtro dropdown | OK — valores IN/OUT; etiquetas "Solo entradas" / "Solo salidas" |
| Tabla Historial de movimientos | OK |
| Tabla Master List | OK |

### Historial — `HistoryTab.tsx`

| Revisión | Estado |
|----------|--------|
| Tabla principal ventas | OK |
| Drawer: Productos comprados | OK — tabla nombre, cant, subtotal |
| Drawer: Datos técnicos | OK — colapsable "Datos técnicos (JSON)", cerrado al abrir otra venta |
| Tabla Trazabilidad de Auditoría | OK — thead sticky + z-10 |

### Clientes — `CustomersTab.tsx`

| Revisión | Estado |
|----------|--------|
| Tabla principal | OK |
| Vista previa importación | OK |

### Mermas — `MermasTab.tsx`

| Revisión | Estado |
|----------|--------|
| Tabla mermas | OK |

### Reportes — `ReportsTab.tsx`

| Revisión | Estado |
|----------|--------|
| Tabla Top productos | OK |
| Tabla Resumen diario | OK |
| Tabla Ranking global | OK |

### Monitoreo remoto — `RemoteTab.tsx`

| Revisión | Estado |
|----------|--------|
| Tabla ventas en vivo | OK |

---

## Pestañas sin tablas

Cards con `rounded-2xl border border-zinc-800 bg-zinc-900/40`.

| Pestaña | Archivo | Revisión |
|---------|---------|----------|
| Turnos | `ShiftsTab.tsx` | Cards OK; tabla solo en popup de impresión (HTML, no React) |
| Empleados | `EmployeesTab.tsx` | Grid de cards, contenedor OK |
| Gastos | `ExpensesTab.tsx` | Cards resumen y formulario OK |
| Fiscal | `FiscalTab.tsx` + paneles | cardCls en todos los paneles |
| Estadísticas | `DashboardStatsTab.tsx` | Paneles OK |

---

## Resumen por archivo

| Archivo | Cambios principales |
|---------|---------------------|
| `TopNavbar.tsx` | PRIMARY_PATHS: clientes, historial, configuraciones en barra |
| `Terminal.tsx` | Alerta corta, factura, mixto, referencia, pendiente→nuevo ticket, sin dropdown/helper |
| `SettingsTab.tsx` | TABS, subtítulo, avanzado colapsable, régimen datalist, previews ticket, tabla impresoras |
| `ProductsTab.tsx` | Helper corto, tabla principal, panel stock bajo, vista previa import |
| `InventoryTab.tsx` | Alertas siempre visibles, Entrada/Salida, tablas canónicas |
| `HistoryTab.tsx` | Tabla principal, drawer productos + técnico colapsable, tablas canónicas |
| `CustomersTab.tsx` | Tabla principal, vista previa import |
| `MermasTab.tsx` | Tabla canónica |
| `ReportsTab.tsx` | 3 tablas canónicas |
| `RemoteTab.tsx` | Tabla canónica |
| `ShiftsTab.tsx`, `EmployeesTab.tsx`, `ExpensesTab.tsx`, `DashboardStatsTab.tsx`, `FiscalTab.tsx` | Cards consistentes |

---

*Última actualización: revisión exhaustiva post-cambios visuales.*
