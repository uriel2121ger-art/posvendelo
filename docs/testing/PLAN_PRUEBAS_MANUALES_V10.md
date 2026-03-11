# Plan de Pruebas Manuales V10 — POSVENDELO

Guia de pruebas manuales **mas exigente**: mas edge cases, variantes por escenario y fase dedicada a **monkey testing**. Criterios de pase/fallo estrictos.

**Prerequisitos:**
- Backend corriendo en `localhost:8090`
- Al menos 10 productos con stock variado (0, 1, 5, 20, 50+)
- Al menos 3 clientes registrados
- Al menos 1 producto con precio mayoreo definido
- Al menos 1 producto con clave SAT especifica (ej. `50181700` o `50202300`)
- Usuario admin/manager logueado

**Nota fiscal:** El backend asume `price_includes_tax=True`. Producto $116.00 = base $100.00 + IVA $16.00. Descuentos se aplican al precio con IVA; el desglose fiscal se calcula despues.

**Convencion de esta guia:**
- `[P]` = Paso individual
- `[V]` = Verificacion (criterio de pase/fallo) — **obligatorio cumplir**
- `[V-]` = Verificacion negativa (no debe ocurrir)
- `BLOCKER` = Si falla, detener pruebas y reportar
- `EDGE` = Caso borde; fallar aqui indica fragilidad
- `MATRIZ` = Prueba combinatoria; ejecutar al menos una muestra por celda
- `ORDEN` = Variante de orden de operaciones (detecta dependencias ocultas)
- Cada seccion indica tiempo estimado para el tester

---

## FASE 0: Regresion de Bugs V8 (EJECUTAR PRIMERO)

> Tiempo estimado: 25 min
> Prioridad: BLOCKER — si alguno falla, hay regresion critica

### 0.1 Empleados — Boton Guardar funcional

**Bug V8:** Boton Guardar permanecia permanentemente deshabilitado.

- [ ] **Crear empleado completo:**
  - [P] Ir a Empleados. Codigo: `REG-001`, Nombre: `Regresion QA`, Posicion: `Cajero`, Salario: `8500`, Comision: `10`.
  - [P] Clic Guardar.
  - [V] Empleado aparece en la tabla. Boton Guardar se habilita cuando nombre y codigo no estan vacios.
  - [V] Seleccionar empleado: comision muestra `10.00`.
- [ ] **Guardar con campos minimos:**
  - [P] Limpiar con "Nuevo". Solo Codigo `REG-MIN` y Nombre `Minimo`.
  - [P] Guardar.
  - [V] Se crea exitosamente. Comision default = 0, salario default = 0.
- [ ] **Codigo vacio bloqueado:**
  - [P] Limpiar. Poner Nombre sin Codigo.
  - [V] Boton Guardar deshabilitado (gris).
- [ ] **EDGE — Nombre muy largo (200+ caracteres):**
  - [P] Codigo `LONG`, Nombre de 200 caracteres. Guardar.
  - [V] Se rechaza con mensaje O se trunca y guarda sin corromper. [V-] No crash ni pantalla en blanco.
- [ ] **EDGE — Comision 100.01:**
  - [P] Comision `100.01`. [V] Rechazado (max 100) O aceptado y mostrado correctamente. Comportamiento consistente.

### 0.2 Fiscal — Generar CFDI con feedback

**Bug V8:** Boton "Generar CFDI" era un cascaron vacio — falla silenciosa sin loader ni toast.

- [ ] **CFDI con datos validos:**
  - [P] Hacer una venta. Anotar folio.
  - [P] Ir a Fiscal. Ingresar folio, RFC `XAXX010101000`, CP `01000`, Uso `G03`.
  - [P] Clic "Generar CFDI".
  - [V] Se muestra loader/busy mientras procesa.
  - [V] Al terminar: panel JSON con resultado O mensaje de error explicito en barra inferior.
  - [V] Nunca queda en silencio — siempre hay feedback visible.
- [ ] **CFDI con datos invalidos:**
  - [P] Folio inexistente. Generar.
  - [V] Mensaje de error claro (no silencio).
- [ ] **EDGE — RFC extranjero:** RFC `EKU9003173C9`, CP `01000`. [V] Aceptado o rechazado con mensaje claro; no silencio.
- [ ] **EDGE — CP invalido (4 digitos):** CP `0123`. [V] Validacion o mensaje; no 500.

### 0.3 Carrito vacio — Cobro bloqueado

**Bug V8:** Se podia procesar venta en $0.00 con carrito vacio.

- [ ] **Intentar cobrar sin productos:**
  - [P] Terminal con carrito vacio. Clic Cobrar.
  - [V] Boton Cobrar esta deshabilitado (gris) cuando `cart.length === 0`.
  - [V] Si por bug el boton estuviera habilitado y se hiciera clic: mensaje "No hay productos en el ticket."
  - [V] No se genera folio ni se registra venta.
- [ ] **EDGE — Vaciar carrito con un solo item:** Agregar 1 producto. Quitar. [V] Cobrar sigue deshabilitado. Total $0.00.

### 0.4 Precision matematica — Sin desfase de centavos

**Bug V8:** 16 unidades x $100 mostraba $1600.06 en lugar de $1600.00.

- [ ] **Suma masiva sin drift:**
  - [P] Agregar producto de $100.00 al carrito. Cambiar cantidad a 16.
  - [V] Total = $1,600.00 exacto (no $1,600.06).
- [ ] **Suma de decimales compensados:**
  - [P] 3 productos: $33.33 + $66.67 + $100.00.
  - [V] Total = $200.00 exacto.
- [ ] **Descuento 33% — centavos limpios:**
  - [P] Producto $100.00 x 1. Descuento individual 33%.
  - [V] Subtotal = $67.00 (no $66.999...).
- [ ] **EDGE — Multiples decimales repetidos:** $11.11 x 9 = $99.99. [V] Sin $99.9900001 ni $100.00 por redondeo incorrecto.
- [ ] **EDGE — 100 unidades x $9.99:** [V] Total = $999.00 exacto.

### 0.5 Monitoreo remoto — Consistencia de datos

**Bug V8:** Dashboard reportaba monto total pero 0 ventas y tabla vacia.

- [ ] **Feed de ventas en vivo:**
  - [P] Hacer 3 ventas en Terminal.
  - [P] Ir a Remoto. Esperar auto-refresh (10s).
  - [V] La tabla "Ventas en Vivo" muestra las ventas recientes (no vacia).
  - [V] El contador de "Ventas" coincide con la cantidad de filas visibles (o cercano — puede haber desfase de 1 por timing).
  - [V] El "Total del Turno" coincide con la suma real.
- [ ] **EDGE — Cero ventas en turno nuevo:** Abrir turno, no vender. Ir a Remoto. [V] "0 ventas" y $0.00; tabla vacia sin error.

### 0.6 Disaster recovery — Badge con conteo real

**Bug V8:** Al recuperar turno perdido, badge mostraba "0 ventas" pero monto correcto.

- [ ] **Recuperar turno con historial:**
  - [P] Abrir turno. Hacer 5 ventas ($50 c/u = $250 total).
  - [P] `localStorage.removeItem('titan.currentShift')`. Recargar (F5).
  - [V] Modal detecta turno abierto y lo recupera.
  - [V] Tras recuperar, badge muestra `5 ventas / $250.00` (no `0 ventas / $250.00`).
- [ ] **EDGE — Recuperar con shift corrupto parcial:** `titan.currentShift` con `sales_count: 0` pero `total_cents` correcto. [V] Al recuperar, badge muestra ventas reales (backend) o mensaje coherente.

---

## FASE 1: Flujo Critico de Negocio (Happy Path + Variantes + Matrices y Orden)

> Tiempo estimado: 70 min (con 1.8–1.11); 45 min solo happy path + variantes basicas
> Prioridad: BLOCKER — es el dia a dia del cajero

### 1.1 Apertura y Primera Venta

- [ ] **Abrir turno con fondo:**
  - [P] Login. Abrir turno con fondo `$2,500.50` (con centavos).
  - [V] Badge muestra operador y "0 ventas / $0.00". Fondo registrado con centavos.
