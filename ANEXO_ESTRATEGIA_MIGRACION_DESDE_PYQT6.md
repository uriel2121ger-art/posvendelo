# Anexo — Estrategia para migrar desde PyQt6 (sin ejecutar aún)

Documento de evaluación para reemplazar PyQt6 por una opción menos problemática en mantenimiento/despliegue.

## 1) Contexto real del sistema

- App POS de escritorio en Python con módulos grandes de UI (`sales_tab`, `settings_tab`, `import_wizard`).
- Integración fuerte con servicios locales (ventas, fiscal, sync, impresión, hardware).
- Operación en sucursales con un equipo servidor y varios clientes.

## 2) Alternativas viables (resumen)

| Opción | Pros | Contras | Encaje con tu caso |
|---|---|---|---|
| `PySide6` (Qt oficial LGPL) | Muy similar a PyQt6, migración más corta, ecosistema Qt completo | Sigue siendo Qt (peso/runtime similar) | **Mejor transición de bajo riesgo** |
| `Tauri + frontend web (React/Vue/Svelte)` | App liviana, UX moderna, mejor separación front/back | Reescritura grande, curva de aprendizaje, puente Python-Rust/API | Bueno a largo plazo, alto costo inicial |
| `Electron + frontend web` | Ecosistema maduro, velocidad de UI web | Consumo de RAM alto, empaquetado pesado | Útil si priorizas web skills, no ideal para equipos modestos |
| `Tkinter/CustomTkinter` | Simple y estándar | Limitado para UI compleja POS | No recomendado para tu complejidad actual |
| `Flet` | Rápido para prototipos, Python-first | Menor madurez para POS complejos offline/hardware | Riesgo medio-alto |

## 3) Recomendación práctica por fases

### Fase A (rápida y conservadora): PyQt6 -> PySide6

- Objetivo: reducir fricción de licenciamiento/tooling sin reescribir todo.
- Esfuerzo estimado: 2-5 semanas (según deuda UI).
- Riesgo: Medio-bajo.
- Beneficio: continuidad operacional con menor impacto.

### Fase B (evolutiva): UI web shell (Tauri) en paralelo

- Objetivo: modernizar UX y desacoplar UI de lógica.
- Esfuerzo: 8-16+ semanas por módulos.
- Riesgo: Medio-alto.
- Beneficio: arquitectura más sostenible a futuro.

## 4) Plan técnico de migración a PySide6 (recomendado)

1. Crear rama de migración y fuente canónica única.
2. Cambiar imports principales:
   - `from PyQt6 import QtCore, QtGui, QtWidgets`
   - a `from PySide6 import QtCore, QtGui, QtWidgets`
3. Ajustar diferencias API Qt6 puntuales (signals/slots, enums, métodos de diálogos).
4. Validar módulos críticos en este orden:
   - `app/entry.py`, `app/core.py`
   - `app/ui/sales_tab.py`
   - `app/ui/settings_tab.py`
   - `app/wizards/import_wizard.py`
5. Ejecutar pruebas de caja: venta, impresión ticket, sync, facturación.
6. Piloto en 1 sucursal antes de rollout.

## 5) Checklist de decisión (Go/No-Go de migración)

### Go
- 100% de flujos críticos funcionando en piloto.
- Sin degradación de rendimiento perceptible.
- Sin incidentes P1 por 7 días.

### No-Go
- Falla en timbrado/sync/impresión.
- Inestabilidad de UI en caja.
- Aumento de latencia en operación de venta.

## 6) Riesgos principales y mitigación

- **Riesgo:** romper flujo de caja por cambios UI.
  - **Mitigación:** feature flags + piloto controlado + rollback.
- **Riesgo:** incompatibilidades Qt/Python en entorno de sucursal.
  - **Mitigación:** matriz de compatibilidad por SO y paquete reproducible.
- **Riesgo:** doble mantenimiento frontend/backend.
  - **Mitigación:** unificar fuente antes de migrar UI.

## 7) Estimación ejecutiva

- Camino recomendado ahora: **PySide6** (menor riesgo, menor costo).
- Camino estratégico 2026+: evaluar **Tauri + frontend web** por etapas.
