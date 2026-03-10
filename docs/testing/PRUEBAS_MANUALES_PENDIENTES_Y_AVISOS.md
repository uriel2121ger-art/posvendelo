# Pruebas manuales: Pendientes entre sesiones y avisos (precio/stock/catálogo)

Objetivo: ver en el navegador que los tickets pendientes se comportan bien cuando hay cambios de precios, stock o productos dados de baja, y que los avisos y bloqueos se muestran correctamente.

**Requisitos:** Backend en marcha (`cd backend && source ../.env && uvicorn main:app --port 8000`), frontend en marcha (`cd frontend && npm run dev`), navegador en `http://localhost:5173`.

---

## 1. Aviso de stock insuficiente al cobrar

Objetivo: ver el diálogo *"Hay N producto(s) con stock insuficiente. ¿Cobrar de todas formas?"* antes de abrir el modal de cobro.

**Pasos:**

1. Iniciar sesión con una cuenta válida de pruebas y, si sale el modal de turno, pulsar **Continuar turno**.
2. En **Terminal**, en el buscador escribe **LIMIT**.
3. Añade al carrito el producto **"Race Condition Item"** (Stock: 0). Si no existe, usa cualquier producto y en **Productos** ponle stock 0 o 1 y en Terminal pide más cantidad (ej. 5) con el botón **+**.
4. Pulsa **COBRAR**.
5. **Resultado esperado:**  
   - Aparece primero el diálogo: **"Hay 1 producto(s) con stock insuficiente. El servidor puede rechazar la venta. ¿Cobrar de todas formas?"** con opciones **Aceptar** / **Cancelar**.  
   - Si pulsas **Cancelar**, no se abre el modal de cobro.  
   - Si pulsas **Aceptar**, se abre el modal **Confirmar Cobro** (y al confirmar ahí el backend puede devolver error de stock).

**Comprobar también en el carrito:**  
Con ese producto en el carrito, encima del listado debe verse el banner amarillo *"Entre sesiones hubo cambios: Hay productos con stock insuficiente. Revisa las líneas marcadas antes de cobrar"*, y en la línea del producto el badge rojo *"Stock: 0 (solicitado: 1)"* (o los números que correspondan).

---

## 2. Bloqueo de cobro cuando hay producto "Ya no en catálogo"

Objetivo: que no se pueda cobrar si hay líneas marcadas como "Ya no en catálogo" y que el mensaje indique quitar esas líneas con el botón ×.

**Pasos:**

1. En **Productos**, crea un producto de prueba: SKU **TEST-BORRAR**, nombre **Test borrar**, precio **10**, guardar.
2. Ve a **Terminal** (Ventas). Busca **TEST-BORRAR** y añádelo al carrito.
3. Pulsa **Ticket pendiente** para guardar el ticket como pendiente (el carrito queda vacío y aparece "Pendientes (1)").
4. Ve de nuevo a **Productos**, localiza **Test borrar** y **elimínalo** (o desactívalo si tu versión lo permite).
5. Vuelve a **Terminal**. En el desplegable de pendientes elige el ticket que guardaste (ej. "Ticket-…").
6. **Resultado esperado:**  
   - Si el ticket solo tenía ese producto: mensaje *"\[Nombre] no se puede cargar: todos los productos ya no están en el catálogo. Elimina ese pendiente del listado si ya no aplica."*  
   - El pendiente sigue en la lista; el carrito no se sustituye por ese ticket.
7. Para probar el **bloqueo al cobrar** con producto inexistente en el catálogo (caso raro en la misma sesión):  
   - Añade un producto válido al carrito.  
   - En otra pestaña o en Productos, da de baja el producto que acabas de añadir.  
   - Vuelve a Terminal (se refrescan productos). La línea debería mostrarse con el badge **"Ya no en catálogo"**.  
   - Pulsa **COBRAR**.  
   - **Resultado esperado:** No se abre el modal de cobro; aparece el mensaje *"Hay productos marcados como 'Ya no en catálogo'. Quítalos del ticket (botón ×) antes de cobrar."*

---

## 3. Cargar pendiente con productos que siguen en catálogo (y opcional stock bajo)

Objetivo: ver que al cargar un pendiente se actualizan precios y se informa si se quitaron productos o si hay stock insuficiente.

**Pasos:**