- [ ] **Venta con efectivo y cambio:**
  - [P] Buscar producto. Agregar 2 unidades. Anotar total $X. Metodo: Efectivo. Monto recibido: $500.
  - [V] Cambio = $500 - X. Badge: "1 venta".
- [ ] **Venta con tarjeta:**
  - [P] 3 productos variados. Metodo: Tarjeta. Cobrar.
  - [V] No pide monto recibido. Venta registrada.
- [ ] **Venta por transferencia:**
  - [P] 1 producto. Metodo: Transferencia. Cobrar.
  - [V] Venta registrada con metodo `transfer`.
- [ ] **Pago exacto en efectivo (campo vacio):**
  - [P] Total $58. Monto recibido: vacio. Cobrar.
  - [V] Sistema asume pago exacto. Cambio: $0.00.
- [ ] **VARIANTE — Monto recibido menor al total (efectivo):**
  - [P] Total $100. Monto recibido $80. Cobrar.
  - [V] Rechazado con mensaje "Monto insuficiente" o similar. No se registra venta.
- [ ] **VARIANTE — Monto recibido con centavos:** Total $99.50. Recibido $100.00. [V] Cambio $0.50.
- [ ] **VARIANTE — Abrir turno con fondo $0.00:** [V] Aceptado o rechazado segun regla de negocio; sin crash.
- [ ] **EDGE — Abrir turno con fondo negativo:** Fondo `-100`. [V] Rechazado. [V-] No se abre turno.

### 1.2 Busqueda de Productos

- [ ] **Por nombre parcial:** Buscar `coca`. [V] Resultados con "coca" en nombre.
- [ ] **Por SKU:** Buscar SKU exacto. [V] Producto encontrado.
- [ ] **Inexistente:** Buscar `XYZNOEXISTE999`. [V] Lista vacia, sin crash.
- [ ] **Caracteres especiales:** Buscar `%`, `'`, `"`. [V] Sin errores SQL. Resultados vacios o parciales.
- [ ] **Un solo caracter:** Buscar `a`. [V] Retorna resultados sin timeout.
- [ ] **VARIANTE — Busqueda vacia (espacios):** Buscar `   `. [V] Lista vacia o sin resultados; no crash.
- [ ] **VARIANTE — Busqueda solo numeros:** Buscar `12345`. [V] Productos con SKU/codigo que coincidan o vacio.
- [ ] **EDGE — Busqueda con newline:** Buscar `coca\ncola`. [V] Sin error. Comportamiento definido (truncar/ignorar).
- [ ] **EDGE — Borrar busqueda muy rapido:** Escribir `refresco`, borrar en < 500 ms. [V] UI estable. Debounce no dispara request obsoletos.
- [ ] **VARIANTE — Busqueda que coincide con varios productos (ej. "agua"):** [V] Lista con todos. Seleccionar uno: se agrega el correcto.
- [ ] **VARIANTE — Busqueda con acentos:** `café`, `México`. [V] Resultados coherentes (normalizado o exacto).
- [ ] **VARIANTE — Busqueda con mayusculas/minusculas:** `COCA`, `coca`, `Coca`. [V] Mismos resultados (case-insensitive) o definido.
- [ ] **VARIANTE — Primer caracter especial:** Buscar `*refresco`. [V] Sin error. Resultados o vacio.
- [ ] **VARIANTE — Backspace hasta vacio y luego escribir de nuevo:** [V] Resultados del texto final. No resultados "fantasma" del anterior.

### 1.3 Carrito Reactivo

- [ ] **Agregar, quitar, modificar:**
  - [P] Agregar 5 productos. Quitar 2. Agregar 1 distinto. Cambiar cantidad de otro a 3.
  - [V] Totales se recalculan en cada modificacion. Ticket final correcto.
- [ ] **Mismo producto varias veces:**
  - [P] Agregar "Coca Cola". Sin cambiar qty, agregar "Coca Cola" otra vez.
  - [V] Cantidad incrementa a 2 (no linea duplicada).
- [ ] **Cantidad 0 o negativa:**
  - [P] Editar cantidad a 0. [V] Se elimina o rechaza.
  - [P] Editar cantidad a -5. [V] Rechazado. Minimo 1.
- [ ] **VARIANTE — Agregar mismo producto 10 veces seguidas (rapido):** [V] Una sola linea con qty 10. Sin duplicar lineas ni total errático.
- [ ] **VARIANTE — Cambiar cantidad 5 -> 1 -> 99 -> 1:** [V] Total siempre coherente. Sin valores residuales.
- [ ] **EDGE — Cantidad 9999 (stock 100):** [V] Se permite en carrito. Al cobrar: backend rechaza stock insuficiente.
- [ ] **EDGE — Eliminar todos los items uno a uno:** [V] Carrito vacio. Cobrar deshabilitado. No error al quitar el ultimo.
- [ ] **VARIANTE — Orden agregar: A, B, C luego quitar B:** [V] Solo A y C. Total = A + C.
- [ ] **VARIANTE — Agregar A, agregar B, cambiar qty A a 0 (o quitar A), luego agregar A de nuevo:** [V] Carrito: B, A. Totales correctos.
- [ ] **VARIANTE — Cinco productos distintos, aplicar desc ind solo al 2do y 4to:** [V] Subtotal = suma de (precio*qty*(1-desc/100)) para 2do y 4to, resto normal.
- [ ] **VARIANTE — Un item, cantidad 1, aplicar desc 100%, agregar segundo item:** [V] Total = precio segundo item. Primer item en $0.
- [ ] **EDGE — Cambiar cantidad a valor no numerico (si el campo lo permite):** [V] Rechazado o vuelve a 1. No NaN en total.

### 1.4 Descuentos — Matriz Matematica (Mas Variantes)

> **Formula de referencia:**
> - Individual: `precio * qty * (1 - descIndiv/100)`
> - Global: `subtotal * (1 - descGlobal/100)`
> - Compuesto: global se aplica SOBRE subtotal ya descontado

- [ ] **Individual 10%:** Producto $100 x 1. [V] Subtotal = $90.00.
- [ ] **Individual 25% con multiples unidades:** $80 x 3, desc 15%. [V] $204.00.
- [ ] **Individual con centavos:** $99.99, desc 10%. [V] $89.99.
- [ ] **Global 5%:** 3 prods $100+$200+$50 = $350, desc 5%. [V] $332.50.
- [ ] **Global 15% con decimales compensados:** $33.33+$66.67+$100 = $200, desc 15%. [V] $170.00.
- [ ] **Compuesto — individual + global:**
  - [P] A: $100, desc ind 10% = $90. B: $200, sin desc. Sub = $290. Desc global 5%.
  - [V] Desc global = $14.50. Total = $275.50.
- [ ] **Doble pesado — ind 30% + global 20%:** $1000, desc ind 30% = $700. Desc global 20%. [V] Total = $560.00.
- [ ] **Desc 100% (regalo):** $300, desc 100%. [V] Subtotal = $0. Se puede cobrar con otros items.
- [ ] **Desc 99.99%:** $10,000, desc 99.99%. [V] Subtotal = $1.00.
- [ ] **Quitar descuento:** Aplicar 50%, luego cambiar a 0%. [V] Precio original restaurado.
- [ ] **VARIANTE — Tres items con desc individual distinto:** A 10%, B 20%, C 5%. [V] Subtotal = suma de cada (precio*qty*(1-desc/100)).
- [ ] **VARIANTE — Descuento global 0%:** Aplicar 0%. [V] Total igual al subtotal. Sin cambio errático.
- [ ] **EDGE — Descuento 0.01% en $1000:** [V] Subtotal = $999.90 (o redondeo consistente a 2 decimales).
- [ ] **EDGE — Descuento 99.99% en $10:** [V] Subtotal >= $0.01. No negativo.
- [ ] **EDGE — Individual 50% + global 50% en $1000:** Ind = $500, global sobre $500 = $250. [V] Total = $250.00.

### 1.5 Tickets Pendientes

