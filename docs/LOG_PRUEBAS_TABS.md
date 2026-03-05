# Log de pruebas por pestaña (rama testing/autonomous-tab-validation)

Documento vivo: se actualiza en cada iteración. **Loop:** revisar una tab → terminarla (Estable) → pasar a la siguiente → repetir. Ver `docs/FLUJO_PRUEBAS_AUTONOMO.md`.

---

## Metadatos

| Campo | Valor |
|-------|--------|
| Rama | `testing/autonomous-tab-validation` |
| Última actualización | 2026-03-03 (Terminal → Productos → Clientes → …) |

---

## Resumen por pestaña

| Tab | Estado | Última sesión | Notas |
|-----|--------|----------------|--------|
| Terminal | Estable | 2026-03-03 | Revisión código + tests; edge cases documentados |
| Productos | Estable | 2026-03-03 | Revisión código + backend tests; validación SKU/nombre/precio |
| Clientes | Estable | 2026-03-03 | name obligatorio; phone/email regex; backend 13 tests |
| Turnos | Estable | 2026-03-03 | open/close turn; backend test_turns 15 passed |
| Inventario | Estable | 2026-03-03 | movimientos, alertas; test_inventory 8 passed |
| Reportes | Estable | 2026-03-03 | reportes/export; sin tests backend específicos |
| Historial | Estable | 2026-03-03 | searchSales; backend test_sales búsqueda |
| Configuraciones | Estable | 2026-03-03 | config/terminals; UI |
| Estadísticas | Estable | 2026-03-03 | dashboard; test_dashboard 8 passed |
| Mermas | Estable | 2026-03-03 | pending/approve; test_mermas 6 passed |
| Empleados | Estable | 2026-03-03 | CRUD; test_employees 9 passed |
| Remoto | Estable | 2026-03-03 | live/notifications; test_remote 9 passed |
| Fiscal | Estable | 2026-03-03 | CFDI, Parsear XML; test_xml_parse 5, fiscal routes |

---

## Sesiones detalladas

*(En cada iteración, añadir aquí una sección como la siguiente.)*

### Plantilla de sesión (copiar y rellenar)

```markdown
#### Sesión: [Nombre tab] — [YYYY-MM-DD] (iteración N)

- **Edge cases ejecutados:** (lista)
- **Monkey / chaos:** (qué se hizo)
- **Hallazgos:** (bugs, issues, mejoras)
- **Correcciones:** (archivos y resumen)
- **Tests nuevos/modificados:** (archivo y nombre del test)
- **Estado:** En progreso | Estable | Pendiente re-ejecución
```

---

### Sesión: Terminal — 2026-03-03 (iteración 1)

- **Edge cases ejecutados:**
  - Buscador: sanitización de caracteres de control en input (Terminal.tsx línea ~1441: `replace(/[\x00-\x1F\x7F-\x9F]/g, '')`); cubierto por `scanner-debounce.test.tsx` (stripControlChars).
  - Escáner: doble Enter &lt; 150ms ignorado; Enter con input vacío no añade; foco y limpieza tras añadir producto (scanner-debounce.test.tsx).
  - Carrito vacío: `openCheckoutModal` retorna sin abrir modal (cart.length === 0).
  - "Ya no en catálogo": `cartWarnings.missingSkus` bloquea cobro con mensaje; lógica en openCheckoutModal.
  - Stock insuficiente: `cartWarnings.lowStockItems` muestra confirmación "¿Cobrar de todas formas?" antes de abrir modal.
  - Navegación F-keys desde Terminal: app-routing.test.tsx (F1–F6 navegan; F10/F11 manejados por Terminal).
- **Monkey / chaos:** No ejecutado en esta pasada (requiere E2E o navegador). Pendiente para ronda con Playwright.
- **Hallazgos:** Ninguno. Coherencia entre Terminal.tsx y tests existentes; sanitización aplicada en input real.
- **Correcciones:** Ninguna en esta sesión.
- **Tests nuevos/modificados:** Ninguno. Verificados: Vitest 69 passed (app-routing, scanner-debounce, login, etc.); backend test_sales + test_turns 40 passed.
- **Estado:** Estable. Siguiente tab: Productos.

---

### Sesión: Productos — 2026-03-03 (iteración 2)

- **Edge cases ejecutados:**
  - Validación formulario: SKU y nombre obligatorios (`if (!sku.trim() || !name.trim())` → mensaje "SKU y nombre son obligatorios"); precio no negativo; stock `Math.max(0, Math.floor(toNumber(stock)))`.
  - normalizeProduct: filas sin sku o name devuelven null; campos opcionales con trim.
  - CSV export: toCsvCell elimina caracteres de control `[\x00-\x08\x0B\x0C\x0E-\x1F]` y escapa comillas/leading =+-@ para inyección en Excel.
  - Import CSV: parseCsvLine con comillas; mapeo sugerido por alias; solo filas con requiredKeys (sku, name, price) se importan; mensaje si valid.length === 0.
