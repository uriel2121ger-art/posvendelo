# Log de pruebas por pestaña (rama testing/autonomous-tab-validation)

Documento vivo: se actualiza en cada iteración. **Loop:** revisar una tab → terminarla (Estable) → pasar a la siguiente → repetir. Ver `docs/FLUJO_PRUEBAS_AUTONOMO.md`.

---

## Metadatos

| Campo | Valor |
|-------|--------|
| Rama | `testing/autonomous-tab-validation` |
| Última actualización | 2026-03-03 (Terminal + Productos) |

---

## Resumen por pestaña

| Tab | Estado | Última sesión | Notas |
|-----|--------|----------------|--------|
| Terminal | Estable | 2026-03-03 | Revisión código + tests; edge cases documentados |
| Productos | Estable | 2026-03-03 | Revisión código + backend tests; validación SKU/nombre/precio |
| Clientes | Pendiente | — | |
| Turnos | Pendiente | — | |
| Inventario | Pendiente | — | |
| Reportes | Pendiente | — | |
| Historial | Pendiente | — | |
| Configuraciones | Pendiente | — | |
| Estadísticas | Pendiente | — | |
| Mermas | Pendiente | — | |
| Empleados | Pendiente | — | |
| Remoto | Pendiente | — | |
| Fiscal | Pendiente | — | |

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