- [ ] **Pausar y retomar:**
  - [P] 5 productos en carrito. Guardar como pendiente. Hacer otra venta. Retomar.
  - [V] Los 5 productos originales siguen con sus cantidades y precios.
- [ ] **Pendiente con descuento individual/global y cliente:** [P] 3 items, desc en item 2, desc global 5%, cliente asignado. Pausar. Retomar. [V] Todo intacto.
- [ ] **Multiples pendientes (4):** Crear 4 tickets. Navegar. Cobrar todos. [V] Todos registrados. Sin cruce de datos.
- [ ] **VARIANTE — Retomar pendiente, modificar, volver a pausar:** [V] Cambios persisten al retomar de nuevo.
- [ ] **EDGE — Pendiente con un solo item de $0.01:** [V] Se guarda y cobra correctamente.
- [ ] **EDGE — Crear 8+ pendientes (si la UI lo permite):** [V] Lista manejable. Cobrar cada uno sin mezclar con otro.

### 1.6 Modo Mayoreo

- [ ] **Toggle mayoreo:** Activar mayoreo. Agregar producto con precio mayoreo. [V] Precio = mayoreo. Desactivar: precio = normal.
- [ ] **Producto sin mayoreo en modo mayoreo:** [V] Usa precio normal como fallback.
- [ ] **Mayoreo + descuento individual:** Mayoreo $80, desc 10%. [V] $72.00.
- [ ] **Mayoreo en ticket pendiente:** Modo mayoreo, agregar, pausar, retomar. [V] Precio mayoreo se conserva.
- [ ] **EDGE — Mayoreo = 0 o igual a precio normal:** [V] No error. Comportamiento consistente (fallback a normal).

### 1.7 Cierre de Turno y Reapertura

- [ ] **Cerrar turno con corte:** Tras varias ventas, ir a Turnos. Cerrar. Ingresar efectivo contado. [V] Esperado vs Contado vs Diferencia. Cierre < 8 s.
- [ ] **Diferencia sobrante/faltante y reapertura limpia:** [V] Nuevo turno sin arrastre del anterior.
- [ ] **EDGE — Cerrar con efectivo contado en 0:** [V] Diferencia = -Total. Se cierra. Sin crash.
- [ ] **EDGE — Cerrar con contado mayor a esperado (ej. 2x):** [V] Diferencia positiva. Cierre correcto.

### 1.8 MATRIZ exhaustiva: Metodo de pago × Cliente × Descuento × Tipo de ticket

> Objetivo: cubrir combinaciones que pueden fallar por interaccion. Ejecutar al menos 1 prueba por fila/columna; si hay tiempo, cubrir todas las celdas.

- [ ] **Efectivo + sin cliente + sin desc + 1 item:** [V] Cobro OK. Cambio correcto.
- [ ] **Efectivo + sin cliente + sin desc + 5 items:** [V] Total = suma. Cobro OK.
- [ ] **Efectivo + con cliente + sin desc + 1 item:** [V] Venta con customer_id. Historial muestra cliente.
- [ ] **Efectivo + con cliente + desc individual 10% + 2 items:** [V] Subtotal descontado. Cliente en venta.
- [ ] **Efectivo + con cliente + desc global 15% + 3 items:** [V] Total = subtotal*0.85. Cliente asignado.
- [ ] **Efectivo + sin cliente + desc ind 50% + 1 item:** [V] Subtotal = mitad precio.
- [ ] **Tarjeta + sin cliente + sin desc + 1 item:** [V] No pide monto. Venta OK.
- [ ] **Tarjeta + con cliente + sin desc + 4 items:** [V] Venta con cliente. Metodo tarjeta.
- [ ] **Tarjeta + con cliente + desc global 5%:** [V] Total con descuento. Metodo correcto.
- [ ] **Transferencia + sin cliente + sin desc + 1 item:** [V] Metodo transfer.
- [ ] **Transferencia + con cliente + desc ind 20%:** [V] Cliente + descuento + metodo en historial.
- [ ] **Efectivo + monto recibido exacto (sin cambio):** Total $77. Monto $77. [V] Cambio $0.00.
- [ ] **Efectivo + monto recibido con centavos:** Total $33.33. Recibido $50.00. [V] Cambio $16.67.
- [ ] **Efectivo + pago con sobra grande:** Total $10. Recibido $1000. [V] Cambio $990.00. Sin overflow.
- [ ] **Mayoreo ON + 1 item con mayoreo + efectivo:** [V] Precio mayoreo. Cobro OK.
- [ ] **Mayoreo ON + 1 item sin mayoreo + tarjeta:** [V] Precio normal. Cobro OK.
- [ ] **Ticket con 1 item + cliente asignado despues de agregar item:** [V] Cliente queda asignado. Cobrar: venta con cliente.
- [ ] **Ticket con 3 items + cliente asignado antes de agregar el 3ro:** [V] Mismo resultado: venta con cliente y 3 items.
- [ ] **Ticket con desc global 10% aplicado antes de agregar ultimo item:** [V] Descuento aplicado a subtotal final.
- [ ] **Ticket con desc global 10% aplicado despues de agregar todos:** [V] Mismo total que el caso anterior.
- [ ] **Cambiar metodo de pago a mitad:** Items en carrito. Seleccionar Efectivo, luego cambiar a Tarjeta. Cobrar. [V] Venta con Tarjeta.
- [ ] **Cambiar cliente a mitad:** Cliente A. Agregar items. Cambiar a Cliente B. Cobrar. [V] Venta con Cliente B.
- [ ] **Quitar cliente antes de cobrar:** Asignar cliente. Quitar (si la UI lo permite). Cobrar. [V] Venta sin cliente o ultimo estado coherente.

### 1.9 ORDEN de operaciones — Variantes que detectan dependencias

- [ ] **Orden A:** Abrir turno → Agregar 1 item → Asignar cliente → Cobrar (efectivo). [V] OK.
- [ ] **Orden B:** Abrir turno → Asignar cliente → Agregar 1 item → Cobrar (efectivo). [V] OK. Mismo resultado que A.
- [ ] **Orden C:** Agregar 3 items → Aplicar desc global 10% → Asignar cliente → Cobrar. [V] Total y cliente correctos.
- [ ] **Orden D:** Asignar cliente → Agregar 3 items → Aplicar desc ind en item 2 → Cobrar. [V] Descuento en item 2. Cliente en venta.
- [ ] **Orden E:** Agregar item → Pausar (pendiente) → Hacer otra venta → Retomar → Agregar otro item → Cobrar. [V] Pendiente con 2 items. Un solo folio.
- [ ] **Orden F:** Abrir F9 (verificador) → Buscar producto → Cerrar F9 → Agregar ese producto al carrito → Cobrar. [V] Producto en ticket. Venta OK.
- [ ] **Orden G:** Agregar 2 items → Cambiar cantidad item 1 a 0 (o quitar) → Cobrar. [V] Solo item 2. Total correcto.
- [ ] **Orden H:** Descuento ind 100% en item 1 (regalo) → Agregar item 2 → Cobrar. [V] Total = precio item 2. Item 1 con $0.
- [ ] **Orden I:** Modo mayoreo ON → Agregar producto con mayoreo → Pausar → Retomar (mayoreo puede quedar OFF) → Cobrar. [V] Precio en venta = mayoreo si se conservo estado; si no, documentar comportamiento.
- [ ] **Orden J:** Cobrar (modal abierto) → Red perdida → Reconectar → Reintentar cobro. [V] Una sola venta o error claro. No duplicado.

### 1.10 Descuentos — Matriz de porcentajes exhaustiva

> Probar al menos un caso por fila. Precio base $100 donde aplique.