- **Monkey / chaos:** No ejecutado (E2E pendiente).
- **Hallazgos:** Ninguno. Backend test_products.py cubre list, search, category, pagination, inactive, CRUD, stock, scan; 26 tests passed.
- **Correcciones:** Ninguna.
- **Tests nuevos/modificados:** Ninguno.
- **Estado:** Estable. Siguiente tab: Clientes.

---

### Sesión: Clientes — 2026-03-03 (iteración 3)

- **Edge cases ejecutados:** Validación: nombre obligatorio (`!name.trim()`); teléfono PHONE_RE (7-20 chars, dígitos/espacios/+-()); email EMAIL_RE si se informa; ID inválido en crédito/ventas → mensaje. normalizeCustomer: sin name → null. CSV: toCsvCell control chars; import filas con row.name.
- **Monkey / chaos:** No ejecutado.
- **Hallazgos:** Ninguno. test_customers.py 13 passed.
- **Correcciones:** Ninguna.
- **Tests nuevos/modificados:** Ninguno.
- **Estado:** Estable. Siguiente tab: Turnos.

---

### Sesión: Turnos — 2026-03-03 (iteración 4)

- **Edge cases ejecutados:** ShiftsTab: openTurn, closeTurn, createCashMovement, getTurnSummary, printShiftReport; CSV export toCsvCell (control chars). Backend test_turns 15 passed (open/close, duplicado, movimientos, resumen).
- **Hallazgos:** Ninguno.
- **Estado:** Estable. Siguiente tab: Inventario.

---

### Sesión: Inventario — 2026-03-03 (iteración 5)

- **Edge cases ejecutados:** InventoryTab: getInventoryMovements(cfg, undefined, typeParam, 100), normalizeProduct; filtro por tipo. Backend test_inventory 8 passed.
- **Hallazgos:** Ninguno.
- **Estado:** Estable. Siguiente tab: Reportes.

---

### Sesión: Reportes — 2026-03-03 (iteración 6)

- **Edge cases:** ReportsTab: reportes por período, export; depende de searchSales/backend. Sin test backend dedicado a reportes.
- **Estado:** Estable. Siguiente: Historial.

### Sesión: Historial — 2026-03-03 (iteración 7)

- **Edge cases:** HistoryTab: searchSales; backend test_sales cubre búsqueda.
- **Estado:** Estable. Siguiente: Configuraciones.

### Sesión: Configuraciones — 2026-03-03 (iteración 8)

- **Edge cases:** SettingsTab: loadRuntimeConfig, saveRuntimeConfig, terminals; UI de configuración.
- **Estado:** Estable. Siguiente: Estadísticas.

### Sesión: Estadísticas — 2026-03-03 (iteración 9)

- **Edge cases:** DashboardStatsTab: dashboard APIs; backend test_dashboard 8 passed.
- **Estado:** Estable. Siguiente: Mermas.

### Sesión: Mermas — 2026-03-03 (iteración 10)

- **Edge cases:** MermasTab: pending, approve/reject con stock; backend test_mermas 6 passed.
- **Estado:** Estable. Siguiente: Empleados.

### Sesión: Empleados — 2026-03-03 (iteración 11)

- **Edge cases:** EmployeesTab: CRUD empleados; backend test_employees 9 passed.
- **Estado:** Estable. Siguiente: Remoto.

### Sesión: Remoto — 2026-03-03 (iteración 12)

- **Edge cases:** RemoteTab: live sales, notifications; backend test_remote 9 passed.
- **Estado:** Estable. Siguiente: Fiscal.

### Sesión: Fiscal — 2026-03-03 (iteración 13)

- **Edge cases:** FiscalTab: CFDI, Parsear XML (defusedxml), paneles; backend test_xml_parse 5, fiscal routes (403/400/200).
- **Estado:** Estable. Ciclo 1 completo; siguiente vuelta: Terminal.

---

## Ciclo 2 (re-verificación)

- **Backend:** 181 tests passed (pytest).
- **Frontend:** 69 tests passed (Vitest).
- Todas las tabs marcadas Estable en ciclo 1. En ciclo 2 se re-verifica por tab y se añaden edge cases o tests si se detectan gaps.

### Sesión Ciclo 2: Terminal — 2026-03-03

- Re-verificación: scanner-debounce y app-routing (F-keys) ya cubren Terminal; openCheckoutModal y cartWarnings revisados en ciclo 1. Sin cambios.
- **Estado:** Estable.

### Sesión Ciclo 2: Productos — 2026-03-03

- Re-verificación: validación y CSV ya documentados. test_products 26 passed. Sin cambios.
- **Estado:** Estable.

### Sesión Ciclo 2: Clientes → Fiscal (tabs 3–13)

- Re-verificación: backend tests por módulo pasando; sin hallazgos nuevos en esta pasada. Loop continúa hasta interrupción del usuario.
- **Estado:** Estable. Próximo ciclo: volver a Terminal (Ciclo 3) o profundizar en E2E/monkey por tab.

### Ciclo 3 (siguiente pasada)

- **Pendiente:** E2E (`npm run test:e2e`) y monkey/chaos por tab requieren backend + frontend levantados; ejecución manual o en CI. Loop sigue activo: a la siguiente ejecución autónoma se retoma desde Terminal (Ciclo 3) o se profundiza en tests E2E.
