# Flujo de pruebas autónomo por pestaña (POSVENDELO)

**Rama de trabajo:** `testing/autonomous-tab-validation`  
**Objetivo:** No tocar `master` hasta que se valide y decida merge. Todo el trabajo (pruebas, documentación, correcciones, nuevos tests) se hace en esta rama.

**Loop:** Revisar una tab → terminarla (Estable) → pasar a la siguiente → repetir. Al acabar la última (Fiscal), volver a la primera (Terminal) o cerrar la ronda.

```
  Terminal → Productos → Clientes → Turnos → … → Fiscal → (vuelta a Terminal)
       ↑_________________________________________________________|
```

---

## 1. Loop de trabajo (una pestaña a la vez, en orden)

El flujo es un **bucle continuo**: se revisa una pestaña, se termina (se deja Estable), se pasa a la siguiente, y así sucesivamente. Cuando se acaban todas, se puede volver a la primera y repetir el ciclo.

**En cada vuelta del loop:**

1. **Tomar la siguiente pestaña** en el orden de la sección 2 (si la anterior quedó Estable, pasar a la siguiente; si es la primera vez o se reinició el ciclo, empezar por la 1).
2. **Trabajar solo en esa pestaña** hasta dejarla Estable:
   - Probar flujos principales (casos felices).
   - Edge cases (límites, vacíos, textos largos, caracteres raros, permisos).
   - Monkey / chaos (entradas inesperadas, errores de red si aplica).
   - Documentar en `docs/testing/LOG_PRUEBAS_TABS.md`: hallazgos, bugs, correcciones, tests nuevos.
   - Corregir bugs y añadir o ampliar pruebas (unitarias, integración, E2E).
3. **Marcar la pestaña como Estable** en el LOG y **pasar a la siguiente** pestaña del orden.
4. **Repetir** desde el paso 1 con la nueva pestaña. Al terminar la pestaña 13 (Fiscal), volver a la 1 (Terminal) para el siguiente ciclo, o dar por cerrada la ronda según convenga.

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
- **Actualizar** `docs/testing/LOG_PRUEBAS_TABS.md` en la misma iteración en que se ejecutan pruebas o se corrigen bugs.
- **Releer** este flujo y el LOG antes de cada nueva ronda de pruebas para mantener coherencia.
- Si se encuentra un bug crítico que ya existe en `master`, documentarlo en el LOG; la corrección puede ir en esta rama y luego llevarse a `master` por separado si se desea.