- [ ] **0% individual:** $100, desc 0%. [V] Subtotal = $100.00.
- [ ] **0.01% individual:** $1000, desc 0.01%. [V] Subtotal = $999.90 (redondeo 2 decimales).
- [ ] **1% individual:** $100, desc 1%. [V] $99.00.
- [ ] **10%, 25%, 33%, 33.33% individual:** [V] $90, $75, $67, $66.67 (redondeo consistente).
- [ ] **50% individual:** $100. [V] $50.00.
- [ ] **99% individual:** $100. [V] $1.00.
- [ ] **99.99% individual:** $100. [V] $0.01.
- [ ] **100% individual (regalo):** [V] $0.00. Cobrable con otros items.
- [ ] **0% global (subtotal $200):** [V] Total = $200.
- [ ] **5%, 10%, 15%, 20% global:** Subtotal $200. [V] $190, $180, $170, $160.
- [ ] **50% global:** Subtotal $200. [V] $100.00.
- [ ] **100% global (todo regalo):** [V] Total $0. Carrito con items; si se permite cobrar, venta en $0 o rechazo segun regla.
- [ ] **Compuesto: ind 10% (item $100=$90) + ind 20% (item $50=$40) → subtotal $130 → global 10%:** [V] $117.00.
- [ ] **Tres items, desc solo en el segundo:** A $100, B $50 desc 30%=$35, C $25. [V] Subtotal = $160.00.
- [ ] **Mismo item, dos lineas, desc solo en una:** Linea 1: $100 x2. Linea 2: $100 x1 desc 10%. [V] 200 + 90 = $290.

### 1.11 Campos numericos — Valores extremos por campo

**Monto recibido (efectivo):**
- [ ] **0:** Total $50, recibido $0. [V] Rechazado (monto insuficiente).
- [ ] **Negativo:** Pegar -50. [V] Rechazado o corregido. [V-] No se acepta.
- [ ] **Decimal 3 cifras:** 99.999. [V] Redondeado a 99.99 o rechazado.
- [ ] **Muy grande:** 99999999.99. [V] Aceptado o limitado. Cambio coherente.
- [ ] **Cientifica:** 1e5. [V] Tratado como 100000 o rechazado. No NaN.

**Cantidad (carrito):**
- [ ] **0:** Editar a 0. [V] Linea eliminada o rechazada.
- [ ] **1, 2, 99, 100:** [V] Total = precio × cantidad.
- [ ] **9999 (stock 10):** [V] En carrito permitido. Al cobrar: rechazo stock.
- [ ] **Negativo:** -1 o -5. [V] Rechazado. Min 1.
- [ ] **Decimal:** 2.5 (si la UI permite). [V] Entero forzado o rechazado. No 2.5 uds vendidas.
- [ ] **Texto:** abc. [V] Rechazado o reset a 1. No NaN.

**Descuento individual %:**
- [ ] **0, 1, 10, 50, 100:** [V] Subtotal segun formula.
- [ ] **100.01, 200:** [V] Limitado a 100 o rechazado. No subtotal negativo.
- [ ] **-5, -10:** [V] Rechazado. No aumento de precio por desc negativo (a menos que sea regla de negocio).
- [ ] **99.99:** [V] Subtotal >= 0.01.

**Descuento global %:** (mismos extremos que individual).

**Fondo de caja (apertura):**
- [ ] **0:** [V] Aceptado o rechazado. Documentado.
- [ ] **0.01:** [V] Aceptado. Badge muestra centavos.
- [ ] **Negativo:** -100. [V] Rechazado.
- [ ] **999999.99:** [V] Aceptado o limite. Sin overflow en reportes.
- [ ] **1e6:** [V] Tratado como numero o rechazado. No NaN.

**Efectivo contado (cierre):**
- [ ] **0:** [V] Diferencia = -Total. Cierre permitido o rechazado.
- [ ] **Con decimales:** 1234.56. [V] Diferencia calculada correctamente.
- [ ] **Mayor que esperado:** Ej. 2×. [V] Diferencia positiva.

---

## FASE 2: Integridad de Datos y Seguridad (Mas Edge)

> Tiempo estimado: 35 min
> Prioridad: ALTA

### 2.1 Stock y Sobreventa

- [ ] **Stock 0:** Agregar producto con stock 0. Cobrar. [V] Backend rechaza "Stock insuficiente... Disponible: 0".
- [ ] **Agotar stock parcial:** Producto 5 uds. Agregar 10. Cobrar. [V] Rechazado. Stock nunca negativo.
- [ ] **Entrada de inventario:** +24 en Inventario. [V] Terminal refleja stock actualizado.
- [ ] **EDGE — Reducir stock a 0 mientras el producto esta en carrito en otra pestana:** [V] Al cobrar, rechazo por stock insuficiente.
- [ ] **EDGE — Stock 1, dos pestanas agregan 1 cada una, cobrar ambas:** [V] Una pasa, otra rechazada. Stock final 0.

### 2.2 Precio en Vuelo (Backend Valida)

- [ ] **Cambiar precio con ticket abierto:** Agregar producto $100. En otra pestana cambiar a $200. Cobrar (frontend envia $100). [V] Backend rechaza; valida precio real de DB.
- [ ] **EDGE — Cambiar precio a $0.01 en otra tab, cobrar en la que muestra $100:** [V] Backend valida con DB; rechaza o acepta segun regla (precio minimo).

### 2.3 Cobro Fantasma Post-Turno

- [ ] **Ticket huerfano:** Pestana A con carrito. Pestana B cierra turno. A cobra. [V] Rechazado "No hay turno abierto."
- [ ] **EDGE — Recargar A despues de que B cierra:** A sin recargar intenta cobrar. [V] Mismo rechazo.

### 2.4 Doble Clic en Cobrar

- [ ] **Doble clic rapido:** Productos en carrito. Doble clic en Cobrar. [V] Solo 1 venta. Boton deshabilitado durante busy.
- [ ] **VARIANTE — Triple clic en < 1 s:** [V] Una sola venta. [V-] No 2 o 3 folios.

### 2.5 Inyeccion XSS y SQL

- [ ] **XSS en busqueda:** `<script>alert(1)</script>`. [V] No se ejecuta JS.
- [ ] **XSS en nombre de producto:** `<img onerror=alert(1) src=x>`. [V] Texto plano.
- [ ] **SQL injection:** `'; DROP TABLE products; --`. [V] Sin error SQL.
- [ ] **Zalgo text, caracteres nulos, emojis:** [V] Sin crash. Busqueda/creacion segun caso.
- [ ] **EDGE — Null byte en medio:** Buscar `coca\0cola`. [V] Caracteres de control eliminados; no error 500.
- [ ] **EDGE — Unicode homoglyphs en busqueda:** Caracteres que parecen ASCII. [V] Resultados coherentes o vacios.

### 2.6 Proteccion de Sesion

- [ ] **localStorage.clear() con ticket:** 10 items. clear(). Cobrar. [V] Error o redireccion a Login. Sin pantalla blanca.
- [ ] **Token invalido / expirado:** [V] 401. Redireccion a Login.
- [ ] **Config corrupta, JSON roto en shift:** [V] App carga con defaults o modal de turno. Sin WSOD.
- [ ] **EDGE — Token vacio:** `titan.token = ''`. [V] Tratado como no autenticado.
- [ ] **EDGE — Token malformado (no JWT):** `titan.token = 'abc'`. [V] 401 o redireccion.
- [ ] **EDGE — Token JWT firmado con otra clave:** Token valido pero de otro entorno. [V] 401.
- [ ] **EDGE — Borrar solo titan.currentShift:** Resto intacto. Recargar. [V] Modal recuperar turno. No perdida de token.
- [ ] **EDGE — Borrar solo titan.token con turno abierto:** Cobrar. [V] 401 o redireccion. Turno en backend sigue abierto.
- [ ] **VARIANTE — Stock 2, pestana A agrega 2, pestana B agrega 1, A cobra primero:** [V] A OK (stock=0). B al cobrar: rechazado.
- [ ] **VARIANTE — Stock 2, A y B agregan 1 cada uno, ambas cobran a la vez:** [V] Dos ventas de 1 ud. Stock final 0. Folios distintos.
- [ ] **VARIANTE — Producto desactivado mientras esta en carrito:** Desactivar en otra tab. Cobrar. [V] Backend rechaza o acepta; no crash. Comportamiento documentado.
- [ ] **VARIANTE — Cliente eliminado (si aplica) mientras esta asignado al ticket:** [V] Cobro con cliente null o rechazo. No 500.
- [ ] **Busqueda: longitud 1, 2, 50, 200, 1000 caracteres:** [V] Sin timeout. Resultados o vacio. No 500.
- [ ] **Busqueda: solo espacios (5, 50, 200):** [V] Lista vacia. No crash.
- [ ] **Busqueda: tab, newline, retorno de carro:** [V] Tratados. No inyeccion.

