# Flujo de pruebas autónomo por pestaña (TITAN POS)

**Rama de trabajo:** `testing/autonomous-tab-validation`  
**Objetivo:** No tocar `master` hasta que se valide y decida merge. Todo el trabajo (pruebas, documentación, correcciones, nuevos tests) se hace en esta rama.

---

## 1. Ciclo de trabajo (repetir de forma autónoma)

Cada iteración sigue este flujo:

1. **Elegir una pestaña** según el orden en la sección 2.
2. **Probar la pestaña al completo:**
   - Casos felices (flujos principales).
   - Edge cases (valores límite, vacíos, largos, caracteres especiales, permisos).
   - Monkey / chaos (entradas aleatorias o inesperadas, errores de red simulados si aplica).
3. **Escribir y actualizar documentación:**
   - En `docs/LOG_PRUEBAS_TABS.md`: anotar qué se probó, hallazgos, bugs, issues.
   - Actualizar el mismo documento con correcciones aplicadas y nuevos tests añadidos.
4. **Corregir bugs e issues** encontrados (en esta rama).
5. **Añadir o ampliar pruebas** (unitarias, integración o E2E) según los edge cases y monkeys.
6. **Releer** `docs/LOG_PRUEBAS_TABS.md` y `docs/FLUJO_PRUEBAS_AUTONOMO.md` para la siguiente iteración.
7. **Repetir** con la misma pestaña hasta dejarla estable o pasar a la siguiente según la prioridad.

---

## 2. Orden sugerido de pestañas

| Orden | Ruta       | Componente   | Notas |
|-------|------------|--------------|--------|
| 1     | Terminal   | Terminal     | POS principal, cobro, pendientes, F-keys |
| 2     | Productos  | ProductsTab  | CRUD, búsqueda, stock, categorías |
| 3     | Clientes   | CustomersTab | CRUD, crédito, historial |
| 4     | Turnos     | ShiftsTab    | Apertura/cierre, movimientos |
| 5     | Inventario | InventoryTab | Movimientos, alertas, ajustes |
| 6     | Reportes   | ReportsTab   | Reportes y exportaciones |
| 7     | Historial  | HistoryTab   | Búsqueda ventas |
| 8     | Configuraciones | SettingsTab | Parámetros |
| 9     | Estadísticas | DashboardStatsTab | KPIs |
| 10    | Mermas     | MermasTab    | Pérdidas, aprobaciones |
| 11    | Empleados  | EmployeesTab | CRUD empleados |
| 12    | Remoto     | RemoteTab    | PWA, notificaciones |
| 13    | Fiscal     | FiscalTab    | CFDI, Parsear XML, paneles fiscal |

---

## 3. Qué documentar en cada iteración (LOG_PRUEBAS_TABS.md)

Para cada pestaña o sesión, registrar:

- **Tab y fecha/sesión**
- **Edge cases ejecutados** (lista breve)
- **Monkey / chaos** (qué se hizo: inputs raros, errores simulados, etc.)
- **Hallazgos:** bugs, comportamientos incorrectos, mejoras
- **Correcciones:** archivos tocados, resumen del fix
- **Tests nuevos o modificados:** archivo y nombre del test
- **Estado:** En progreso / Estable / Pendiente de re-ejecución

---

## 4. Comandos útiles

```bash
# Asegurarse de estar en la rama
git checkout testing/autonomous-tab-validation

# Backend (para pruebas manuales o E2E)
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Tests backend
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/ -v

# Frontend (Vitest)
cd frontend && npx vitest run

# E2E (Playwright; backend y frontend deben estar levantados)
cd frontend && npm run test:e2e
```

---

## 5. Reglas para ejecución autónoma

- **Siempre trabajar en la rama** `testing/autonomous-tab-validation`. No hacer merge a `master` sin aprobación explícita.
- **Actualizar** `docs/LOG_PRUEBAS_TABS.md` en la misma iteración en que se ejecutan pruebas o se corrigen bugs.
- **Releer** este flujo y el LOG antes de cada nueva ronda de pruebas para mantener coherencia.
- Si se encuentra un bug crítico que ya existe en `master`, documentarlo en el LOG; la corrección puede ir en esta rama y luego llevarse a `master` por separado si se desea.