1. En **Terminal** añade 1 o 2 productos que **sí existan** en catálogo (ej. "Prod 1 P1") y guarda **Ticket pendiente**.
2. (Opcional) En **Productos** cambia el **precio** de uno de esos productos o reduce **stock** por debajo de la cantidad del ticket.
3. En **Terminal**, en el desplegable de pendientes, **carga** el ticket que guardaste.
4. **Resultado esperado:**  
   - El carrito se rellena con ese ticket.  
   - Los precios son los **actuales** del catálogo.  
   - Si quitaste algún producto del catálogo antes de cargar: mensaje del tipo *"Se quitaron N producto(s) que ya no están en catálogo"*.  
   - Si hay productos con stock menor que la cantidad pedida: mensaje *"N con stock insuficiente (revisa o ajusta cantidad)"* y, en el carrito, banner amarillo y badges *"Stock: X (solicitado: Y)"* en esas líneas.

---

## 4. Resumen de qué ver en cada caso

| Caso | Dónde | Qué deberías ver |
|------|--------|-------------------|
| Stock insuficiente al cobrar | Al pulsar COBRAR | Diálogo "Hay N producto(s) con stock insuficiente. ¿Cobrar de todas formas?" |
| Stock insuficiente en carrito | Lista del carrito | Banner amarillo y badge "Stock: X (solicitado: Y)" en la línea |
| Producto ya no en catálogo al cobrar | Al pulsar COBRAR | Mensaje "Hay productos marcados como 'Ya no en catálogo'. Quítalos del ticket (botón ×) antes de cobrar." (no se abre modal) |
| Producto ya no en catálogo en carrito | Lista del carrito | Banner amarillo y badge "Ya no en catálogo" en la línea |
| Cargar pendiente cuando todos los productos fueron dados de baja | Al elegir el pendiente en el desplegable | Mensaje "no se puede cargar: todos los productos ya no están en el catálogo" y el pendiente sigue en la lista |
| Cargar pendiente con precios/stock actualizados | Después de cargar | Precios actuales; mensaje si se quitaron productos o hay stock insuficiente |

Si algo no coincide con la tabla, conviene anotar navegador, pasos exactos y si el backend está en la misma versión que el frontend.

---

## Verificación en navegador (3 variantes ejecutadas)

| Variante | Pasos | Resultado |
|----------|--------|-----------|
| **1. Stock insuficiente** | Añadir "Race Condition Item" (Stock: 0) → COBRAR → Cancelar en el diálogo | ✅ Aparece primero el diálogo "Stock insuficiente" con el mensaje de confirmación; al cancelar no se abre el modal de cobro. |
| **2. Producto ya no en catálogo** | Añadir TEST-BORRAR al carrito → ir a Productos → Editar TEST-BORRAR → Eliminar → volver a Ventas → COBRAR | ✅ No se abre el modal; se muestra mensaje (productos "Ya no en catálogo"). Botón Editar en Productos siempre visible (fix aplicado). |
| **3. Flujo pendiente → cobro** | Añadir Prod 1 P1 → Guardar ticket pendiente → Cargar ese pendiente del desplegable → COBRAR | ✅ Se abre el modal "Confirmar Cobro" con monto $33.33 y método Efectivo. |

### Tres variantes adicionales (4–6)

| Variante | Pasos | Resultado |
|----------|--------|-----------|
| **4. Stock insuficiente + Aceptar** | Añadir "Race Condition Item" (Stock: 0) → COBRAR → en el diálogo pulsar **Aceptar** | ✅ Tras Aceptar se abre el modal "Confirmar Cobro" ($100.00); se puede cancelar ahí. |
| **5. Cargar pendiente inválido** | En el desplegable elegir el pendiente que solo tenía TEST-BORRAR (producto ya eliminado del catálogo) | ✅ El carrito no se sustituye; el mensaje "no se puede cargar: todos los productos ya no están en el catálogo" aparece en el área de mensajes. |
| **6. F12 con stock insuficiente** | Añadir producto con Stock: 0 → quitar foco del buscador (clic en otra zona) → pulsar **F12** | ✅ Aparece el mismo diálogo "Stock insuficiente" que al pulsar COBRAR (F12 usa la misma validación). |

---

## Notas de verificación

- Las **6 variantes** (1–6) fueron ejecutadas en navegador vía MCP y pasaron con el comportamiento esperado.
- El botón **Editar** en la tabla de Productos está siempre visible (opacity 60 %) para accesibilidad y pruebas automatizadas.
- Al pulsar **COBRAR** o **F12**, las validaciones (producto “ya no en catálogo” y stock insuficiente) se aplican **antes** de abrir el modal de cobro; si hay bloqueo o el usuario cancela el aviso de stock, el modal no se abre.