---

## FASE 3: CRUD Completo (Mas Variantes y Edge)

> Tiempo estimado: 35 min
> Prioridad: ALTA

### 3.1 Productos

- [ ] **Crear basico, con mayoreo, editar precio/SKU, precio min/max, nombre largo, SKU especiales, desactivar, stock negativo rechazado:** (resumen V9) [V] Segun cada caso.
- [ ] **VARIANTE — Editar producto que esta en un pendiente:** [V] Al retomar pendiente, precio/cantidad coherente (el que tenia al guardar o el actual segun regla).
- [ ] **EDGE — Nombre vacio:** Crear con SKU y nombre vacio. [V] Rechazado.
- [ ] **EDGE — Precio $0.00:** [V] Rechazado o permitido; comportamiento documentado. No overflow en totales.
- [ ] **EDGE — Stock inicial negativo al crear:** [V] Rechazado.

### 3.2 Claves SAT

- [ ] **Default, asignar especifica, cambiar, clave unidad KGM, copia a sale_items:** (resumen V9). [V] Correcto.
- [ ] **EDGE — Clave SAT vacia o invalida (ej. 8 letras):** [V] Rechazado o default a 01010101.

### 3.3 Clientes

- [ ] **Crear, duplicado local/backend/espacios, persistir, solo nombre, editar, asignar a venta, cambiar a mitad de captura:** (resumen V9). [V] Correcto.
- [ ] **EDGE — Nombre con 500 caracteres:** [V] Truncado o rechazado. No crash.
- [ ] **EDGE — Telefono con letras:** [V] Rechazado o guardado como texto; no error 500.

### 3.4 Empleados

- [ ] **CRUD, comision decimal, 0% y 100%, notas, codigo duplicado, caracteres especiales:** (resumen V9). [V] Correcto.
- [ ] **EDGE — Salario negativo:** [V] Rechazado.

### 3.5 Gastos

- [ ] **Registrar, monto 0 rechazado, centavos:** (resumen V9). [V] Correcto.
- [ ] **EDGE — Motivo vacio:** [V] Aceptado o rechazado; consistente.
- [ ] **VARIANTE — Monto negativo:** -100. [V] Rechazado.
- [ ] **VARIANTE — Monto muy grande:** 999999.99. [V] Aceptado o limite. Aparece en reporte/corte.
- [ ] **VARIANTE — Motivo muy largo (500 chars):** [V] Truncado o rechazado. No error.
- [ ] **VARIANTE — Dos gastos seguidos mismo monto:** $50, $50. [V] Ambos registrados. Timestamps distintos.

### 3.6 MATRIZ Producto — Campos en combinacion

- [ ] **SKU minimo (1 char) + nombre 1 char:** Si permitido. [V] Crea. Busqueda encuentra.
- [ ] **SKU max (longitud permitida) + nombre largo:** [V] Persiste. No truncado incorrecto.
- [ ] **Precio 0.01 + stock 0:** [V] Producto creado. Venta rechazada por stock.
- [ ] **Precio 0.01 + stock 9999:** [V] Venta 1 ud = $0.01. Total correcto.
- [ ] **Precio 999999.99 + mayoreo 999999.00:** [V] Ambos guardados. Terminal muestra correcto.
- [ ] **Crear producto → editar nombre → editar precio → desactivar:** [V] Cada paso persiste. Desactivado no aparece en Terminal.
- [ ] **Producto con clave SAT + clave unidad: crear, vender, facturar:** [V] CFDI con claves correctas en concepto.

### 3.7 MATRIZ Cliente — Variantes

- [ ] **Nombre con solo espacios:** `   `. [V] Rechazado o normalizado. No fila vacia.
- [ ] **Nombre duplicado case-insensitive:** `Juan` y `juan`. [V] Segundo rechazado (local o 409).
- [ ] **Telefono 10 digitos, 15 digitos, con guiones:** [V] Aceptado o normalizado. No 500.
- [ ] **Email invalido:** `no-email`. [V] Rechazado o guardado como texto. No 500.
- [ ] **Cliente usado en 5 ventas → editar nombre:** [V] Edicion OK. Ventas historicas siguen mostrando nombre en momento de venta o actualizado segun diseno.

### 3.8 MATRIZ Empleado — Variantes

- [ ] **Salario 0, salario 0.01, salario 999999.99:** [V] Todos aceptados o con limites. Lista muestra correcto.
- [ ] **Comision 0, 50, 100, 100.00:** [V] Persisten. No 100.01 si hay validacion.
- [ ] **Posicion vacia (si es opcional):** [V] Crea. No error.
- [ ] **Codigo con espacios:** ` EMP-01 `. [V] Trim o rechazado. No duplicado con `EMP-01`.
- [ ] **Eliminar empleado con ventas en turno actual (si aplica):** [V] Rechazado o cascada documentada.

---

## FASE 4: Navegacion, UX y Configuracion

> Tiempo estimado: 20 min
> Prioridad: MEDIA

### 4.1 Teclas F — Navegacion Rapida

- [ ] **F1–F6, F1 desde cualquier tab, F7/F8/F9, F9 no afecta carrito, abrir/cerrar F9 x10:** (resumen V9). [V] Instantaneo, sin leak.
- [ ] **EDGE — F1 pulsado 20 veces seguidas muy rapido:** [V] Terminal estable. Carrito intacto. Sin stack de modales.
- [ ] **EDGE — Modal F9 abierto y pulsar F1:** [V] Comportamiento definido (cierra modal y va a Terminal, o bloquea). Sin estado inconsistente.

### 4.2–4.5 Movimientos, Verificador, Dirty State, Historial

- [ ] Segun Fase 4 V9. [V] Movimientos F7/F8 con PIN, dirty state en Settings/Hardware, historial por folio/fecha/descuento/metodo.
- [ ] **EDGE — Guardar pendiente con F9 abierto:** [V] Pendiente guardado. F9 se cierra o no interfiere.

---

## FASE 5: Concurrencia y Multi-Terminal (Mas Variantes)

> Tiempo estimado: 40 min
> Prioridad: ALTA

### 5.1 Multi-Pestana

- [ ] **Badges por polling, 5 pestanas 20 ventas, descuentos en pestanas separadas:** (V9). [V] Folios secuenciales, descuentos correctos.
- [ ] **VARIANTE — Mismo producto en 3 pestanas, distintas cantidades; cobrar las 3 casi a la vez (stock justo):** [V] Solo las que no excedan stock total pasan. Stock final coherente.
- [ ] **EDGE — Pestana A en "Cobrar" (modal abierto), B cierra turno:** A termina cobro. [V] Rechazo "turno cerrado" o venta registrada antes del cierre; nunca venta fantasma.

### 5.2 Colision de Stock y 5.3–5.4

- [ ] Stock bajo + cobros simultaneos, ultima unidad, edicion simultanea producto; cerrar turno en A y cobrar en B; dos terminales fisicas: (V9). [V] Sin corrupcion.
- [ ] **EDGE — Dos tabs editan el mismo producto (nombre vs precio) y guardan:** [V] Uno gana. No corrupcion de campos.

---

## FASE 6: Resiliencia de Red

> Tiempo estimado: 20 min
> Prioridad: ALTA

### 6.1–6.4

- [ ] Desconexion total (cobrar, guardar pendiente, reconectar); micro-cortes; backend muerto; 3G lento: (V9). [V] Toast/error claro, ticket intacto, 0 duplicados.
- [ ] **EDGE — Reconectar exactamente al momento de recibir 200 del cobro:** [V] Una sola venta. No duplicado.
- [ ] **EDGE — Timeout largo (30 s):** Simular latencia 30 s en cobro. [V] Timeout o retry; mensaje claro. No doble envio al reintentar.

---

