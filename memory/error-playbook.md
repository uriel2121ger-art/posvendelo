# Error Playbook — POSVENDELO

Errores y bugs encontrados en auditorías, con causa raíz, solución y lección. Consultar antes de investigar un error nuevo.

Formato por entrada: ID, Síntoma, Causa raíz, Solución, Resultado, Lección.

---

## ERR-001 — Respuesta JSON con float para montos en resumen de turno remoto

- **Síntoma:** El endpoint remoto de estado de turno (`/turn-status` o equivalente) devolvía `0.0` (float) para `cash_sales`, `card_sales`, `transfer_sales`, `total_sales` cuando no había resumen, en lugar de string decimal.
- **Causa raíz:** En `backend/modules/remote/routes.py` se usaba `0.0` como fallback cuando `summary` era falsy. El contrato del proyecto exige que los montos en JSON sean `money()` (string) o Decimal en lógica; nunca float en respuestas API.
- **Solución:** Sustituir `0.0` por `money(Decimal("0"))` en las cuatro claves del payload de respuesta (cash_sales, card_sales, transfer_sales, total_sales). El módulo ya importaba `Decimal` y `money`.
- **Resultado:** Las respuestas de resumen de turno remoto devuelven siempre string decimal para montos (p. ej. `"0.00"`), consistente con el resto de la API.
- **Lección:** En respuestas API, montos deben ser `money(Decimal(...))` o `"0.00"`; no usar `0.0` (float). Regla: dinero en JSON como string; en aritmética usar `dec()`.

---

## ERR-002 — Emoji en UI (modal “Operación exitosa” movimiento de caja)

- **Síntoma:** En el modal de éxito de entrada/retiro de efectivo (movimiento de caja) se mostraba el carácter Unicode ✅ (`&#9989;`). La convención del proyecto es no usar emojis en la UI.
- **Causa raíz:** En `frontend/src/renderer/src/App.tsx` (CashMovementModal) se usaba `<div className="text-5xl mb-4">&#9989;</div>` para el ícono de éxito.
- **Solución:** Importar `Check` de `lucide-react` y reemplazar el div con el emoji por `<Check className="h-14 w-14 text-emerald-400" strokeWidth={2.5} aria-hidden />` dentro de un contenedor flex centrado, manteniendo el mismo mensaje “Operación exitosa”.
- **Resultado:** El modal muestra un ícono de check de Lucide en lugar del emoji; se cumple la convención “sin emojis en UI”.
- **Lección:** No usar emojis ni caracteres Unicode decorativos en la UI; usar íconos de la librería del proyecto (Lucide React).

---

---

## ERR-003 — Instalación nueva: evitar ejecutar 48 migraciones (pre-producción)

- **Síntoma:** En una DB vacía, el entrypoint aplica `schema.sql` (esquema completo) y luego `migrate.py` ejecuta los 48 archivos de migración uno a uno; es redundante y más lento.
- **Causa raíz:** No se marcaban como aplicadas las versiones 1..N en `schema_version` tras aplicar `schema.sql`, por lo que `migrate.py` consideraba todas pendientes.
- **Solución:** En `backend/entrypoint.sh`, justo después de aplicar `schema.sql` en una DB recién detectada como vacía, ejecutar un script que obtiene el máximo número de migración existente en `migrations/*.sql` e inserta en `schema_version` las versiones 1..N con `ON CONFLICT (version) DO NOTHING`. Así `migrate.py` no tiene nada pendiente en instalación nueva.
- **Resultado:** Instalación nueva = una sola aplicación de `schema.sql` + inserción de versiones 1..N; `migrate.py` termina en segundos sin ejecutar 48 archivos. Las migraciones futuras (049, 050, …) se aplican solo cuando se añadan.
- **Lección:** Antes de producción se puede consolidar el “todo de una vez” para DB nueva usando el schema completo y marcando las migraciones actuales como aplicadas; no hace falta borrar ni archivar los archivos de migración.

---

*Última actualización: 2026-03-13. Entradas derivadas de auditoría backend, frontend y correcciones aplicadas.*
