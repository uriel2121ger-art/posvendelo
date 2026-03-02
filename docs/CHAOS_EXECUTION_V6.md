# Chaos Engineering — Ejecución V6 (PLAN_TESTING_V6.md)

Documento de ejecución y resultado de las fases Chaos 1–9 del Plan de Testing V6.

---

## Resumen por fase

| Fase | Descripción | Ejecutable automático | Resultado / Notas |
|------|-------------|------------------------|-------------------|
| **1** | Chronobiología / time travel | No (requiere cambiar hora SO) | Manual: cambiar fecha/hora del SO; login, vender, cobrar; verificar timestamps. |
| **2** | Throttling 2G / payload fragmentado | Parcial | 2.2: FastAPI rechaza JSON inválido (422). 2.1: manual con DevTools Network throttling. |
| **3** | Corrupción almacenamiento (NaN/undefined, impresión) | Parcial | 3.1: manual (editar localStorage). 3.2: manual (interceptar impresora). |
| **4** | Volumetría (15k líneas ticket, 200k ventas) | Script/seed posible | No ejecutado; requiere seed de datos y/o virtualización en frontend. |
| **5** | Split brain (retiros cruzados, deslogueo fantasma) | Tests de concurrencia | Cubierto por tests de turnos (close duplicate, ownership). 5.2: manual dos clientes. |
| **6** | Hardware hot-swap (impresora desconectada) | No | Manual: desconectar impresora durante impresión; verificar que worker no bloquea UI. |
| **7** | Event flooding (F10/F11/Escape/Enter mismo frame) | Test unitario posible | Cubierto por tests F-keys en app-routing; no superposición de modales. |
| **8** | Unicode Zalgo/RTL en nombres | Backend 422 / frontend | Backend valida UTF-8 y longitud; tests de creación con nombres edge pueden añadirse. |
| **9** | Límites numéricos (BigInt / 9e9) | Backend 422/400 | Backend con Decimal/validación; cantidad o cambio excesivo → rechazo. |

---

## Detalle por fase

### FASE 1: Chronobiología y time travel

- **1.1 Desfase de zona horaria:** Ejecución manual. Pasos: cambiar fecha/hora del SO (ej. diciembre 2023); login, vender, cobrar; comprobar que backend asigna día correctamente o detecta anomalías.
- **1.2 Turnos vampiro (medianoche/DST):** Ejecución manual. Abrir turno 23:55, vender 23:59, cambiar hora a 00:05, vender de nuevo, cerrar; corte de caja debe unificar sin crashear.

**Estado:** No ejecutado en esta sesión (requiere manipulación de reloj del sistema).

---

### FASE 2: Limitaciones físicas y throttling

- **2.1 Red 2G simulada:** DevTools → Network → Throttling 20 kbps + 15 s latencia; 5 checkouts seguidos. Objetivo: sin colapso React, sin duplicar peticiones, botón deshabilitado o spinner.
- **2.2 Payload fragmentado:** Enviar JSON de venta con bytes corrompidos. **Verificación:** FastAPI devuelve 422 por deserialización; no se inserta producto vacío. (Cubierto por validación Pydantic.)

**Estado:** 2.2 cubierto por comportamiento estándar de la API. 2.1 manual.

---

### FASE 3: Corrupción de almacenamiento

- **3.1 NaN/Undefined en estado:** Sustituir en localStorage valores (descuentos, tax, ID) por `NaN` o `undefined`; recargar. Objetivo: app no crashea o muestra Error Boundary recuperable.
- **3.2 Secuestro de impresión:** Interceptar llamada a impresora e inyectar bucle infinito. Objetivo: UI principal no bloqueada; worker aísla fallo.

**Estado:** Manual; no ejecutado en esta sesión.

---

### FASE 4: Volumetría y memoria

- **4.1 Ticket 15 000 líneas:** Requiere seed o generación de ticket con 15k líneas; verificar virtualización o límite en frontend/backend.
- **4.2 Historial 200 000 ventas:** Seed de 200k ventas; abrir Historial; verificar que request usa `limit`/`offset` y no carga todo en RAM.

**Estado:** No ejecutado; requiere datos de volumen.

---

### FASE 5: Estrés dual (split brain)

- **5.1 Retiros y cobros cruzados:** PC1 vende; PC2 retira el total en el mismo instante. Validación atómica debe evitar balance negativo. (Tests de turnos cubren cierre y movimientos.)
- **5.2 Deslogueo fantasma:** Cerrar turno en PC1; en PC2 intentar facturar ticket ya armado. Objetivo: error graceful; no limbo de sesión.

**Estado:** 5.1/5.2 parcialmente cubiertos por lógica de turnos y permisos; escenario multi-PC manual.

---

### FASE 6: Hardware hot-swap

- **6.1 Impresora desconectada al imprimir:** Tras 200 OK de venta, desconectar driver de impresión. Objetivo: worker no crashea el thread principal; reintento o spooler al reconectar.

**Estado:** Manual.

---

### FASE 7: Trampas modales y event flooding

- **7.1 Macro F10/F11/Escape/Enter mismo frame:** Evitar modales superpuestos; al cerrar “Cobro”, fondo y foco correctos. Tests de F-keys en `app-routing.test.tsx` cubren que F7/F8/F9 abren modales y que F10/F11 no cambian ruta.

**Estado:** Cubierto por tests de navegación y teclas; no hay test explícito de “mismo frame”.

---

### FASE 8: Corrupción Unicode (Zalgo, RTL)

- **8.1 Zalgo y RTL en nombre:** Cliente o producto con nombre Zalgo + RTL. Objetivo: CSS/layout no rotos; backend valida UTF-8 y longitud. Schemas Pydantic con `max_length` y encoding UTF-8 cubren rechazo de valores inválidos o excesivos.

**Estado:** Cubierto por validación backend; test explícito opcional.

---

### FASE 9: Límites numéricos (64 bits / BigInt)

- **9.1 Millonarios pícaros:** Cantidad 9 999 999 999 y cambio 999 999 999 999. Backend debe rechazar “Out of Range”; no notación científica en flujo de caja. Schemas con `Decimal` y `ge`/`le` limitan rangos.

**Estado:** Cubierto por validación de esquemas; test explícito de límite opcional.

---

## Tests automatizados relacionados

- **Turnos:** `test_open_turn_duplicate`, `test_close_turn_already_closed`, `test_cash_movement_*` (evitar estado inconsistente).
- **Seguridad:** `test_price_forgery_blocked` (no confiar en datos cliente).
- **Productos:** `test_create_product_validation` (sku/name/price), `test_scan_sku_not_found`.
- **Gastos:** `test_register_expense_invalid_amount_rejected`, `test_register_expense_empty_description_rejected`.
- **Frontend:** F-keys y modales en `app-routing.test.tsx`; sanitización escáner en `scanner-debounce.test.tsx`.

---

## Conclusión

Las fases Chaos que dependen de **validación de API o lógica de negocio** quedan cubiertas por la suite actual (pytest + Vitest). Las que requieren **manipulación de entorno** (hora del sistema, red, hardware, almacenamiento corrupto, datos masivos) quedan documentadas para ejecución manual o en entorno controlado.

*Documento generado como parte del Plan de Testing V6. Actualizar tras ejecutar pruebas manuales de Chaos.*