## FASE 7: Estres y Volumen (Mas Exigente)

> Tiempo estimado: 55 min
> Prioridad: MEDIA

- [ ] **50 ventas en < 30 min** con descuentos y movimientos; **tickets 5+ items**; **pendientes activos:** (V9). [V] Sin lag, totales correctos.
- [ ] **Carrito 100+ items:** Scroll fluido. Cobro exitoso.
- [ ] **VARIANTE — Carrito 200+ items (mezcla 20 productos):** [V] Render estable. Cobro en < 15 s.
- [ ] **VARIANTE — 100 ventas en sesion (turno unico):** [V] Historial y reporte coherentes. Folios 1–100. Corte < 10 s.
- [ ] **Sesion 4+ h, corte con 100+ ventas:** (V9). [V] Memoria < 500MB, sin "pagina no responde".
- [ ] **EDGE — Mismo producto x999 en un ticket (stock >= 999):** [V] Total correcto. Backend acepta. Sin timeout.

---

## FASE 8: Escenarios Caoticos

> Tiempo estimado: 25 min
> Prioridad: MEDIA

- [ ] **Disaster recovery (Alt+F4, kill backend, F5 durante cobro); login simultaneo; cascada de errores con pendientes; abuso UI (10k chars, debounce, 50 busquedas); datos numericos extremos:** (V9). [V] Ventas atomicas, 0 duplicados, UI estable.
- [ ] **EDGE — localStorage modificado durante request de cobro:** [V] No corrupcion. Venta se registra o falla limpio.
- [ ] **EDGE — Dos F5 en 2 segundos:** [V] Una sola recarga efectiva. Turno recuperable.

---

## FASE 9: Fiscal y Facturacion

> Tiempo estimado: 20 min
> Prioridad: MEDIA

- [ ] **CFDI valido/invalido, claves SAT, clave unidad, descuento, metodo de pago; IVA desglose; Remoto:** (V9). [V] Loader, resultado/error, numeros correctos.
- [ ] **EDGE — CFDI de venta con total $0.01 (regalo + otro item):** [V] Genera o rechaza con mensaje. No 500.
- [ ] **EDGE — Venta con 20+ conceptos (items):** [V] CFDI generado con todos los conceptos. Claves SAT correctas.

---

## FASE 10: Auditoria Final Post-Pruebas

> Tiempo estimado: 20 min
> Prioridad: ALTA

- [ ] **Cuadre matematico (10 tickets, 5 productos stock, metodos de pago, movimientos caja); folios secuenciales; claves SAT en ventas; descuentos en historial:** (V9). [V] Centavo a centavo.
- [ ] **EDGE — Cuadre despues de sesion con 100+ ventas y varios pendientes cobrados:** [V] Suma ventas = total reporte. Entradas - retiros = neto corte.

---

## FASE 11: Monkey Testing

> Tiempo estimado: 40 min
> Prioridad: ALTA — valida robustez ante uso impredecible

Objetivo: simular usuario que hace clics e inputs rapidos, aleatorios y a veces invalidos. **Criterio de pase:** no crash, no pantalla blanca, no duplicar ventas ni corromper datos. Errores mostrados al usuario son aceptables.

### 11.1 Clics Rapidos y Multi-boton

- [ ] **Cobrar x10 en 2 segundos (con productos en carrito):**
  - [P] Un item en carrito. Clic Cobrar 10 veces lo mas rapido posible.
  - [V] Solo 1 venta registrada. [V-] No 2+ folios. UI se recupera (boton deshabilitado o loading).
- [ ] **Guardar pendiente x5 rapido:** Carrito con 3 items. Clic "Guardar pendiente" 5 veces. [V] Un solo pendiente. No duplicados en lista.
- [ ] **Alternar F1–F6 muy rapido (2 ciclos completos en 5 s):** [V] No crash. Tab final coherente. Carrito si estaba en Terminal intacto.
- [ ] **Abrir y cerrar F9 (Verificador) 15 veces seguidas:** [V] No leak de modales. No error "already open". Al final se cierra con Esc.

### 11.2 Inputs Caoticos en Buscador

- [ ] **Pegar 5000 caracteres en busqueda:** [V] No congelamiento. Resultados vacios o truncado. Debounce no dispara 50 requests.
- [ ] **Escribir y borrar con backspace muy rapido (20 veces):** Ej: `refresco` -> borrar todo -> `agua`. [V] Resultado final "agua". Sin requests intermedios que cambien resultados al azar.
- [ ] **Solo teclas especiales:** Ctrl+V, Enter, Tab en campo busqueda. [V] Comportamiento definido. No crash.
- [ ] **Pegar texto con null bytes y saltos de linea:** [V] Caracteres peligrosos no provocan error 500 ni XSS.
- [ ] **Busqueda con emojis y RTL:** Ej: `🍺 cerveza` o texto RTL. [V] No crash. Resultados o vacio.

### 11.3 Carrito bajo Estrés

- [ ] **Agregar y quitar el mismo producto 20 veces seguidas (rapido):** [V] Estado final: 0 o 1 unidad. Total correcto. No lineas fantasma.
- [ ] **Cambiar cantidad con teclado muy rapido:** 1 -> 5 -> 10 -> 2 -> 99 -> 1. [V] Total final coherente con cantidad mostrada.
- [ ] **Agregar 5 productos distintos en 3 segundos (buscar y agregar):** [V] Los 5 en el ticket. Totales correctos.
- [ ] **Clic "Quitar" en el mismo item 3 veces rapido:** [V] Item eliminado una vez. No negativo ni error.

### 11.4 Modales y Navegacion Caotica

- [ ] **Abrir F9, luego F7, luego F8 sin cerrar:** [V] Solo un modal activo (el ultimo) o se cierran en orden. No multiples overlays.
- [ ] **Durante "Cobrar" (modal de pago abierto), pulsar F1 varias veces:** [V] Modal de cobro prevalece o se cierra con mensaje. No navegar a Terminal dejando modal huérfano.
- [ ] **Abrir turno y antes de que termine el request, hacer clic otra vez en "Abrir turno":** [V] Un solo turno abierto. No doble fondo.
- [ ] **Cerrar turno: ingresar monto y clic "Cerrar" x3 rapido:** [V] Un solo cierre. No dos turnos cerrados con mismo ID.

### 11.5 Campos Numericos (Monto, Cantidad, Descuento)

- [ ] **Monto recibido: pegar "-100":** [V] Rechazado o corregido a 0/positivo. No se acepta negativo como valido.
- [ ] **Monto recibido: pegar "1.999" (3 decimales):** [V] Redondeado a 2 decimales o rechazado. Total/cambio coherente.
- [ ] **Cantidad: pegar "0" o "abc":** [V] Rechazado o reset a 1. No NaN en total.
- [ ] **Descuento individual: escribir "100.01" o "200%":** [V] Limitado a 100 o rechazado. No subtotal negativo.
- [ ] **Fondo de caja: pegar "1e10" o "999999999999":** [V] Rechazado o limitado. No overflow en reportes.

### 11.6 Multi-Pestana Monkey

- [ ] **3 pestanas: en cada una agregar productos y hacer clic en Cobrar en ventana de 1 segundo (mismo turno):** [V] 3 ventas. Folios distintos. Totales correctos. Stock coherente.
- [ ] **Pestana A: cobrar. Pestana B: recargar (F5) en el mismo segundo:** [V] A: venta registrada o error. B: tras recarga ve turno y badge actualizado. No estado corrupto.
- [ ] **Pestana A: guardar pendiente. B: guardar otro pendiente. A: retomar el primero y cobrar de inmediato:** [V] Cobro del pendiente correcto. No mezcla con el de B.

### 11.7 Resiliencia Post-Monkey

- [ ] **Tras 11.1–11.6: verificar historial y badge:** [V] Numero de ventas y total del turno coinciden con ventas realizadas. [V-] No ventas duplicadas ni faltantes.
- [ ] **Tras monkey: cerrar turno normalmente:** [V] Cierre exitoso. Esperado vs Contado coherente.

### 11.8 Monkey — Variantes adicionales exhaustivas

- [ ] **Cobrar con 0 items (si el boton por bug se habilita):** Forzar o simular. [V] Mensaje "No hay productos" o rechazo. No folio.
- [ ] **Guardar pendiente con carrito vacio (si permitido):** [V] No pendiente vacio o mensaje claro.
- [ ] **Pulsar F1–F6 en orden inverso (F6→F5→…→F1) 3 veces rapido:** [V] Tab estable. Sin doble render.
- [ ] **Abrir modal F7, escribir monto, sin guardar pulsar F8:** [V] Un solo modal activo. F7 se cierra o F8 abre encima. No ambos abiertos.
- [ ] **En busqueda: pegar 10 veces el mismo string (ej. 1000 chars x10):** [V] Input limitado o truncado. No 10k chars enviados al backend.
- [ ] **Agregar producto A, B, A, B, A (alternando) muy rapido:** [V] Carrito con A x3, B x2. Total correcto.
- [ ] **Cambiar cantidad con flechas (si hay) o teclado: 1 → 2 → 1 → 0 (o quitar):** [V] Linea eliminada o cantidad 1. No estado invalido.
- [ ] **Seleccionar metodo Efectivo, escribir monto, cambiar a Tarjeta, cobrar:** [V] Venta con Tarjeta. No pide monto. No monto residual.
- [ ] **Asignar cliente, guardar pendiente, retomar, quitar cliente (si UI permite), cobrar:** [V] Venta sin cliente o con cliente segun ultima accion.
- [ ] **Cerrar navegador (Ctrl+W) con modal de cobro abierto:** Reabrir. [V] Turno recuperable. Venta no duplicada. Carrito puede estar vacio (cobro en curso) o con items (cobro no enviado).
- [ ] **Durante carga de "Abrir turno" (spinner), recargar pagina:** [V] Un solo turno abierto o ninguno. No doble apertura.
- [ ] **En Historial: buscar folio inexistente, folio vacio, folio con caracteres:** [V] Sin resultados o error claro. No 500.
- [ ] **En Fiscal: Generar CFDI dos veces seguidas mismo folio (doble clic):** [V] Un solo CFDI o segundo rechazado (ya facturado). No duplicado.
- [ ] **F9 abierto, buscar producto, agregar al carrito desde F9 (si hay boton):** [V] Item en carrito. F9 no corrompe estado.
- [ ] **Multi-pestana: A en Turnos (cerrar), B en Terminal (cobrar). B cobra 1 s despues de que A cierra:** [V] B: rechazo "turno cerrado". No venta fantasma.

---

## FASE 12: Variantes exhaustivas y matrices (deteccion de fallos)

> Tiempo estimado: 60 min (muestreo) a 120 min (completo)
> Prioridad: ALTA — maximiza probabilidad de encontrar fallos antes de produccion

Objetivo: ejercitar combinaciones y ordenes que rara vez se prueban. Ejecutar por **muestreo** (elegir N por bloque) o **completo** si hay tiempo.

### 12.1 Matriz: Metodo × Momento de asignar cliente

| Metodo    | Cliente antes de items | Cliente despues de items | Sin cliente |
|-----------|------------------------|---------------------------|-------------|
| Efectivo  | [ ] [V] venta con cliente | [ ] [V] venta con cliente | [ ] [V] venta sin cliente |
| Tarjeta  | [ ] [V] | [ ] [V] | [ ] [V] |
| Transferencia | [ ] [V] | [ ] [V] | [ ] [V] |

- [ ] **Cobertura:** Al menos 1 prueba por fila. [V] En historial: customer_id y payment_method correctos.

### 12.2 Matriz: Descuento × Cantidad de items

| Descuento      | 1 item | 2 items | 5+ items |
|----------------|--------|---------|----------|
| Sin desc       | [ ] [V] | [ ] [V] | [ ] [V] |
| Solo ind 10%   | [ ] [V] | [ ] [V] | [ ] [V] |
| Solo global 10%| [ ] [V] | [ ] [V] | [ ] [V] |
| Ind + global   | [ ] [V] | [ ] [V] | [ ] [V] |
| Regalo (100% ind) + otros | [ ] [V] | [ ] [V] | [ ] [V] |

- [ ] **Cobertura:** Al menos 2 filas y 2 columnas. [V] Total = formula. Descuento en historial correcto.

### 12.3 Matriz: Pendiente × Accion posterior

| Accion tras guardar pendiente | Retomar y cobrar | Retomar, modificar, cobrar | Retomar, pausar de nuevo |
|------------------------------|-------------------|----------------------------|---------------------------|
| Hacer 0 ventas               | [ ] [V] | [ ] [V] | [ ] [V] |
| Hacer 1 venta                | [ ] [V] | [ ] [V] | [ ] [V] |
| Hacer 3 ventas               | [ ] [V] | [ ] [V] | [ ] [V] |
| Crear otro pendiente         | [ ] [V] | [ ] [V] | [ ] [V] |

- [ ] **Cobertura:** Al menos 3 celdas. [V] Pendiente correcto. Sin cruce de items entre pendientes.

### 12.4 Orden critico — Secuencias que suelen fallar

- [ ] **Secuencia 1:** Agregar item → Descuento 50% → Agregar otro item → [V] Descuento solo en item 1. Subtotal = item1*0.5 + item2.
- [ ] **Secuencia 2:** Descuento global 20% → Agregar items (sin desc ind). [V] Global aplicado al subtotal final.
- [ ] **Secuencia 3:** Cliente A → Agregar items → Cliente B → Agregar 1 mas → Cobrar. [V] Venta con Cliente B.
- [ ] **Secuencia 4:** Guardar pendiente → Cerrar turno (otra pestana) → Retomar pendiente → Cobrar. [V] Rechazo "no hay turno" o venta en nuevo turno segun regla.
- [ ] **Secuencia 5:** Mayoreo ON → Agregar producto mayoreo → Descuento ind 10% → [V] Descuento sobre precio mayoreo.
- [ ] **Secuencia 6:** Agregar 10 items → Quitar 5 (cualesquiera) → Descuento global 10% → [V] Global sobre subtotal de los 5 restantes.
- [ ] **Secuencia 7:** Abrir turno → F7 entrada $100 → Venta $50 efectivo → F8 retiro $30 → Cerrar. [V] Corte: esperado coherente con ventas y movimientos.
- [ ] **Secuencia 8:** Producto stock 1. Agregar. Otro usuario (otra pestana) vende esa unidad. Cobrar. [V] Rechazo stock insuficiente.
- [ ] **Secuencia 9:** Cobrar (efectivo, monto correcto) → Red cae antes de 200 → Reintentar cobro. [V] Una venta o error. No duplicado.
- [ ] **Secuencia 10:** F5 con modal de "Cerrar turno" abierto (monto ingresado). [V] Al recargar: turno cerrado o no; no estado corrupto.

### 12.5 Campos texto — Valores extremos por pantalla

**Terminal / Busqueda:** ya cubierto en 1.2 y 2.5. Añadir:
- [ ] **Pegar desde Excel (tabs, saltos):** [V] Tratado. No error.
- [ ] **Copiar-pegar nombre de producto con 200 chars:** En busqueda. [V] Resultados o vacio. No timeout.

**Productos (nombre, SKU):** ya en 3.1/3.6. Añadir:
- [ ] **Nombre con \r\n en medio:** [V] Rechazado o sanitizado. No multilinea en lista.
- [ ] **SKU solo numeros, solo letras, mixto, con guion bajo:** [V] Todos aceptados si validacion lo permite.

**Clientes (nombre, telefono, email):** [ ] Nombre 300 chars. [ ] Telefono con +52. [ ] Email max longitud. [V] No 500.

**Empleados:** [ ] Nombre 200 chars. [ ] Notas 1000 chars. [V] Persiste o truncado.

**Fiscal (RFC, CP, Uso):** [ ] RFC 12 chars, 13 chars. [ ] CP 5 chars, con letras. [ ] Uso invalido. [V] Validacion o mensaje. No 500.

**Gastos (motivo):** [ ] 500 caracteres. [ ] Solo emojis. [V] Aceptado o limite. No error.

### 12.6 Concurrencia exhaustiva — Quien gana

- [ ] **Dos tabs: mismo producto, stock 1. Ambas agregan 1. A cobra, B cobra 0.5 s despues.** [V] A OK. B rechazado. Stock 0.
- [ ] **Dos tabs: mismo producto, stock 5. A: 3 uds. B: 3 uds. A cobra, luego B.** [V] A OK. B rechazado (solo 2 quedan).
- [ ] **Tres tabs: mismo empleado. A abre turno. B intenta abrir turno (sin recargar).** [V] B: rechazado o "turno ya abierto". Un solo turno.
- [ ] **A: editar producto precio $100→$110. B: editar mismo producto nombre. Guardar A, guardar B (casi junto).** [V] Ultimo guardado gana o merge. No corrupcion (precio y nombre coherentes).
- [ ] **A: guardar pendiente. B: guardar pendiente. A: lista pendientes. B: lista pendientes.** [V] Ambas ven 2 pendientes. Al retomar cada uno ve su contenido.

### 12.7 Red y tiempo — Variantes exhaustivas

- [ ] **Cobrar → timeout 60 s (simular) → reintentar:** [V] Error o retry. Una venta. No duplicado.
- [ ] **Guardar pendiente offline → 3 ventas en otra pestana online → volver online, retomar y cobrar:** [V] Pendiente con datos correctos. Cobro OK.
- [ ] **Backend reinicia (kill + start) mientras busqueda en curso:** [V] Error en busqueda. Al reintentar, OK. No crash.
- [ ] **Backend reinicia mientras modal "Cerrar turno" esta abierto:** Cerrar. [V] Error o exito. Turno en estado coherente (cerrado o abierto).
- [ ] **Respuesta 502/503 en cobro (si se puede simular):** [V] Mensaje de error. Ticket intacto. Reintentar: una venta.

### 12.8 Numeros y redondeo — Casos que suelen fallar

- [ ] **Precios que suman mal por float:** $0.1 + $0.2 + $0.3 + … x10. [V] Total exacto (no 2.999999).
- [ ] **Descuento que deja sub-centavo:** $3.00 desc 33.33%. [V] Redondeado a 2 decimales (ej. $2.00). No $1.9999.
- [ ] **Multiplicacion grande:** $9999.99 x 100. [V] $999999.00. No overflow.
- [ ] **Cambio con muchos decimales intermedios:** Total $33.33. Recibido $100. [V] Cambio $66.67 exacto.
- [ ] **Suma 50 items de $0.01:** [V] Total $0.50. Cobro OK.
- [ ] **Suma 100 items mezclados (centavos variados):** [V] Total sin drift. Cuadre en auditoria.

### 12.9 UI y estado — Transiciones fragiles

- [ ] **Cambiar de tab (F2) mientras lista de productos carga:** [V] Al volver a Terminal, carrito intacto. No lista en Terminal.
- [ ] **Cobrar → inmediatamente F1 (antes de que cierre modal):** [V] Modal se cierra o F1 ignorado. No navegar con modal abierto.
- [ ] **Abrir F9 → escribir en busqueda de Terminal (focus robado):** [V] Focus en F9 o en Terminal. Comportamiento definido. No input en ambos.
- [ ] **Scroll en carrito con 50 items → agregar item 51:** [V] Nuevo item visible. Scroll no salta a cero si no debe.
- [ ] **Seleccionar pendiente de lista → retomar → lista sigue mostrando ese seleccionado:** [V] Contenido del pendiente cargado. No pendiente equivocado.
- [ ] **Settings: cambiar URL, no guardar, F1, Cancelar, cambiar otra cosa, F1, Aceptar:** [V] Sale sin guardar segunda vez. No dirty residual.

---

## Resumen de Cobertura V10 (exhaustivo)

| Fase | Tests (aprox) | Enfoque | Prioridad |
|------|----------------|---------|-----------|
| 0 | 14 | Regresion bugs V8 + edge | BLOCKER |
| 1 | 52 + **1.8–1.11** ~80 | Flujo critico + **matriz venta, orden, descuentos, campos numericos** | BLOCKER |
| 2 | 24 + **~15** | Integridad y seguridad + variantes stock/sesion/busqueda | ALTA |
| 3 | 32 + **3.6–3.8** ~25 | CRUD + **matrices producto, cliente, empleado, gastos** | ALTA |
| 4 | 18 | Navegacion, UX, config | MEDIA |
| 5 | 20 | Concurrencia + variantes | ALTA |
| 6 | 10 | Resiliencia de red + edge | ALTA |
| 7 | 12 | Estres y volumen + variantes | MEDIA |
| 8 | 14 | Caos + edge | MEDIA |
| 9 | 14 | Fiscal + edge | MEDIA |
| 10 | 8 | Auditoria final | ALTA |
| 11 | 22 + **11.8** ~37 | **Monkey testing** + variantes exhaustivas | ALTA |
| **12** | **~55** | **Matrices exhaustivas, orden, concurrencia, red, redondeo, UI** | ALTA |
| **Total** | **~379+** | Cobertura exhaustiva para detectar fallos | |

### Cambios respecto a V9 (~161 tests)

1. **+218+ tests / variantes / edge / matrices:** Criterios por fase ampliados. Etiquetas EDGE, VARIANTE, MATRIZ, ORDEN.
2. **Criterios mas estrictos:** [V-] para "no debe ocurrir". Referencias explicitas a "una sola venta", "0 duplicados", "sin crash".
3. **Fase 1 ampliada (1.8–1.11):**
   - **1.8 Matriz exhaustiva venta:** Metodo × Cliente × Descuento × Tipo ticket (~23 variantes).
   - **1.9 Orden de operaciones:** 10 secuencias (cliente antes/despues, desc antes/despues, F9, red, etc.).
   - **1.10 Matriz descuentos:** 0%, 0.01%, 1%, 10%, 33.33%, 50%, 99%, 99.99%, 100% individual y global; compuesto; varias lineas.
   - **1.11 Campos numericos extremos:** Monto recibido (0, negativo, 3 decimales, 1e5), cantidad (0, 9999, negativo, texto), descuento (100.01, 200, -5), fondo y contado (0, 0.01, negativo, 1e6).
4. **Fase 2:** Mas variantes stock (quien cobra primero), producto desactivado/cliente eliminado con ticket abierto, busqueda longitud 1/2/50/200/1000 y solo espacios.
5. **Fase 3:** Subsecciones 3.6–3.8 matrices producto (SKU+nombre, precio+stock, mayoreo), cliente (duplicados, telefono, email), empleado (salario, comision, codigo espacios), gastos (monto negativo, muy grande, motivo largo).
6. **Fase 11.8:** +15 variantes monkey (cobrar vacio, F1–F6 inverso, modales encima, pegar 10x, alternar A/B/A/B, cerrar navegador con modal, doble CFDI, multi-pestana cerrar vs cobrar).
7. **Fase 12 — Variantes exhaustivas (nueva):**
   - 12.1 Matriz Metodo × Momento cliente (tabla 3×3).
   - 12.2 Matriz Descuento × Cantidad items (tabla 5×3).
   - 12.3 Matriz Pendiente × Accion posterior (tabla 4×3).
   - 12.4 Orden critico: 10 secuencias que suelen fallar.
   - 12.5 Campos texto extremos por pantalla (busqueda, productos, clientes, empleados, fiscal, gastos).
   - 12.6 Concurrencia exhaustiva (stock 1/5, dos tabs mismo producto, editar mismo producto, pendientes).
   - 12.7 Red y tiempo (timeout, offline/online, backend reinicia, 502/503).
   - 12.8 Numeros y redondeo (float, sub-centavo, overflow, cambio decimales).
   - 12.9 UI y estado (cambiar tab durante carga, F1 durante cobro, focus, scroll, pendientes, settings dirty).
8. **Tiempos estimados:** Fase 1 ~70 min, Fase 12 muestreo 60 min / completo 120 min. Sesion completa exhaustiva: **~4–6 h** (muestreo) a **~8–10 h** (completo).
