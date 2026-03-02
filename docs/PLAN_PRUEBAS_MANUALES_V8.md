# Plan de Pruebas Manuales V8 — TITAN POS

Guia completa de pruebas manuales: regresion, escenarios cotidianos de retail mexicano, volumen, concurrencia, caos destructivo, matematicas de descuentos y facturacion SAT.

**Regla de oro:** Todo se ejecuta 100% manual en el navegador. Sin scripts, sin inyeccion directa a la DB.

**Nota sobre precios:** El backend asume `price_includes_tax=True` por defecto. Un producto con precio $116.00 tiene base $100.00 + IVA $16.00. Los descuentos se ajustan dividiendo entre 1.16 antes de calcular.

---

## FASE 1: Regresion de Bugs V7

Validar que los 4 bugs corregidos no regresan.

### 1.1 Empleados — Guardar funciona

- [ ] **Crear empleado con comision:**
  1. Ir a Empleados.
  2. Codigo: `EMP-001`, Nombre: `Juan Perez`, Posicion: `Cajero`, Salario: `8500`, Comision: `10`, Telefono: `5551234567`.
  3. Clic en Guardar.
  4. **Verificar:** Empleado aparece en la tabla. Seleccionarlo y confirmar que el campo Comision muestra `10.00` (no `0.10`).
- [ ] **Codigo vacio bloqueado:**
  1. Limpiar formulario con "Nuevo".
  2. Dejar Codigo vacio, poner Nombre: `Test`.
  3. **Verificar:** Boton Guardar esta deshabilitado (gris). Si se fuerza, el mensaje dice "Codigo de empleado es obligatorio."
- [ ] **Comision se guarda como decimal en DB:**
  1. Crear empleado con Comision `15`.
  2. Recargar la pagina (F5 real del navegador).
  3. Ir a Empleados, hacer clic en Cargar.
  4. Seleccionar el empleado creado.
  5. **Verificar:** El campo Comision muestra `15.00`, no `0.15` ni `1500`.
- [ ] **Comision 0% — comisionista sin comision:**
  1. Crear empleado con Comision `0`.
  2. Recargar, seleccionar. **Verificar:** Muestra `0.00`.
- [ ] **Comision 100% — valor limite:**
  1. Crear empleado con Comision `100`.
  2. Recargar, seleccionar. **Verificar:** Muestra `100.00`. Backend almacena `1.00`.
- [ ] **Comision con decimales — 7.5%:**
  1. Crear empleado con Comision `7.5`.
  2. Recargar, seleccionar. **Verificar:** Muestra `7.50`.
- [ ] **Editar comision existente:**
  1. Seleccionar empleado con comision 10%. Cambiar a 12.5%.
  2. Clic Actualizar. Recargar. Seleccionar.
  3. **Verificar:** Muestra `12.50`.
- [ ] **Empleado con todos los campos vacios excepto obligatorios:**
  1. Solo Codigo `EMP-MIN` y Nombre `Minimo`. Todo lo demas vacio.
  2. Guardar. **Verificar:** Se crea. Comision default es 0, salario default es 0.
- [ ] **Notas de empleado persisten:**
  1. Crear empleado con notas: `Trabaja lunes a viernes, horario 9-6`.
  2. Recargar, seleccionar. **Verificar:** Notas aparecen completas.

### 1.2 Clientes — Sin duplicados

- [ ] **Duplicado local bloqueado:**
  1. Ir a Clientes. Crear cliente: `Maria Lopez`, tel: `5559876543`.
  2. Guardar exitosamente.
  3. Limpiar con "Nuevo". Escribir `maria lopez` (minusculas).
  4. Clic en Guardar.
  5. **Verificar:** Mensaje de error "Ya existe un cliente con el nombre..." SIN hacer request al backend.
- [ ] **Duplicado backend bloqueado (409):**
  1. Abrir segunda pestana. Crear cliente `Carlos Ramirez` en Pestana A.
  2. Sin recargar Pestana B, intentar crear `Carlos Ramirez` en Pestana B.
  3. **Verificar:** Backend responde 409 y muestra error en UI.
- [ ] **Cliente persiste tras recarga:**
  1. Crear cliente `Ana Torres`.
  2. Cerrar pestana completamente. Abrir nueva pestana, loguearse, ir a Clientes.
  3. **Verificar:** `Ana Torres` aparece en la lista. No desaparecio como antes (bug del sync con IDs string).
- [ ] **Duplicado con espacios extra:**
  1. Crear `Roberto Diaz`. Luego intentar crear `  Roberto   Diaz  ` (con espacios).
  2. **Verificar:** Detectado como duplicado (TRIM + LOWER).
- [ ] **Duplicado con acentos (si aplica):**
  1. Crear `Jose Garcia`. Intentar crear `José García`.
  2. **Verificar:** Comportamiento consistente (ambos se aceptan o se detecta duplicado).
- [ ] **Cliente con solo nombre (sin tel/email):**
  1. Crear `Publico Especial` sin telefono ni email.
  2. **Verificar:** Se crea correctamente. Campos opcionales quedan vacios.
- [ ] **Editar cliente existente:**
  1. Seleccionar cliente. Cambiar telefono. Clic Actualizar.
  2. Recargar. Seleccionar. **Verificar:** Telefono actualizado persiste.

### 1.3 Contador de turno — Multi-terminal

- [ ] **Badge se actualiza por polling:**
  1. Abrir 2 pestanas con el mismo turno abierto.
  2. En Pestana A, realizar 3 ventas rapidas.
  3. En Pestana B, esperar 60-70 segundos sin hacer nada.
  4. **Verificar:** El badge "X ventas / $Y.YY" en Pestana B se actualiza automaticamente reflejando las 3 ventas de Pestana A.
- [ ] **Polling no ejecuta sin turno:**
  1. Abrir app sin turno abierto. Esperar 2 minutos.
  2. Abrir DevTools > Network.
  3. **Verificar:** No se hacen llamadas repetidas a `getTurnSummary` sin turno.
- [ ] **Badge refleja montos correctos tras polling:**
  1. Pestana A: venta de $100, venta de $250, venta de $75.
  2. Pestana B espera 60s.
  3. **Verificar:** Badge en B muestra `3 ventas / $425.00` (exacto).
- [ ] **Disaster recovery inicializa con conteos reales:**
  1. Abrir turno. Hacer 5 ventas ($50 cada una = $250 total).
  2. `localStorage.removeItem('titan.currentShift')`. Recargar.
  3. **Verificar:** Al recuperar turno, badge muestra `5 ventas / $250.00` (no `0 / $0`).

### 1.4 Dirty state — Settings y Hardware

- [ ] **Settings bloquea navegacion con F-keys:**
  1. Ir a Configuraciones. Cambiar el Base URL a `http://localhost:9999`.
  2. NO guardar. Presionar F1 (Terminal).
  3. **Verificar:** Aparece dialogo "Tienes cambios sin guardar. ¿Deseas salir sin guardar?"
  4. Cancelar. Confirmar que sigues en Configuraciones.
  5. Presionar F1 de nuevo. Aceptar salir.
  6. Volver a Configuraciones. **Verificar:** URL es la original, no `9999`.
- [ ] **Settings — guardar limpia dirty flag:**
  1. Cambiar Token a `abc123`. Presionar Guardar.
  2. Presionar F1. **Verificar:** NO aparece dialogo (cambios guardados, dirty=false).
- [ ] **Settings — cambiar y revertir manualmente:**
  1. URL original: `http://localhost:8000`. Cambiar a `http://localhost:9999`.
  2. Cambiar de nuevo a `http://localhost:8000` (valor original).
  3. Presionar F1. **Verificar:** NO aparece dialogo (form === savedForm).
- [ ] **Hardware bloquea navegacion:**
  1. Ir a Hardware. Cambiar nombre de impresora a `PRUEBA_DIRTY`.
  2. Sin guardar, presionar F2 (Clientes).
  3. **Verificar:** Aparece dialogo de confirmacion.
- [ ] **Hardware — guardar limpia dirty flag:**
  1. Cambiar nombre de negocio. Guardar.
  2. Navegar a otra tab. **Verificar:** No aparece dialogo.
- [ ] **beforeunload — cerrar pestana con cambios:**
  1. Ir a Configuraciones. Cambiar algo. NO guardar.
  2. Intentar cerrar la pestana (Ctrl+W).
  3. **Verificar:** Navegador muestra advertencia nativa de "cambios sin guardar".

---

## FASE 2: Escenarios Cotidianos de Retail Mexicano

Simulaciones de lo que pasa todos los dias en una tienda real. Cada escenario debe ejecutarse completo sin atajos.

### 2.1 La Manana del Lunes — Apertura de Tienda

- [ ] **Abrir turno con fondo de caja:**
  1. Login como cajero. El modal de turno aparece.
  2. Ingresar fondo inicial: `$2,500.00`. Abrir turno.
  3. **Verificar:** Badge de turno muestra operador y 0 ventas / $0.00.
- [ ] **Fondo de caja con centavos:**
  1. Abrir turno con fondo `$2,500.50`.
  2. **Verificar:** Fondo registrado correctamente con centavos.
- [ ] **Primera venta del dia — Cliente con billete de $500:**
  1. Buscar "Coca Cola 600ml" (o producto existente). Agregar 2 unidades.
  2. Pago: Efectivo. Monto recibido: `500`.
  3. Cobrar.
  4. **Verificar:** Mensaje muestra cambio correcto. Badge: 1 venta.
- [ ] **Cliente paga con tarjeta:**
  1. Agregar 3 productos variados al carrito.
  2. Cambiar metodo de pago a "Tarjeta".
  3. Cobrar.
  4. **Verificar:** No pide monto recibido (no aplica cambio). Venta registrada.
- [ ] **Cliente paga por transferencia:**
  1. Venta con 1 producto. Metodo: Transferencia.
  2. Cobrar.
  3. **Verificar:** Venta registrada correctamente con metodo `transfer`.
- [ ] **Venta de pago exacto en efectivo:**
  1. Total de venta: $58.00. Monto recibido: $58.00.
  2. Cobrar. **Verificar:** Cambio = $0.00. Venta exitosa.
- [ ] **Cliente no tiene cambio — billete de $1000 para compra de $35:**
  1. Producto de $35. Monto recibido: $1000.
  2. **Verificar:** Cambio mostrado: $965.00.

### 2.2 Hora Pico — Flujo Rapido de Clientes

- [ ] **10 ventas consecutivas en menos de 5 minutos:**
  1. Ejecutar 10 ventas seguidas de 1-3 productos cada una.
  2. Alternar: 5 efectivo, 3 tarjeta, 2 transferencia.
  3. En ventas de efectivo, usar montos variados: exacto en unas, billete grande en otras.
  4. **Verificar:** No hay lag acumulado. Cada venta limpia el carrito instantaneamente. Badge se actualiza en cada cobro.
- [ ] **Cliente indeciso — Agregar y quitar productos:**
  1. Agregar 5 productos al carrito.
  2. El "cliente" cambia de opinion: quitar 2 productos.
  3. Agregar 1 producto diferente.
  4. Cambiar cantidad de otro a 3 unidades.
  5. Cobrar normalmente.
  6. **Verificar:** Totales se recalculan correctamente en cada modificacion. El ticket final solo tiene los items correctos.
- [ ] **Agregar mismo producto multiples veces:**
  1. Buscar `Coca Cola`. Agregar al carrito.
  2. Sin cambiar cantidad, buscar `Coca Cola` y agregar de nuevo.
  3. **Verificar:** La cantidad se incrementa (2 unidades del mismo item), no se crea linea duplicada.
- [ ] **Ventas consecutivas sin pausar — 5 ventas en 60 segundos:**
  1. Venta 1: 1 producto, efectivo exacto. Cobrar.
  2. Inmediatamente venta 2: 1 producto, tarjeta. Cobrar.
  3. Repetir hasta 5 ventas.
  4. **Verificar:** Cada cobro limpia carrito. Folios consecutivos. Badge = 5.

### 2.3 Descuento Individual por Producto — Matematicas

- [ ] **Descuento 10% a un solo producto:**
  1. Producto A: $100.00 x 1 unidad. Aplicar descuento individual 10%.
  2. **Verificar en pantalla:** Subtotal item = $90.00.
  3. Cobrar. Revisar historial.
  4. **Verificar backend:** Descuento calculado: $100 * 0.10 = $10. Base gravable (si IVA incluido): $90/1.16 = $77.59. IVA: $12.41. Total: $90.00.
- [ ] **Descuento 25% a producto de $200:**
  1. Producto: $200.00 x 1 unidad. Descuento individual 25%.
  2. **Verificar:** Subtotal = $150.00. Descuento = $50.00.
- [ ] **Descuento individual con multiples unidades:**
  1. Producto: $80.00 x 3 unidades. Descuento individual 15%.
  2. **Verificar:** Precio total sin desc = $240. Descuento = $36. Subtotal = $204.00.
- [ ] **Descuento 0% (sin descuento explicito):**
  1. Agregar producto $150 sin descuento.
  2. **Verificar:** Subtotal = $150.00. Campo descuento muestra 0%.
- [ ] **Descuento 50% — mitad de precio:**
  1. Producto $500 x 1 unidad. Descuento 50%.
  2. **Verificar:** Subtotal = $250.00.
- [ ] **Descuento solo a 1 de 3 productos:**
  1. Producto A: $100 (sin descuento). Producto B: $200 (descuento 20% = $160). Producto C: $50 (sin descuento).
  2. **Verificar:** Total = $100 + $160 + $50 = $310.00.
- [ ] **Descuentos diferentes por producto:**
  1. A: $100, 10% desc = $90. B: $200, 25% desc = $150. C: $300, 5% desc = $285.
  2. **Verificar:** Total = $90 + $150 + $285 = $525.00.
- [ ] **Descuento que genera centavos — 33%:**
  1. Producto $100 x 1. Descuento 33%.
  2. **Verificar:** Subtotal = $67.00 (redondeo consistente, no $66.999...).
- [ ] **Descuento a producto con precio con centavos:**
  1. Producto $99.99 x 1. Descuento 10%.
  2. **Verificar:** Subtotal = $89.99 (redondeado correctamente).

### 2.4 Descuento Global al Ticket — Matematicas

- [ ] **Descuento global 5% a ticket simple:**
  1. Agregar 3 productos: $100, $200, $50. Subtotal = $350.
  2. Aplicar descuento global 5%.
  3. **Verificar:** Descuento = $17.50. Total = $332.50.
- [ ] **Descuento global 10% a ticket de 5 productos:**
  1. Productos: $80, $120, $45, $200, $55. Subtotal = $500.
  2. Descuento global 10%.
  3. **Verificar:** Total = $450.00. Descuento = $50.00.
- [ ] **Descuento global 15% con centavos problematicos:**
  1. Productos: $33.33, $66.67, $100.00. Subtotal = $200.00.
  2. Descuento global 15%.
  3. **Verificar:** Total = $170.00. Sin error de punto flotante.
- [ ] **Descuento global 0% (sin descuento):**
  1. 2 productos: $100, $100. Descuento global 0%.
  2. **Verificar:** Total = $200.00. Identico a no aplicar descuento.
- [ ] **Descuento global 100% — todo gratis:**
  1. 1 producto $100. Descuento global 100%.
  2. **Verificar:** Total = $0.00. El sistema acepta o rechaza (verificar politica).
- [ ] **Descuento global sobre ticket ya con descuentos individuales (compuesto):**
  1. A: $100 con 10% individual = $90. B: $200 sin descuento. Subtotal = $290.
  2. Descuento global 5% sobre $290.
  3. **Verificar:** Descuento global = $14.50. Total final = $275.50.
  4. **Matematica:** El descuento global se aplica SOBRE el subtotal ya descontado, no sobre el precio original.
- [ ] **Doble descuento pesado — individual 30% + global 20%:**
  1. Producto $1000. Desc individual 30% = $700.
  2. Desc global 20% = $700 * 0.80 = $560.
  3. **Verificar:** Total = $560.00. Descuento total efectivo = 44% (no 50%).

### 2.5 El Cliente Frecuente — Gestion de Clientes en Venta

- [ ] **Asignar cliente a una venta:**
  1. En Terminal, cambiar el nombre de cliente de "Publico General" a un cliente registrado.
  2. Agregar productos y cobrar.
  3. Ir a Historial. Buscar la venta por folio.
  4. **Verificar:** La venta tiene el nombre del cliente asignado, no "Publico General".
- [ ] **Consultar credito de cliente:**
  1. Ir a Clientes. Seleccionar un cliente existente.
  2. Clic en "Credito".
  3. **Verificar:** Se muestran: Limite, Balance, Disponible. Los numeros son coherentes (Disponible = Limite - Balance).
- [ ] **Consultar historial de compras:**
  1. Con un cliente seleccionado, clic en "Ventas".
  2. **Verificar:** Se muestra tabla con Folio, Total, Metodo, Fecha. Las ventas asignadas a ese cliente aparecen.
- [ ] **Cambiar cliente a mitad de captura:**
  1. Seleccionar cliente `Maria Lopez`. Agregar 2 productos.
  2. Cambiar a cliente `Carlos Ramirez`.
  3. Cobrar. Revisar en historial.
  4. **Verificar:** Venta asignada a `Carlos Ramirez`, no a `Maria Lopez`.

### 2.6 Gestion de Inventario en el Dia

- [ ] **Llega mercancia — Entrada de inventario:**
  1. Ir a Inventario (F4). Seleccionar un producto existente.
  2. Registrar entrada: +24 unidades.
  3. **Verificar:** Stock actualizado inmediatamente en la lista.
  4. Ir a Terminal (F1), buscar el producto. **Verificar:** Stock refleja las 24 unidades adicionales.
- [ ] **Producto danado — Registrar merma:**
  1. Ir a Inventario. Seleccionar producto con stock > 5.
  2. Registrar salida tipo "Merma": 2 unidades.
  3. Ir a Mermas. **Verificar:** La merma aparece como pendiente de aprobacion.
- [ ] **Crear producto nuevo sobre la marcha:**
  1. Ir a Productos (F3).
  2. Crear: SKU `CHOC-001`, Nombre `Chocolate Abuelita 90g`, Precio `$28.00`, Stock `50`.
  3. Guardar.
  4. Ir a Terminal (F1). Buscar `CHOC`. **Verificar:** El producto aparece y se puede agregar al carrito.
- [ ] **Entrada de inventario masiva — 5 productos:**
  1. Registrar entradas: Prod A +50, Prod B +100, Prod C +25, Prod D +75, Prod E +30.
  2. **Verificar:** Todos los stocks actualizados correctamente.
- [ ] **Ajuste de stock a 0:**
  1. Producto con 10 unidades. Registrar salida de 10.
  2. **Verificar:** Stock = 0. Intentar vender. **Verificar:** Rechazado por stock insuficiente.

### 2.7 Operaciones de Productos — CRUD Completo

- [ ] **Crear producto basico:**
  1. Ir a Productos. SKU: `AGUA-001`, Nombre: `Agua Purificada 1L`, Precio: `$15.00`, Stock: `100`.
  2. Guardar. **Verificar:** Aparece en lista.
- [ ] **Crear producto con precio mayoreo:**
  1. SKU: `JABON-001`, Nombre: `Jabon Zote 400g`, Precio: `$25.00`, Precio Mayoreo: `$20.00`.
  2. Guardar. Ir a Terminal. Activar Mayoreo. Buscar `Jabon Zote`.
  3. **Verificar:** Precio mostrado = $20.00 (mayoreo). Desactivar mayoreo: precio = $25.00.
- [ ] **Crear producto sin precio mayoreo:**
  1. SKU: `LECHE-001`, Nombre: `Leche Entera 1L`, Precio: `$28.00`, Mayoreo: vacio.
  2. Guardar. Activar Mayoreo en Terminal. Buscar.
  3. **Verificar:** Usa precio normal $28.00 (fallback cuando mayoreo = 0).
- [ ] **Editar precio de producto:**
  1. Seleccionar producto existente. Cambiar precio de $100 a $120.
  2. Guardar. Ir a Terminal. Buscar producto.
  3. **Verificar:** Precio actualizado a $120.
- [ ] **Editar SKU de producto:**
  1. Cambiar SKU de `AGUA-001` a `AGUA-PUR-001`.
  2. Guardar. Buscar por nuevo SKU. **Verificar:** Encontrado.
  3. Buscar por SKU viejo. **Verificar:** No encontrado.
- [ ] **Producto con precio 0.01 (minimo):**
  1. Crear producto con precio $0.01. Stock 100.
  2. Vender 5 unidades. **Verificar:** Total = $0.05.
- [ ] **Producto con precio alto — $99,999.99:**
  1. Crear producto con precio $99,999.99.
  2. Vender 1 unidad. **Verificar:** Total correcto sin overflow.
- [ ] **Producto con nombre de 150+ caracteres:**
  1. Nombre: `Tornillo Autorroscante Cabeza Avellanada Phillips Acero Inoxidable 304 Medida 1/4 x 2 Pulgadas Caja 100 Piezas Marca Truper`.
  2. **Verificar:** Se crea. En la Terminal aparece truncado pero legible.
- [ ] **Producto con SKU con caracteres especiales:**
  1. Crear con SKU `TORN-1/4x2`. **Verificar:** Se acepta.
  2. Crear con SKU `P&G-001`. **Verificar:** Funciona correctamente.
- [ ] **Desactivar producto:**
  1. Desactivar un producto existente.
  2. **Verificar:** No aparece en busquedas de Terminal. Sigue visible en Productos (filtrado).
- [ ] **Producto con stock negativo (proteccion):**
  1. Producto con 5 unidades. Intentar vender 10.
  2. **Verificar:** Backend rechaza. Stock nunca llega a negativo.
- [ ] **Producto comun (sin ID en DB):**
  1. Si existe opcion de "producto comun", crear una venta con producto generico.
  2. **Verificar:** Se registra correctamente sin `product_id`.

### 2.8 Claves SAT en Productos

- [ ] **Producto con clave SAT default (01010101):**
  1. Crear producto sin especificar clave SAT.
  2. **Verificar:** En DB/API, `sat_clave_prod_serv = '01010101'` (No existe en catalogo SAT).
  3. **Verificar:** `sat_clave_unidad = 'H87'` (Pieza).
- [ ] **Asignar clave SAT especifica — Alimentos:**
  1. Crear producto `Galletas Maria`. Clave SAT: `50181700` (Galletas).
  2. Guardar. Seleccionar. **Verificar:** Clave SAT persiste como `50181700`.
- [ ] **Asignar clave SAT — Bebidas no alcoholicas:**
  1. Producto: `Refresco Cola 2L`. Clave: `50202300` (Refrescos).
  2. **Verificar:** Clave correcta en el producto.
- [ ] **Asignar clave SAT — Articulos de limpieza:**
  1. Producto: `Cloro 1L`. Clave: `47131800` (Limpiadores).
  2. **Verificar:** Clave persiste.
- [ ] **Asignar clave SAT — Papeleria:**
  1. Producto: `Cuaderno 100 hojas`. Clave: `14111500` (Papel).
  2. **Verificar:** Correcto.
- [ ] **Cambiar clave SAT de producto existente:**
  1. Producto con default `01010101`. Editar a `50181700`.
  2. Guardar. **Verificar:** Clave actualizada.
- [ ] **Clave SAT se copia a sale_items al vender:**
  1. Producto con clave `50202300`. Vender 2 unidades.
  2. Consultar en historial/API el detalle de la venta.
  3. **Verificar:** `sale_items.sat_clave_prod_serv = '50202300'`.
- [ ] **Producto con clave_unidad diferente:**
  1. Producto a granel: `Frijol Negro`. Clave unidad: `KGM` (Kilogramo) en vez de `H87`.
  2. **Verificar:** Clave unidad persiste como `KGM`.
- [ ] **Validar que clave SAT invalida se rechaza o advierte:**
  1. Intentar guardar producto con clave SAT `99999999` (no existe en catalogo).
  2. **Verificar:** El sistema advierte o acepta (verificar politica — algunos sistemas aceptan cualquier 8 digitos).

### 2.9 Movimientos de Caja — F7 y F8

- [ ] **Entrada de efectivo (F7) — Proveedor paga:**
  1. Presionar F7. Monto: `1500`. Motivo: `Pago proveedor tortillas`.
  2. Registrar.
  3. **Verificar:** Mensaje de exito. Cajon se abre (si esta habilitado).
- [ ] **Retiro de efectivo (F8) — Pago a proveedor:**
  1. Presionar F8. Monto: `800`. Motivo: `Pago a repartidor de refrescos`.
  2. Registrar.
  3. **Verificar:** Movimiento registrado exitosamente.
- [ ] **Movimiento con PIN de gerente:**
  1. Presionar F8. Monto: `5000`. Motivo: `Retiro para deposito bancario`. PIN: (ingresar PIN valido).
  2. **Verificar:** Movimiento aceptado.
  3. Repetir con PIN incorrecto. **Verificar:** Rechazado.
- [ ] **Entrada de centavos (F7):**
  1. Monto: `$1,234.56`. Motivo: `Ajuste de caja`.
  2. **Verificar:** Monto registrado con centavos exactos.
- [ ] **Retiro que excede caja (si hay validacion):**
  1. Intentar F8 con monto mayor al efectivo en caja.
  2. **Verificar:** Rechazado o advertencia.
- [ ] **5 movimientos consecutivos:**
  1. F7 $500, F8 $200, F7 $300, F8 $100, F7 $1000.
  2. **Verificar:** Balance neto = +$1,500 en movimientos. Todos registrados en orden.

### 2.10 Verificador de Precios — F9

- [ ] **Consulta rapida sin afectar el carrito:**
  1. Con un ticket a medio capturar (3 items en carrito), presionar F9.
  2. Buscar un producto por nombre. **Verificar:** Muestra precio, precio mayoreo (si existe) y stock.
  3. Cerrar el verificador (Esc).
  4. **Verificar:** El carrito sigue intacto con los 3 items originales.
- [ ] **F9 con carrito vacio:**
  1. Sin items en carrito. F9. Buscar producto.
  2. **Verificar:** Funciona igual. Cerrar. Carrito sigue vacio.
- [ ] **F9 buscar producto sin stock:**
  1. F9. Buscar producto con stock 0.
  2. **Verificar:** Muestra precio y stock = 0.
- [ ] **Abrir y cerrar F9 repetidamente:**
  1. F9 abrir, Esc cerrar. Repetir 10 veces rapido.
  2. **Verificar:** Sin leak de modales. Abre/cierra limpiamente.

### 2.11 Tickets Pendientes — El Cliente que "Ahorita Regreso"

- [ ] **Pausar y retomar ticket:**
  1. En Terminal, agregar 5 productos al carrito.
  2. Crear nuevo ticket (Ctrl+N o boton de nuevo ticket).
  3. **Verificar:** El carrito se limpia para un nuevo ticket.
  4. Hacer una venta rapida con el nuevo ticket.
  5. Volver al ticket pendiente. **Verificar:** Los 5 productos originales siguen ahi.
  6. Cobrar el ticket pendiente. **Verificar:** Venta registrada correctamente.
- [ ] **Multiples tickets pendientes (hasta 8):**
  1. Crear 4 tickets pendientes con diferentes productos cada uno.
  2. Navegar entre ellos. **Verificar:** Cada ticket conserva su carrito, cliente y metodo de pago.
  3. Cobrar todos en orden inverso (del 4 al 1). **Verificar:** Todos se registran correctamente.
- [ ] **Ticket pendiente con descuento individual:**
  1. Ticket con 3 items, item 2 tiene 15% descuento. Pausar.
  2. Hacer otra venta. Retomar ticket pendiente.
  3. **Verificar:** El descuento del 15% sigue aplicado al item 2.
- [ ] **Ticket pendiente con descuento global:**
  1. Ticket con descuento global 10%. Pausar. Retomar.
  2. **Verificar:** Descuento global sigue aplicado. Totales correctos.
- [ ] **Ticket pendiente con cliente asignado:**
  1. Asignar `Maria Lopez` a ticket. Agregar items. Pausar.
  2. Retomar. **Verificar:** Cliente sigue siendo `Maria Lopez`.

### 2.12 Modo Mayoreo

- [ ] **Activar modo mayoreo:**
  1. En Terminal, activar el toggle de Mayoreo.
  2. Agregar un producto que tenga precio mayoreo definido.
  3. **Verificar:** El precio mostrado es el de mayoreo, no el retail.
  4. Cobrar. **Verificar:** Total usa precios de mayoreo.
  5. Desactivar mayoreo. Agregar el mismo producto. **Verificar:** Vuelve al precio normal.
- [ ] **Mayoreo con descuento individual:**
  1. Producto: precio retail $100, mayoreo $80. Activar mayoreo.
  2. Agregar. Aplicar 10% descuento.
  3. **Verificar:** Subtotal = $80 * 0.90 = $72.00. Descuento sobre precio mayoreo.
- [ ] **Mayoreo con descuento global:**
  1. 3 productos en mayoreo: $80, $60, $40. Subtotal = $180.
  2. Descuento global 5%.
  3. **Verificar:** Total = $171.00.
- [ ] **Producto sin precio mayoreo en modo mayoreo:**
  1. Activar mayoreo. Agregar producto sin mayoreo definido.
  2. **Verificar:** Usa precio normal como fallback.

### 2.13 Consulta de Historial y Reportes

- [ ] **Buscar venta por folio:**
  1. Ir a Historial. Ingresar un folio conocido.
  2. **Verificar:** Se muestra la venta con todos sus detalles.
- [ ] **Filtrar ventas por rango de fecha:**
  1. Filtrar ventas del dia de hoy.
  2. **Verificar:** Solo aparecen ventas de hoy. El conteo coincide con el badge del turno.
- [ ] **Reporte diario:**
  1. Ir a Reportes (F6). Generar reporte del dia.
  2. **Verificar:** Total de ventas, promedio por ticket, desglose por metodo de pago. Los numeros cuadran con las ventas hechas.
- [ ] **Verificar descuentos en historial:**
  1. Hacer venta con descuento individual 20% en producto de $500 (= $400).
  2. Ir a Historial. Buscar por folio.
  3. **Verificar:** El detalle muestra descuento = $100. Subtotal = $400.
- [ ] **Verificar metodo de pago en historial:**
  1. Hacer 3 ventas: una efectivo, una tarjeta, una transferencia.
  2. **Verificar en historial:** Cada una muestra el metodo correcto.

### 2.14 Gestion de Empleados — Ciclo Completo

- [ ] **CRUD completo de empleado:**
  1. Crear: Codigo `EMP-TEST`, Nombre `Prueba QA`, Posicion `Auxiliar`, Salario `7000`, Comision `5`.
  2. Seleccionar y editar: Cambiar salario a `7500`. Clic Actualizar. **Verificar:** Cambio reflejado.
  3. Eliminar: Clic Eliminar. Confirmar. **Verificar:** Desaparece de la lista.
  4. Recargar pagina. **Verificar:** El empleado eliminado NO reaparece.

### 2.15 Gastos Operativos

- [ ] **Registrar gasto:**
  1. Ir a Gastos. Registrar: Monto `$350.00`, Descripcion: `Compra de papel para tickets`.
  2. **Verificar:** Gasto aparece en el listado con timestamp correcto.
- [ ] **Gasto invalido rechazado:**
  1. Intentar registrar gasto con monto `0`. **Verificar:** Rechazado (422).
  2. Intentar con descripcion vacia. **Verificar:** Rechazado.
- [ ] **Gasto con centavos:**
  1. Monto: $123.45. Descripcion: `Compra de bolsas`.
  2. **Verificar:** Centavos registrados correctamente.

### 2.16 Hardware — Configuracion de Impresora y Cajon

- [ ] **Detectar impresoras:**
  1. Ir a Hardware. Clic "Detectar Impresoras".
  2. **Verificar:** Lista de impresoras disponibles se llena.
- [ ] **Imprimir ticket de prueba:**
  1. Seleccionar impresora. Clic "Imprimir Prueba".
  2. **Verificar:** Mensaje de exito (independiente de si hay impresora fisica).
- [ ] **Configurar datos del negocio:**
  1. Ir a seccion Negocio. Cambiar nombre a `Mi Tienda QA`.
  2. Guardar. Recargar pagina. Ir a Hardware > Negocio.
  3. **Verificar:** El nombre persiste como `Mi Tienda QA`.

---

## FASE 3: Escenarios Complejos del Dia a Dia

Situaciones que ocurren inevitablemente y que el cajero debe poder manejar sin llamar al programador.

### 3.1 El Cliente con Problemas de Pago

- [ ] **Efectivo insuficiente:**
  1. Total de venta: $250. Monto recibido: $200.
  2. **Verificar:** Mensaje "Monto insuficiente. Falta: $50.00". Venta NO se procesa.
- [ ] **Cliente cambia de metodo de pago a ultimo momento:**
  1. Cargar carrito con productos. Seleccionar Efectivo.
  2. Antes de cobrar, cambiar a Tarjeta.
  3. Cobrar. **Verificar:** Venta registrada como Tarjeta.
- [ ] **Pago exacto (sin ingresar monto):**
  1. Cargar venta. Metodo: Efectivo. Dejar monto recibido en 0 o vacio.
  2. Cobrar. **Verificar:** Sistema asume pago exacto. Cambio: $0.00.
- [ ] **Monto recibido con centavos:**
  1. Total: $187.50. Monto recibido: $200.00.
  2. **Verificar:** Cambio = $12.50.
- [ ] **Monto recibido exacto con centavos:**
  1. Total: $187.53. Monto recibido: $187.53.
  2. **Verificar:** Cambio = $0.00.

### 3.2 El Producto que No Existe

- [ ] **Buscar producto inexistente:**
  1. En Terminal, buscar `XYZNOEXISTE999`. **Verificar:** Lista vacia, sin errores.
- [ ] **Verificador de precios — Producto no encontrado:**
  1. F9. Buscar `zzzzzz`. **Verificar:** "Sin resultados" sin errores.
- [ ] **Escanear SKU inexistente (simulado):**
  1. En el campo de busqueda, pegar un codigo largo tipo `7501234567890`.
  2. **Verificar:** Si no existe, lista vacia. Sin crash.
- [ ] **Buscar con un solo caracter:**
  1. Buscar `a`. **Verificar:** Retorna resultados (todos los que contienen 'a'). Sin timeout.
- [ ] **Buscar con caracteres especiales:**
  1. Buscar `%`, `_`, `'`, `"`. **Verificar:** Sin errores SQL injection. Resultados vacios o parciales.

### 3.3 Cambio de Turno a Medio Dia

- [ ] **Cerrar turno del turno matutino y abrir vespertino:**
  1. Realizar 5 ventas en el turno actual.
  2. Ir a Turnos (F5). Cerrar turno con efectivo contado: ingresar un monto.
  3. **Verificar:** Se muestra corte: Esperado vs Contado vs Diferencia.
  4. Abrir nuevo turno con fondo: `$3,000.00`.
  5. Realizar 3 ventas mas.
  6. **Verificar:** El badge se reinicio con las ventas del nuevo turno (3, no 8).
  7. En Historial, confirmar que las 5 ventas del turno anterior siguen visibles.
- [ ] **Diferencia en corte de caja — sobrante:**
  1. Cerrar turno. Efectivo esperado: $5,000. Efectivo contado: $5,200.
  2. **Verificar:** Diferencia = +$200.00 (sobrante). Se registra.
- [ ] **Diferencia en corte de caja — faltante:**
  1. Cerrar turno. Efectivo esperado: $5,000. Efectivo contado: $4,800.
  2. **Verificar:** Diferencia = -$200.00 (faltante). Se registra.

### 3.4 Manejo de Perfiles de Configuracion

- [ ] **Guardar y cargar perfil:**
  1. Ir a Configuraciones. Configurar URL: `http://192.168.10.90:8000`, Terminal ID: `2`.
  2. Guardar config. Nombre perfil: `Caja 2 Prod`. Guardar perfil.
  3. Cambiar URL a `http://localhost:8000`, Terminal: `1`. Guardar config.
  4. Seleccionar perfil `Caja 2 Prod` del dropdown.
  5. **Verificar:** URL y Terminal ID cambian a los del perfil guardado.
- [ ] **Eliminar perfil:**
  1. Seleccionar perfil. Clic Eliminar. Confirmar.
  2. **Verificar:** Perfil desaparece del dropdown.
- [ ] **Guardar perfil con nombre duplicado sobreescribe:**
  1. Guardar perfil `Caja 1`. Cambiar URL. Guardar perfil `Caja 1` de nuevo.
  2. **Verificar:** Solo 1 perfil `Caja 1` (el nuevo).
- [ ] **Maximo 20 perfiles:**
  1. Crear 20 perfiles. Intentar crear el 21.
  2. **Verificar:** Se crea y el mas antiguo se elimina (comportamiento slice).

### 3.5 Navegacion Rapida con Teclas F

- [ ] **Ciclo completo de navegacion F1-F6:**
  1. Presionar F1. **Verificar:** Terminal visible.
  2. F2. **Verificar:** Clientes visible.
  3. F3. **Verificar:** Productos visible.
  4. F4. **Verificar:** Inventario visible.
  5. F5. **Verificar:** Turnos visible.
  6. F6. **Verificar:** Reportes visible.
  7. **Verificar:** Navegacion instantanea (< 200ms perceptible). Sin parpadeo blanco.
- [ ] **F1 desde cualquier tab vuelve a Terminal:**
  1. Estar en F4 (Inventario). Presionar F1.
  2. **Verificar:** Terminal visible. Carrito intacto si tenia items.
- [ ] **F7, F8, F9 — modales:**
  1. F7 abre Entrada de efectivo. Esc cierra.
  2. F8 abre Retiro de efectivo. Esc cierra.
  3. F9 abre Verificador de precios. Esc cierra.
  4. **Verificar:** Los 3 modales abren y cierran sin afectar el estado.

### 3.6 El Cajero Novato — Errores Comunes

- [ ] **Cobrar sin productos en carrito:**
  1. En Terminal con carrito vacio, intentar cobrar.
  2. **Verificar:** Mensaje "No hay productos en el ticket." Nada se envia al backend.
- [ ] **Cobrar sin turno abierto:**
  1. Borrar `localStorage.removeItem('titan.currentShift')` desde consola.
  2. Intentar cobrar con productos en carrito.
  3. **Verificar:** Mensaje indicando que no hay turno abierto.
- [ ] **Doble clic accidental en Cobrar:**
  1. Agregar productos. Hacer doble clic rapido en Cobrar.
  2. **Verificar:** Solo se registra UNA venta (el boton se deshabilita durante el busy).
- [ ] **Navegar a otra pestana con ticket a medio capturar:**
  1. Agregar 4 productos al carrito. Presionar F2 (Clientes). Presionar F1 (Terminal).
  2. **Verificar:** Los 4 productos siguen en el carrito.
- [ ] **Ingresar cantidad 0 en producto:**
  1. Agregar producto. Editar cantidad a 0.
  2. **Verificar:** Se elimina del carrito o se rechaza.
- [ ] **Ingresar cantidad negativa:**
  1. Agregar producto. Intentar editar cantidad a -5.
  2. **Verificar:** Rechazado. Cantidad minima es 1.
- [ ] **Descuento mayor a 100%:**
  1. Intentar aplicar descuento individual de 150%.
  2. **Verificar:** Rechazado o limitado a 100%.

### 3.7 Busqueda Intensiva de Productos

- [ ] **Buscar por nombre parcial:**
  1. Buscar `coca`. **Verificar:** Todos los productos con "coca" en el nombre aparecen.
- [ ] **Buscar por SKU:**
  1. Buscar el SKU exacto de un producto. **Verificar:** El producto aparece.
- [ ] **Busqueda con espacios y mayusculas:**
  1. Buscar `  COCA  cola  `. **Verificar:** Funciona sin errores, ignora espacios extra.
- [ ] **Buscar por SKU parcial:**
  1. SKU del producto: `CHOC-001`. Buscar `CHOC`.
  2. **Verificar:** Aparece en resultados.
- [ ] **Buscar numeros:**
  1. Buscar `600` (parte del nombre "600ml").
  2. **Verificar:** Retorna productos que contengan "600" en nombre o SKU.

---

## FASE 4: Volumen y Estres — Dia de Ventas Pesado

Meta: simular un dia completo de alta demanda con **500+ ventas**.

### Reglas Globales de Datos
- Precios base en `.00` (sin centavos). Centavos solo via descuentos.
- Mezcla de metodos: 60% efectivo, 25% tarjeta, 15% transferencia.
- Cada 7 ventas, hacer rotacion de inventario (crear 10-15 productos nuevos).
- Cada 20 ventas, hacer un movimiento de caja (F7 o F8).

### 4.1 Bloque de Velocidad (ventas 1-50)

- [ ] **Ventas rapidas de 1-2 productos:**
  1. Objetivo: calentar el sistema. Ventas simples.
  2. **Observar:** Tiempos de respuesta estables. Sin degradacion.
- [ ] **Primera rotacion de inventario (venta ~7):**
  1. Ir a Productos. Crear 15 productos nuevos con stock 12-36.
  2. Volver a Terminal. Usar esos productos en las siguientes ventas.
- [ ] **Ventas con descuento individual cada 5 ventas:**
  1. Venta 5: 1 producto con 10% descuento.
  2. Venta 10: 2 productos, uno con 20% descuento.
  3. **Verificar:** Descuentos correctos en cada caso.
- [ ] **Ventas con montos exactos vs cambio:**
  1. 25 ventas con pago exacto, 25 con billete grande.
  2. **Verificar:** Cambio calculado correctamente en todas.

### 4.2 Bloque de Complejidad (ventas 50-200)

- [ ] **Ventas con descuentos variados:**
  1. Cada tercera venta, aplicar descuento (5%, 10%, 15% alternado).
  2. **Observar:** Los centavos resultantes son matematicamente correctos.
- [ ] **Ventas con descuento global cada 10 ventas:**
  1. Venta 60: descuento global 5%. Venta 70: 10%. Venta 80: 15%.
  2. **Verificar:** Total = subtotal * (1 - descuento/100) exacto.
- [ ] **Ventas con descuento individual + global combinado:**
  1. Cada 20 ventas: 1 item con 10% individual + 5% global.
  2. **Verificar:** Descuento compuesto correcto (no aditivo).
- [ ] **Ventas con 5+ items por ticket:**
  1. Mezclar productos viejos y nuevos. Cantidades variadas (1 a 5 unidades).
  2. **Verificar:** Total siempre es correcto.
- [ ] **Intercalar movimientos de caja:**
  1. Cada ~20 ventas: F7 con $500 o F8 con $300.
  2. **Verificar:** Movimientos no afectan el flujo de ventas.
- [ ] **Ventas en modo mayoreo intercaladas:**
  1. Cada 15 ventas: activar mayoreo, 3 ventas, desactivar.
  2. **Verificar:** Precios correctos en cada modo.

### 4.3 Bloque de Resistencia (ventas 200-500)

- [ ] **Ventas con tickets pendientes activos:**
  1. Mantener 2-3 tickets pendientes mientras se hacen ventas rapidas.
  2. Cada ~30 ventas, cobrar un pendiente y crear otro nuevo.
  3. **Observar:** Sin acumulacion de memoria. Sin lag progresivo.
- [ ] **Ventas con clientes asignados:**
  1. Cada 10 ventas, asignar un cliente diferente.
  2. **Verificar:** Historial del cliente se actualiza correctamente.
- [ ] **Busquedas intensivas entre ventas:**
  1. Antes de cada venta, buscar productos por diferentes terminos.
  2. **Observar:** Busqueda sigue fluida aun con 200+ productos en catalogo.
- [ ] **Stress de descuentos variados:**
  1. Venta con solo descuentos individuales (sin global).
  2. Venta con solo descuento global (sin individuales).
  3. Venta con ambos combinados.
  4. Venta sin descuentos.
  5. Repetir patron 10 veces. **Verificar:** Todos los totales correctos.
- [ ] **Verificacion de folios al final:**
  1. Tras 500 ventas, ir a Historial. Ordenar por folio.
  2. **Verificar:** Folios consecutivos sin huecos. Sin duplicados.

---

## FASE 5: Concurrencia Extrema — Race Conditions

### 5.1 Multi-Pestana Simultanea

- [ ] **5 pestanas, 200 ventas alternadas:**
  1. Abrir 5 pestanas del navegador, todas logueadas en la misma sesion.
  2. Realizar ventas alternando entre pestanas aleatoriamente.
  3. Combinar pagos exactos y con cambio.
  4. **Verificar:** Folios secuenciales sin huecos ni duplicados. Consultar en Historial.
- [ ] **Badges sincronizados:**
  1. Tras las 200 ventas, abrir una pestana nueva.
  2. Esperar 60s. **Verificar:** Badge muestra el total correcto (sincronizado via polling).
- [ ] **3 pestanas con descuentos simultaneos:**
  1. Pestana A: venta con descuento individual 20%.
  2. Pestana B: venta con descuento global 10%.
  3. Pestana C: venta con descuento individual 15% + global 5%.
  4. Cobrar las 3 casi al mismo tiempo.
  5. **Verificar:** Cada venta tiene su descuento correcto. Sin mezcla entre pestanas.

### 5.2 Colision de Inventario

- [ ] **Stock bajo + cobros simultaneos:**
  1. Identificar producto con exactamente 5 unidades.
  2. Pestana A: agregar 4 unidades al carrito.
  3. Pestana B: agregar 4 unidades al carrito.
  4. Pestana C: agregar 3 unidades al carrito.
  5. Cobrar en las 3 pestanas casi al mismo tiempo (< 2 segundos).
  6. **Verificar:** Solo el primer cobro pasa. Los demas son rechazados por stock insuficiente. Stock NUNCA llega a negativo.
- [ ] **Edicion simultanea de producto:**
  1. En Pestana A (Productos): seleccionar producto, cambiar precio a $99.
  2. En Pestana B (Productos): seleccionar mismo producto, cambiar precio a $150.
  3. Guardar ambos casi al mismo tiempo.
  4. **Verificar:** Uno gana. No hay corrupcion de datos. El precio final es uno de los dos.
- [ ] **Stock bajo + descuentos:**
  1. Producto con 2 unidades a $100.
  2. Pestana A: 2 unidades con descuento 50% = $100 total.
  3. Pestana B: 1 unidad sin descuento = $100 total.
  4. Cobrar simultaneamente.
  5. **Verificar:** Maximo 2 unidades vendidas entre ambas. Stock >= 0.

### 5.3 Operaciones Cruzadas

- [ ] **Vender mientras otro pestana edita inventario:**
  1. Pestana A: agregar producto al carrito y cobrar.
  2. Mientras tanto, Pestana B: hacer ajuste de stock al mismo producto.
  3. **Verificar:** Ambas operaciones se completan sin error. Stock final es consistente.
- [ ] **Cerrar turno desde Pestana A, vender desde Pestana B:**
  1. Pestana A: cerrar turno.
  2. Pestana B (sin recargar): intentar cobrar.
  3. **Verificar:** Pestana B detecta turno cerrado y muestra error claro.
- [ ] **Editar producto y venderlo simultaneamente:**
  1. Pestana A: editar precio de "Producto X" de $100 a $200.
  2. Pestana B: agregar "Producto X" al carrito (precio $100 en pantalla) y cobrar.
  3. **Verificar:** Backend valida y usa el precio real de la DB. Sin precio inconsistente.
- [ ] **Crear cliente y usarlo al mismo tiempo:**
  1. Pestana A: crea cliente `Nuevo Cliente` y lo guarda.
  2. Pestana B: recarga clientes. Asigna `Nuevo Cliente` a una venta.
  3. **Verificar:** Venta con el cliente correcto.

---

## FASE 6: Caos de Red y Resiliencia

### 6.1 Desconexion Prolongada

- [ ] **50 ventas offline:**
  1. DevTools > Network > Offline (o apagar red).
  2. Realizar 50 ventas variadas.
  3. **Verificar 1:** UI sigue funcionando sin congelarse. Productos se buscan del cache local.
  4. Reconectar red.
  5. **Verificar 2:** Las ventas se sincronizan al backend sin duplicarse.
- [ ] **Descuentos offline:**
  1. Red offline. Venta con descuento individual 10%.
  2. Reconectar. **Verificar:** Venta sincronizada con descuento correcto.

### 6.2 Latencia Extrema — 3G Lento

- [ ] **Operaciones bajo 3G Lento:**
  1. DevTools > Network > Slow 3G.
  2. Buscar producto con termino generico (`a`) que retorne muchos resultados.
  3. **Verificar:** Spinner visible. UI no se congela.
  4. Realizar venta. **Verificar:** Boton Cobrar muestra estado loading/disabled. No permite doble envio.
  5. Hacer corte de caja. **Verificar:** Se completa (lento pero sin error).
- [ ] **Descuento bajo latencia:**
  1. 3G Lento. Agregar producto con descuento 15%. Cobrar.
  2. **Verificar:** Descuento se envia correctamente al backend. Sin timeout.

### 6.3 Micro-Cortes de Red

- [ ] **Apagar red justo al cobrar (5 intentos):**
  1. Preparar venta. En el instante de presionar Cobrar, apagar red.
  2. Esperar 2 segundos. Encender red.
  3. **Verificar:** O la venta se registro exitosamente, o muestra error limpio.
  4. Revisar Historial: la venta NO esta duplicada.
  5. Repetir 5 veces. **Verificar:** Ningun ticket se duplico.
- [ ] **Micro-corte durante venta con descuento:**
  1. Venta con descuento global 20%. Apagar red al cobrar.
  2. Reconectar. **Verificar:** Si la venta paso, el descuento es correcto.

### 6.4 Backend Muerto

- [ ] **Detener backend completamente:**
  1. Detener el servidor FastAPI.
  2. Intentar: login, cobrar, cargar productos, abrir turno.
  3. **Verificar:** Cada operacion muestra error claro ("No se pudo conectar al servidor" o similar). No hay pantalla blanca.
  4. Re-iniciar backend.
  5. **Verificar:** Todas las operaciones vuelven a funcionar sin recargar pagina.
- [ ] **Backend muere y revive entre 2 ventas:**
  1. Venta 1 exitosa. Matar backend. Intentar venta 2 (falla).
  2. Reiniciar backend. Venta 3.
  3. **Verificar:** Venta 1 y 3 en historial. Venta 2 no existe. Sin corrupcion.

---

## FASE 7: Fatiga de Memoria y Abuso de UI

### 7.1 Inyeccion de Texto Malicioso

- [ ] **XSS en busqueda:**
  1. En Terminal, buscar: `<script>alert(1)</script>`.
  2. **Verificar:** No se ejecuta JS. Texto se muestra como texto plano o se ignora.
- [ ] **XSS en nombre de producto:**
  1. Crear producto con nombre `<img onerror=alert(1) src=x>`.
  2. **Verificar:** Se guarda como texto plano. Sin ejecucion de JS.
- [ ] **XSS en nombre de cliente:**
  1. Crear cliente `<script>document.cookie</script>`.
  2. **Verificar:** Se guarda como texto plano. Visible sin ejecucion.
- [ ] **SQL injection en busqueda:**
  1. Buscar `'; DROP TABLE products; --`.
  2. **Verificar:** Sin error de SQL. Busqueda retorna vacio.
- [ ] **Zalgo text:**
  1. Buscar: `T̴̡̧̛̛̘͙̱̪̝̝̤͎͑̂̇̃̈́̾̏̽̕͝ë̶̢s̷̨t̴`.
  2. **Verificar:** Sin crash. Busqueda funciona normalmente.
- [ ] **Texto extremadamente largo (10,000 chars):**
  1. Pegar 10,000 caracteres de Lorem Ipsum en el buscador.
  2. **Verificar:** Sin congelamiento. La busqueda retorna sin resultados.
- [ ] **Caracteres de control y nulos:**
  1. Intentar pegar texto con `\0`, `\t`, `\n` en campos de busqueda.
  2. **Verificar:** Caracteres de control se stripean. Sin comportamiento inesperado.
- [ ] **Emojis en campos:**
  1. Crear producto con nombre `Cerveza 🍺 Premium`.
  2. **Verificar:** Se crea correctamente. Emoji visible en busqueda.

### 7.2 Sobrecarga de Carrito

- [ ] **100+ items en un solo ticket:**
  1. Agregar 100+ productos diferentes al carrito uno por uno.
  2. Hacer scroll en el carrito. **Verificar:** Fluidez aceptable (no congelamiento).
  3. Cobrar el ticket masivo. **Verificar:** Se registra exitosamente en el backend.
- [ ] **Mismo producto 999 unidades:**
  1. Agregar producto. Editar cantidad a 999.
  2. **Verificar:** Total se calcula correctamente. Si supera stock, el backend debe rechazar al cobrar.
- [ ] **100 items con descuentos individuales diferentes:**
  1. Agregar 100 items. A cada uno aplicar descuento diferente (1%, 2%, 3%... 100%).
  2. **Verificar:** Total es la suma correcta de todos los subtotales descontados.
- [ ] **Carrito masivo con descuento global:**
  1. 50 productos variados. Descuento global 12%.
  2. **Verificar:** Total = sum(subtotales) * 0.88.

### 7.3 Sesion Prolongada sin Recarga

- [ ] **4+ horas sin recargar pagina:**
  1. Dejar la app abierta sin recargar durante toda la sesion de pruebas.
  2. Tras 100+ ventas, verificar que busquedas, cobros y navegacion siguen fluidas.
  3. **Verificar:** Sin memory leaks evidentes (tab no consume > 500MB en DevTools > Memory).
- [ ] **Sesion con multiples descuentos acumulados:**
  1. En la sesion prolongada, hacer 50 ventas con descuentos variados.
  2. **Verificar:** Los calculos siguen correctos incluso despues de horas.

### 7.4 Purga de LocalStorage

- [ ] **localStorage.clear() con ticket activo:**
  1. Agregar 10 items al carrito.
  2. Abrir consola: `localStorage.clear()`.
  3. Intentar cobrar.
  4. **Verificar:** Redireccion a Login o mensaje de error claro. Sin pantalla blanca.
- [ ] **Borrar solo el token:**
  1. Con ticket activo: `localStorage.removeItem('titan.token')`.
  2. Intentar cobrar.
  3. **Verificar:** Error 401 manejado limpiamente. Redireccion a Login.
- [ ] **Corromper runtime config:**
  1. `localStorage.setItem('titan.config', '{basura}')`.
  2. Recargar pagina.
  3. **Verificar:** App carga con defaults o muestra pantalla de configuracion.

---

## FASE 8: Cierre de Turno Masivo — El Juicio Final

Con 500-1500 ventas acumuladas, movimientos de caja, mermas y operaciones concurrentes.

### 8.1 Corte de Caja

- [ ] **Cerrar turno pesado:**
  1. Ir a Turnos. Iniciar cierre de turno.
  2. Ingresar efectivo contado.
  3. **Cronometrar:** El calculo del corte no debe tardar > 8 segundos.
  4. **Verificar:** Esperado, Contado y Diferencia se muestran correctamente.
  5. **Verificar:** El navegador NO muestra "La pagina no responde".
- [ ] **Corte con diferencia de centavos:**
  1. Esperado: $12,345.67. Contado: $12,345.50.
  2. **Verificar:** Diferencia = -$0.17. Centavos cuadran.

### 8.2 Auditoria Matematica

- [ ] **Cuadre de 10 tickets aleatorios:**
  1. Seleccionar 10 tickets al azar del Historial (mezcla de metodos, con/sin descuento).
  2. Con calculadora fisica, sumar subtotales, impuestos y descuentos de cada uno.
  3. **Verificar:** Los numeros coinciden centavo a centavo con lo que muestra el sistema.
- [ ] **Cuadre de stock de 5 productos:**
  1. Seleccionar 5 productos creados en Fase 4 (stock inicial conocido: 12-36 uds).
  2. Calcular: `Stock Inicial - Unidades Vendidas (historial) = Stock Actual`.
  3. **Verificar:** El calculo coincide exactamente con el stock mostrado en Inventario.
- [ ] **Cuadre de descuentos — 5 tickets con descuento:**
  1. Seleccionar 5 tickets que tenian descuento (individual, global, o combinado).
  2. Recalcular manualmente: precio * qty * (1 - desc%) para individuales, total * (1 - globalDesc%) para globales.
  3. **Verificar:** Todos coinciden centavo a centavo.
- [ ] **Cuadre de ventas por metodo de pago:**
  1. Sumar todas las ventas en efectivo. Sumar tarjeta. Sumar transferencia.
  2. **Verificar:** efectivo + tarjeta + transferencia = total general del reporte.
- [ ] **Cuadre de movimientos de caja:**
  1. Sumar todos los F7 (entradas). Sumar todos los F8 (retiros).
  2. **Verificar:** Neto movimientos = entradas - retiros. Coincide con corte de caja.

### 8.3 Reportes Post-Cierre

- [ ] **Reporte de ventas del dia:**
  1. Ir a Reportes. Generar reporte del rango de hoy.
  2. **Verificar:** Total de ventas coincide con el corte de caja.
  3. Desglose por metodo: efectivo + tarjeta + transferencia = total general.
- [ ] **Top 10 productos:**
  1. En Reportes, verificar ranking de productos.
  2. **Verificar:** Los productos mas vendidos tienen sentido (aquellos usados mas frecuentemente en ventas).
- [ ] **Reporte de descuentos:**
  1. Verificar total de descuentos otorgados.
  2. **Verificar:** Suma de descuentos individuales + globales = total descuentos reportado.

### 8.4 Reapertura Limpia

- [ ] **Turno fresco del "dia siguiente":**
  1. Cerrar navegador completamente. Abrir ventana de incognito.
  2. Loguearse. Abrir nuevo turno con fondo $2,000.
  3. **Verificar:** Badge: 0 ventas / $0.00. Sin arrastre de datos del turno anterior.
  4. Hacer 1 venta. **Verificar:** Badge: 1 venta con total correcto.
- [ ] **Turno fresco con descuento:**
  1. Primera venta del nuevo turno con descuento global 10%.
  2. **Verificar:** Descuento aplica correctamente. Badge: 1 venta con total descontado.

---

## FASE 9: Escenarios Caoticos Extremos

Situaciones que "nunca deberian pasar" pero pasan. Cada una busca un crash o corrupcion de datos.

### 9.1 Cobro Fantasma Post-Turno

- [ ] **Ticket huerfano tras cierre:**
  1. Pestana A: cargar carrito con 3 productos. NO cobrar.
  2. Pestana B: cerrar turno e imprimir comprobante.
  3. Volver a Pestana A: intentar cobrar.
  4. **Verificar:** Rechazado. Exige abrir nuevo turno. El ticket NO se cuela en el turno cerrado.
- [ ] **Ticket con descuento huerfano:**
  1. Pestana A: carrito con descuento global 15%. NO cobrar.
  2. Pestana B: cerrar turno.
  3. Pestana A: cobrar.
  4. **Verificar:** Rechazado. Descuento no causa comportamiento diferente.

### 9.2 Disaster Recovery — Turno Perdido

- [ ] **Simular perdida de localStorage con turno activo en backend:**
  1. Abrir turno normalmente. Hacer 3 ventas.
  2. `localStorage.removeItem('titan.currentShift')`.
  3. Recargar pagina (F5 real). Loguearse de nuevo.
  4. **Verificar:** El modal de turno detecta el turno abierto en el backend y lo recupera.
  5. **Verificar:** El badge muestra las 3 ventas que se hicieron antes (no 0).
- [ ] **Disaster recovery con ventas con descuento:**
  1. Abrir turno. Venta 1: $100. Venta 2: $200 con 10% desc = $180. Venta 3: $50.
  2. Total esperado: $330 (3 ventas).
  3. Borrar localStorage. Recuperar turno.
  4. **Verificar:** Badge muestra 3 ventas / $330.00 (incluye el descuento).

### 9.3 Login Simultaneo Contradictorio

- [ ] **Dos navegadores, mismo usuario, operaciones opuestas:**
  1. Navegador A: login como admin. Abrir turno.
  2. Navegador B (incognito): login como admin.
  3. Navegador A: hacer 5 ventas.
  4. Navegador B: intentar abrir otro turno.
  5. **Verificar:** Backend rechaza segundo turno (ya hay uno abierto) O lo recupera.
  6. Navegador B: intentar cerrar el turno.
  7. Navegador A: intentar cobrar.
  8. **Verificar:** Error claro en A (turno cerrado). Sin corrupcion de datos.

### 9.4 Manipulacion de Precios en Vuelo

- [ ] **Cambiar precio mientras hay tickets pendientes:**
  1. Agregar "Producto X" al carrito (precio $100).
  2. En otra pestana, ir a Productos y cambiar precio de "Producto X" a $200.
  3. Volver a la pestana original y cobrar.
  4. **Verificar:** La venta se registra con el precio que valida el backend. Sin monto inconsistente.
- [ ] **Cambiar precio mayoreo mientras hay venta mayoreo pendiente:**
  1. Modo mayoreo. Producto con mayoreo $80. Agregar al carrito.
  2. Otra pestana: cambiar mayoreo a $60.
  3. Cobrar. **Verificar:** Precio coherente con DB.
- [ ] **Desactivar producto mientras esta en carrito:**
  1. Agregar "Producto Y" al carrito.
  2. Otra pestana: desactivar "Producto Y".
  3. Cobrar.
  4. **Verificar:** Backend rechaza o acepta con advertencia. Sin crash.

### 9.5 Cascada de Errores

- [ ] **Todo falla al mismo tiempo:**
  1. Tener 3 tickets pendientes.
  2. Apagar red.
  3. Intentar cobrar ticket 1 (falla por red).
  4. Intentar cobrar ticket 2 (falla).
  5. Prender red.
  6. Cobrar ticket 3 exitosamente.
  7. Cobrar ticket 1 y 2.
  8. **Verificar:** Las 3 ventas se registraron exactamente una vez cada una. Sin duplicados.
- [ ] **Cascada con descuentos:**
  1. Ticket 1: descuento individual 10%. Ticket 2: descuento global 15%. Ticket 3: ambos.
  2. Apagar red. Intentar cobrar los 3. Falla.
  3. Encender red. Cobrar los 3.
  4. **Verificar:** Cada descuento se mantuvo intacto tras los reintentos.

### 9.6 Sesion Zombie — Token Expirado

- [ ] **Token JWT expirado mid-sesion:**
  1. Modificar el token en localStorage a un string invalido: `localStorage.setItem('titan.token', 'expired.jwt.token')`.
  2. Intentar cobrar.
  3. **Verificar:** Error 401 capturado. Redireccion a Login.
  4. Loguearse de nuevo. **Verificar:** Las operaciones funcionan normalmente.

### 9.7 Abuso del Formulario de Empleados

- [ ] **Salario con valores extremos:**
  1. Crear empleado con salario `0`. **Verificar:** Se acepta (puede ser voluntario/comisionista).
  2. Crear empleado con salario `999999999`. **Verificar:** Se acepta o se rechaza limpiamente.
  3. Crear empleado con comision `100` (100%). **Verificar:** Se guarda como `1.00` en backend.
  4. Crear empleado con comision `0`. **Verificar:** Se guarda como `0.00`.
- [ ] **Codigo de empleado duplicado:**
  1. Crear empleado con codigo `DUP-001`.
  2. Crear otro con mismo codigo `DUP-001`.
  3. **Verificar:** Backend rechaza con error "Codigo de empleado ya existe".
- [ ] **Empleado con caracteres especiales en nombre:**
  1. Nombre: `María José Ñoño-García`. **Verificar:** Acentos y ñ se guardan correctamente.
- [ ] **Empleado con email invalido:**
  1. Email: `noesunmail`. **Verificar:** Rechazado o advertencia.
  2. Email: `empleado@correo.com`. **Verificar:** Aceptado.

### 9.8 Clientes — Edge Cases

- [ ] **Telefono y email invalidos:**
  1. Crear cliente con telefono `abc`. **Verificar:** Rechazado por validacion de formato.
  2. Crear cliente con email `noesunmail`. **Verificar:** Rechazado.
  3. Crear cliente con telefono y email vacios (solo nombre). **Verificar:** Se acepta.
- [ ] **Nombre extremadamente largo:**
  1. Crear cliente con nombre de 200 caracteres (maximo del input).
  2. **Verificar:** Se crea correctamente. Se muestra truncado en la tabla.
- [ ] **Cliente con nombre con caracteres especiales:**
  1. Crear `Corporación Ñandú S.A. de C.V.`. **Verificar:** Se guarda con acentos y ñ.

### 9.9 Recarga de Pagina en Momentos Criticos

- [ ] **F5 mientras se procesa un cobro:**
  1. Presionar Cobrar. Inmediatamente hacer F5 (recarga real).
  2. Loguearse de nuevo. Revisar Historial.
  3. **Verificar:** La venta se registro UNA sola vez (o no se registro y el ticket se puede reintentar).
- [ ] **F5 durante cierre de turno:**
  1. Iniciar cierre de turno. Inmediatamente F5.
  2. **Verificar:** El turno o se cerro exitosamente o sigue abierto. No queda en estado corrupto.
- [ ] **F5 durante creacion de producto:**
  1. Llenar formulario de producto nuevo. Clic Guardar. Inmediatamente F5.
  2. **Verificar:** El producto se creo (aparece en lista) o no se creo (se puede reintentar).
- [ ] **F5 con descuento global activo:**
  1. Aplicar descuento global 20%. F5 antes de cobrar.
  2. Loguearse. **Verificar:** El descuento se perdio (nuevo carrito limpio) — comportamiento esperado.

### 9.10 Ataque de Volumen al Buscador

- [ ] **Escribir y borrar rapidamente (debounce):**
  1. En Terminal, escribir `coca` caracter por caracter muy rapido, luego borrar todo, luego escribir `pepsi`.
  2. **Verificar:** Solo se muestra el resultado final (`pepsi`). Sin resultados fantasma de `coca`.
- [ ] **Pegar y buscar 50 veces seguidas:**
  1. Pegar un termino de busqueda, borrar, pegar otro, borrar. Repetir 50 veces en 30 segundos.
  2. **Verificar:** La UI no se congela. Sin memory leak por requests acumulados.
- [ ] **Buscar mientras se aplica descuento:**
  1. Agregar producto. Aplicar descuento 15%. Mientras el descuento se calcula, buscar otro producto.
  2. **Verificar:** Ambas operaciones se completan sin interferencia.

### 9.11 Matematicas de Descuento — Casos Limite

- [ ] **Descuento que genera $0.001 (sub-centavo):**
  1. Producto $3.00. Descuento 33.33%.
  2. **Verificar:** Total redondeado a 2 decimales. Sin error de precision.
- [ ] **Multiples descuentos individuales que suman > 100% efectivo con global:**
  1. Item A: $100, desc 80% = $20. Item B: $100, desc 90% = $10. Subtotal = $30.
  2. Descuento global 50%. Total = $15.
  3. **Verificar:** Total = $15.00. Matematica correcta.
- [ ] **Descuento a producto de $0.01:**
  1. Producto $0.01. Descuento 50%.
  2. **Verificar:** Subtotal = $0.01 o $0.00 (redondeo). Sin error.
- [ ] **10 productos identicos con descuentos diferentes cada uno:**
  1. Mismo producto x10. Desc: 0%, 5%, 10%, 15%, 20%, 25%, 30%, 35%, 40%, 45%.
  2. Precio unitario: $100.
  3. **Verificar:** Total = $100*(1+0.95+0.90+0.85+0.80+0.75+0.70+0.65+0.60+0.55) = $100*7.75 = $775.00.
- [ ] **Descuento 99.99% — casi gratis:**
  1. Producto $10,000. Descuento 99.99%.
  2. **Verificar:** Subtotal = $1.00. Se cobra correctamente.
- [ ] **Ticket con 1 item sin descuento y 1 con 100% descuento:**
  1. Item A: $500 sin descuento. Item B: $300 con 100% descuento = $0.
  2. **Verificar:** Total = $500.00. Item B aparece en detalle con total $0.

---

## FASE 10: Dos Terminales Fisicas Simultaneas (2 PCs)

Simular una tienda real con 2 cajas operando al mismo tiempo. Requiere 2 computadoras (o 2 perfiles de navegador con diferente `terminalId`) apuntando al mismo backend.

**Setup:** PC-A configura `terminalId: 1`. PC-B configura `terminalId: 2`. Ambas apuntan al mismo backend (`http://192.168.10.X:8000`).

### 10.1 Apertura de Dia — 2 Cajas

- [ ] **Cada caja abre su propio turno:**
  1. PC-A: Login como `cajero1`. Abrir turno con fondo $2,500.
  2. PC-B: Login como `cajero2`. Abrir turno con fondo $3,000.
  3. **Verificar:** Cada PC muestra su propio badge de turno con el operador correcto.
  4. **Verificar:** En el backend (Turnos o Reportes), se ven 2 turnos abiertos simultaneamente.

### 10.2 Ventas Simultaneas — Flujo Normal

- [ ] **Ambas cajas venden al mismo tiempo:**
  1. PC-A: cargar ticket con 3 productos. Cobrar con efectivo.
  2. PC-B: cargar ticket con 2 productos. Cobrar con tarjeta.
  3. Hacer esto simultaneamente (presionar Cobrar en ambas PCs al mismo tiempo).
  4. **Verificar:** Ambas ventas se registran. Folios son consecutivos sin duplicados.
  5. Repetir 20 veces. **Verificar:** 20 ventas en cada caja, folios todos unicos.
- [ ] **Ambas cajas venden el mismo producto:**
  1. Producto con stock 30 unidades.
  2. PC-A vende 5 unidades. PC-B vende 8 unidades. Al mismo tiempo.
  3. **Verificar:** Stock final = 30 - 5 - 8 = 17. Exacto.
- [ ] **Ventas con descuentos en ambas cajas:**
  1. PC-A: venta con descuento individual 10% en producto de $200 = $180.
  2. PC-B: venta con descuento global 15% sobre $500 = $425.
  3. Cobrar simultaneamente.
  4. **Verificar:** Cada descuento correcto. Sin interferencia entre terminales.
- [ ] **Ventas mayoreo vs menudeo simultaneas:**
  1. PC-A: modo mayoreo. Producto con mayoreo $80.
  2. PC-B: modo menudeo. Mismo producto con precio $100.
  3. Cobrar ambas. **Verificar:** PC-A cobra $80. PC-B cobra $100.

### 10.3 Colision de Stock entre Terminales

- [ ] **Agotamiento cruzado de inventario:**
  1. Producto con exactamente 3 unidades de stock.
  2. PC-A: agregar 2 unidades al carrito.
  3. PC-B: agregar 2 unidades al carrito.
  4. PC-A cobra. **Verificar:** Exito. Stock queda en 1.
  5. PC-B cobra. **Verificar:** Rechazado. Solo hay 1 unidad, pide 2.
- [ ] **Ultima unidad — carrera:**
  1. Producto con exactamente 1 unidad.
  2. Ambas PCs lo agregan al carrito. Cobran al mismo tiempo.
  3. **Verificar:** Solo 1 PC logra la venta. La otra recibe error. Stock = 0 (nunca negativo).
- [ ] **Stock bajo con descuento:**
  1. Producto con 2 unidades, precio $100.
  2. PC-A: 2 unidades con 50% descuento = $100.
  3. PC-B: 1 unidad sin descuento = $100.
  4. PC-A cobra primero. **Verificar:** Stock = 0. PC-B rechazada.

### 10.4 Operaciones Cruzadas entre Cajas

- [ ] **PC-A edita producto, PC-B lo vende:**
  1. PC-A: ir a Productos, cambiar precio de "Producto X" de $100 a $150.
  2. Mientras tanto, PC-B: agregar "Producto X" al carrito y cobrar.
  3. **Verificar:** La venta usa un precio valido ($100 o $150, dependiendo del timing). Sin error.
- [ ] **PC-A registra merma, PC-B vende:**
  1. Producto con 10 unidades.
  2. PC-A: registrar merma de 8 unidades.
  3. PC-B: intentar vender 5 unidades del mismo producto.
  4. **Verificar:** PC-B rechazada por stock insuficiente (solo quedan 2).
- [ ] **PC-A crea cliente, PC-B lo usa inmediatamente:**
  1. PC-A: crear cliente "Empresa XYZ SA de CV".
  2. PC-B: ir a Clientes, hacer clic en Cargar.
  3. **Verificar:** "Empresa XYZ SA de CV" aparece en la lista de PC-B.
  4. PC-B: asignar ese cliente a una venta. Cobrar.
  5. **Verificar:** Venta registrada con el cliente correcto.
- [ ] **PC-A crea producto, PC-B lo vende:**
  1. PC-A: crear producto `Nuevo Producto X`, precio $75, stock 20.
  2. PC-B: buscar `Nuevo Producto`. **Verificar:** Aparece.
  3. PC-B: vender 3 unidades. **Verificar:** Stock = 17.
- [ ] **PC-A cambia clave SAT, PC-B vende:**
  1. PC-A: editar producto, cambiar clave SAT de `01010101` a `50181700`.
  2. PC-B: vender ese producto.
  3. **Verificar:** La venta registra `sat_clave_prod_serv = '50181700'` (clave actualizada).

### 10.5 Movimientos de Caja Cruzados

- [ ] **Entrada en PC-A, retiro en PC-B (turnos separados):**
  1. PC-A: F7, entrada de $1,000. Motivo: "Cambio de caja vecina".
  2. PC-B: F8, retiro de $1,000. Motivo: "Envio a caja 1".
  3. **Verificar:** Cada movimiento se asocia al turno correcto de cada terminal.
  4. Al cerrar turno de cada PC, los movimientos cuadran con la caja correspondiente.

### 10.6 Cierre Escalonado de Turnos

- [ ] **PC-A cierra turno, PC-B sigue operando:**
  1. PC-A: hacer 10 ventas. Cerrar turno.
  2. PC-B: seguir haciendo ventas normalmente.
  3. **Verificar:** El cierre de PC-A no afecta en absoluto a PC-B.
  4. PC-B: cerrar turno despues.
  5. **Verificar:** Cada corte de caja muestra solo las ventas de su terminal.
- [ ] **Reportes muestran ambas terminales:**
  1. Ir a Reportes desde cualquier PC.
  2. Generar reporte del dia.
  3. **Verificar:** El reporte total incluye ventas de AMBAS terminales. El desglose es correcto.
- [ ] **Descuentos por terminal en reporte:**
  1. PC-A: 5 ventas con descuentos individuales.
  2. PC-B: 5 ventas con descuento global.
  3. **Verificar:** Reporte muestra total descuentos = descuentos_A + descuentos_B.

### 10.7 Disaster Recovery Multi-Terminal

- [ ] **PC-A muere a media venta:**
  1. PC-A: cargar carrito, presionar Cobrar.
  2. Mientras se procesa, apagar PC-A (simular con cerrar navegador abruptamente).
  3. PC-B: seguir operando normalmente.
  4. Encender PC-A de nuevo. Loguearse.
  5. **Verificar:** El turno de PC-A se recupera del backend. El badge muestra las ventas correctas.
  6. Revisar si la venta interrumpida se registro o no. Sin duplicados.

---

## FASE 11: Mas Escenarios Cotidianos de Retail Mexicano

### 11.1 El Lunes de Quincena

- [ ] **Rafaga de 30 ventas en 15 minutos:**
  1. Simular hora pico de quincena. Ventas rapidas de 2-3 items.
  2. Montos variados: $45, $120, $380, $67, $250.
  3. 50% efectivo (billetes de $500 y $200), 30% tarjeta, 20% transferencia.
  4. **Verificar:** Todo fluye sin lag. Cambios calculados correctamente. Badge actualizado.
- [ ] **Cliente paga $500 por venta de $12.50 (con descuento):**
  1. Producto de $25 con descuento 50%. Total: $12.50.
  2. Pago: $500.
  3. **Verificar:** Cambio mostrado: $487.50. Los centavos son exactos.
- [ ] **Venta de centavo problematico (descuento que genera .33):**
  1. Producto de $100. Descuento global de 33%.
  2. **Verificar:** Total muestra $67.00 (o redondeo consistente, no $66.999...).
- [ ] **Rafaga de descuentos variados en quincena:**
  1. Venta 1: sin descuento. Venta 2: 5% global. Venta 3: 10% individual. Venta 4: 15% global + 10% individual.
  2. 10 ventas asi alternando.
  3. **Verificar:** Cada total es correcto.

### 11.2 La Tlapaleria — Productos con Nombres Largos y SKUs Complejos

- [ ] **Crear producto con nombre de 150+ caracteres:**
  1. Nombre: `Tornillo Autorroscante Cabeza Avellanada Phillips Acero Inoxidable 304 Medida 1/4 x 2 Pulgadas Caja 100 Piezas Marca Truper`.
  2. **Verificar:** Se crea. En la Terminal aparece truncado pero legible.
- [ ] **SKUs con caracteres especiales:**
  1. Crear producto con SKU `TORN-1/4x2`. **Verificar:** Se acepta.
  2. Crear con SKU `P&G-001`. **Verificar:** Funciona correctamente.
- [ ] **Producto de tlapaleria con clave SAT correcta:**
  1. `Tornillo Autorroscante`. Clave SAT: `31161700` (Tornillos).
  2. `Pintura Vinilica 4L`. Clave SAT: `31211500` (Pintura).
  3. **Verificar:** Ambas claves se guardan correctamente.
- [ ] **Buscar producto largo por nombre parcial:**
  1. Buscar `Tornillo Auto`. **Verificar:** Aparece el producto de 150+ chars.
  2. Buscar `Avellanada`. **Verificar:** Tambien aparece (busqueda parcial).

### 11.3 La Abarrotera — Ventas de Alto Volumen por Unidad

- [ ] **Venta de 50 unidades de un mismo producto:**
  1. Agregar producto. Editar cantidad a 50.
  2. Cobrar. **Verificar:** Stock se reduce en 50. Total = precio x 50.
- [ ] **Venta con 20 productos diferentes (ticket largo):**
  1. Agregar 20 productos distintos, cada uno con cantidad 1-3.
  2. Cobrar. **Verificar:** Todos los items aparecen en el historial de la venta.
- [ ] **Abarrotera — descuento por volumen (manual):**
  1. 50 unidades de Jabon ($10 c/u). Subtotal $500. Descuento global 5%.
  2. **Verificar:** Total = $475.00.
- [ ] **Abarrotera — multiples productos con claves SAT diferentes:**
  1. Refresco (clave `50202300`), Galletas (clave `50181700`), Jabon (clave `53131600`).
  2. Vender los 3 en un ticket.
  3. **Verificar:** Cada `sale_item` tiene su clave SAT correspondiente.

### 11.4 Horarios de Baja Demanda

- [ ] **Verificar precios entre ventas (F9 repetido):**
  1. Abrir y cerrar el verificador de precios (F9) 10 veces.
  2. Buscar diferentes productos en cada apertura.
  3. **Verificar:** Sin memory leak. Abre y cierra limpiamente cada vez.
- [ ] **Ajustar inventario entre ventas:**
  1. Ir a Inventario (F4). Hacer 5 ajustes de stock.
  2. Volver a Terminal (F1). Hacer una venta.
  3. Repetir 3 veces.
  4. **Verificar:** La alternancia entre tabs no corrompe ningun estado.
- [ ] **Actualizar claves SAT de productos existentes:**
  1. Seleccionar 5 productos con clave default `01010101`.
  2. Asignar claves SAT correctas a cada uno.
  3. **Verificar:** Todas persisten tras recargar.

### 11.5 El Cliente VIP — Descuentos Combinados

- [ ] **Descuento por item + descuento global — caso basico:**
  1. 3 productos: A=$100, B=$200, C=$50.
  2. Descuento 20% a producto B. Nuevo precio B: $160.
  3. Descuento global 10% al ticket.
  4. **Verificar:** Subtotal con desc. item = $310. Desc global 10% = $31. Total = $279. Matematica exacta.
- [ ] **Descuento 100% en un producto (regalo):**
  1. Agregar producto. Descuento 100%.
  2. **Verificar:** Precio del item = $0.00. Total refleja $0 por ese item.
  3. Cobrar con otros items. **Verificar:** Venta se registra. Item regalado aparece con total $0.
- [ ] **VIP — descuento maximo combinado:**
  1. A: $1000, desc individual 40% = $600. B: $500, desc individual 30% = $350. Subtotal = $950.
  2. Desc global 20%. Total = $950 * 0.80 = $760.
  3. **Verificar:** Total = $760.00. Descuento total efectivo = $1500 - $760 = $740 (49.33%).
- [ ] **VIP — todos los items con descuento diferente + global:**
  1. A: $200, 5% = $190. B: $300, 10% = $270. C: $100, 15% = $85. D: $400, 20% = $320.
  2. Subtotal = $865. Desc global 8%.
  3. Total = $865 * 0.92 = $795.80.
  4. **Verificar:** Total exacto = $795.80.
- [ ] **VIP — descuento individual a producto ya en mayoreo:**
  1. Producto: retail $100, mayoreo $80. Modo mayoreo activo.
  2. Agregar. Desc individual 10%. Subtotal = $80 * 0.90 = $72.
  3. Desc global 5%. Total = $72 * 0.95 = $68.40.
  4. **Verificar:** Total = $68.40. Triple descuento (mayoreo + individual + global).

### 11.6 Errores Comunes del Cajero Real

- [ ] **Cancelar venta ya cobrada:**
  1. Hacer una venta. Ir a Historial. Buscar por folio.
  2. Intentar cancelar la venta.
  3. **Verificar:** Se requiere confirmacion y/o PIN de gerente. Stock se restaura.
- [ ] **Cobrar por error y querer deshacer:**
  1. Cobrar venta accidentalmente (producto equivocado).
  2. Inmediatamente ir a Historial y cancelar.
  3. **Verificar:** Cancelacion exitosa. Stock restaurado. Total del turno ajustado.
- [ ] **Buscar producto que acaba de crearse:**
  1. Ir a Productos. Crear `Nuevo Prueba QA`. Stock: 10.
  2. Sin recargar, ir a Terminal (F1). Buscar `Nuevo Prueba`.
  3. **Verificar:** El producto aparece inmediatamente (pull de productos actualizado).
- [ ] **Aplicar descuento por error y querer quitarlo:**
  1. Agregar producto. Aplicar desc individual 50%. Darse cuenta del error.
  2. Cambiar descuento a 0%.
  3. **Verificar:** Precio vuelve al original. Sin residuo del descuento anterior.

### 11.7 Notificaciones Remotas

- [ ] **Recibir notificacion del gerente:**
  1. Desde Remoto (gerente), enviar notificacion con titulo y cuerpo.
  2. En Terminal (cajero), verificar que la notificacion se recibe.
  3. **Verificar:** Notificacion visible con contenido correcto.
- [ ] **Cambio de precio remoto:**
  1. Desde Remoto, cambiar precio de un producto con motivo.
  2. En Terminal, buscar ese producto.
  3. **Verificar:** Precio actualizado sin necesidad de recargar pagina.

### 11.8 Ventas con IVA — Verificacion de Desglose Fiscal

- [ ] **Verificar IVA en venta simple:**
  1. Producto $116.00 (precio con IVA). Vender 1 unidad.
  2. **Verificar en detalle de venta:**
    - Base: $100.00 ($116 / 1.16)
    - IVA: $16.00
    - Total: $116.00
- [ ] **IVA con descuento individual:**
  1. Producto $116.00. Descuento 10% = $104.40.
  2. **Verificar:**
    - Monto con descuento: $104.40
    - Base: $104.40 / 1.16 = $90.00
    - IVA: $90.00 * 0.16 = $14.40
    - Total: $90.00 + $14.40 = $104.40
- [ ] **IVA con descuento global:**
  1. 2 productos: $116 + $232 = $348. Desc global 10% = $313.20.
  2. **Verificar:** Base = $313.20 / 1.16 = $270.00. IVA = $43.20. Total = $313.20.
- [ ] **IVA con multiples items y descuentos variados:**
  1. A: $580 (base $500), desc 20%. B: $232 (base $200), sin desc. C: $116 (base $100), desc 50%.
  2. A descontado: $464. B: $232. C: $58. Subtotal: $754.
  3. **Verificar:** IVA total corresponde a base total / 1.16 * 0.16.

---

## FASE 12: Fiscal y Operaciones Avanzadas

### 12.1 Facturacion CFDI — Claves SAT

- [ ] **Generar factura de venta individual:**
  1. Ir a Fiscal > Facturacion. Seleccionar una venta reciente.
  2. Llenar datos: RFC, Nombre, Regimen, CP, Forma de Pago, Uso CFDI.
  3. Generar CFDI. **Verificar:** Respuesta exitosa con UUID fiscal.
- [ ] **Datos fiscales invalidos:**
  1. Intentar con RFC invalido (`ABC`). **Verificar:** Rechazado.
  2. Intentar sin CP. **Verificar:** Rechazado.
- [ ] **CFDI global (multiples ventas):**
  1. Seleccionar 5 ventas del dia. Generar CFDI global.
  2. **Verificar:** La factura abarca las 5 ventas correctamente.
- [ ] **CFDI verifica claves SAT en conceptos:**
  1. Venta con 3 productos: clave `50181700`, `50202300`, `01010101`.
  2. Generar CFDI.
  3. **Verificar:** Cada concepto tiene su `ClaveProdServ` correcta en el XML.
- [ ] **CFDI con clave unidad diferente:**
  1. Producto a granel con `ClaveUnidad = KGM`. Vender. Facturar.
  2. **Verificar:** Concepto muestra `ClaveUnidad="KGM"`, no `H87`.
- [ ] **CFDI con descuento — nodo Descuento en XML:**
  1. Venta con descuento individual 15% en producto de $1000.
  2. Facturar.
  3. **Verificar:** El nodo `<cfdi:Concepto>` incluye atributo `Descuento` con el monto correcto.
- [ ] **CFDI con metodo de pago correcto:**
  1. Venta en efectivo → FormaPago `01`.
  2. Venta en tarjeta → FormaPago `04`.
  3. Venta en transferencia → FormaPago `03`.
  4. **Verificar:** Cada factura usa la forma de pago correcta.

### 12.2 Catalogo SAT — Validaciones

- [ ] **Verificar claves SAT comunes del catalogo:**
  1. Alimentos preparados: `50192100`. **Verificar:** Valida.
  2. Bebidas alcoholicas: `50202200`. **Verificar:** Valida.
  3. Tabaco: `50201700`. **Verificar:** Valida.
  4. Medicamentos: `51241900`. **Verificar:** Valida.
  5. Ropa: `53100000`. **Verificar:** Valida.
- [ ] **Clave unidad — variantes:**
  1. Pieza: `H87`. Kilogramo: `KGM`. Litro: `LTR`. Metro: `MTR`.
  2. **Verificar:** Todas se aceptan en productos.
- [ ] **Producto con clave SAT especifica genera factura correcta:**
  1. Crear producto: `Cerveza Artesanal 355ml`, clave SAT `50202200`, unidad `H87`.
  2. Vender. Facturar.
  3. **Verificar:** XML contiene `ClaveProdServ="50202200"` y `ClaveUnidad="H87"`.

### 12.3 Monitoreo Remoto

- [ ] **Ver ventas en tiempo real:**
  1. Ir a Remoto. **Verificar:** Se muestran las ultimas 20 ventas.
  2. Hacer una venta en Terminal. Volver a Remoto (o esperar refresh).
  3. **Verificar:** La nueva venta aparece en el feed.
- [ ] **Abrir cajon remotamente:**
  1. En Remoto, clic "Abrir Cajon".
  2. **Verificar:** Solicitud enviada exitosamente.
- [ ] **Estado del turno en tiempo real:**
  1. En Remoto, verificar estado del turno activo.
  2. Hacer una venta en Terminal.
  3. Refrescar Remoto. **Verificar:** Estadisticas actualizadas.
- [ ] **Remoto muestra descuentos en ventas:**
  1. Hacer venta con descuento 20%.
  2. En Remoto. **Verificar:** Venta muestra descuento aplicado.

### 12.4 Estadisticas y Dashboards

- [ ] **Dashboard del dia:**
  1. Ir a Estadisticas. **Verificar:** Ventas de hoy, total, mermas pendientes se muestran.
- [ ] **Dashboard ejecutivo (solo manager+):**
  1. Loguearse como manager/admin. Ir a Estadisticas.
  2. **Verificar:** Se muestran paneles avanzados (RESICO, Wealth, AI si estan habilitados).
  3. Loguearse como cajero. **Verificar:** Paneles restringidos no visibles.

---

## FASE 13: Escenarios Caoticos Terminales

Lo peor que puede pasar en una tienda real. Si el sistema sobrevive esto, sobrevive todo.

### 13.1 Apagon Electrico Simulado

- [ ] **Cerrar navegador a la fuerza mid-cobro:**
  1. Cargar carrito. Presionar Cobrar. Inmediatamente `Alt+F4` (cerrar navegador).
  2. Reabrir navegador. Loguearse.
  3. **Verificar:** Turno se recupera. Venta se registro (o no, pero sin duplicado). Tickets pendientes intactos en localStorage (si no se cobraron).
- [ ] **Matar el proceso del backend mid-transaccion:**
  1. Preparar venta grande (10 items).
  2. Cobrar. Mientras se procesa, `kill -9 <PID>` al proceso FastAPI.
  3. Reiniciar backend. Recargar frontend.
  4. **Verificar:** La venta o se completo atomicamente o no existe. No hay venta a medias (items parciales).
- [ ] **Apagon durante venta con descuento combinado:**
  1. Ticket con desc individual 15% + global 10%. Cobrar. Alt+F4.
  2. Reabrir. **Verificar:** Si la venta paso, descuentos son correctos. Si no paso, se puede reintentar.

### 13.2 Corrupcion de Datos Local

- [ ] **JSON roto en localStorage:**
  1. `localStorage.setItem('titan.currentShift', '{{{ROTO')`.
  2. Recargar pagina.
  3. **Verificar:** La app no crashea. Detecta JSON invalido y muestra modal de turno nuevo.
- [ ] **localStorage lleno:**
  1. Llenar localStorage con basura: `for(let i=0;i<10000;i++) localStorage.setItem('basura'+i, 'x'.repeat(1000))`.
  2. Intentar cobrar una venta.
  3. **Verificar:** El cobro funciona (la venta se registra en backend). El localStorage puede fallar al guardar shift pero sin crash.

### 13.3 Ataque de Stress al Backend

- [ ] **200 ventas en 10 minutos (2 PCs al maximo):**
  1. PC-A y PC-B cobran lo mas rapido posible.
  2. Ventas de 1-2 items para maximizar velocidad.
  3. **Verificar:** Ninguna venta se pierde. Ningun folio duplicado. Stock consistente.
- [ ] **50 busquedas simultaneas:**
  1. Ambas PCs buscando productos agresivamente al mismo tiempo.
  2. **Verificar:** Respuestas correctas. Sin timeouts. Backend no se cae.
- [ ] **200 ventas con descuentos variados:**
  1. PC-A: ventas con descuento individual aleatorio (5-30%).
  2. PC-B: ventas con descuento global aleatorio (5-20%).
  3. **Verificar:** Todas las matematicas correctas. Sin drift por acumulacion.

### 13.4 El Peor Caso Combinado

- [ ] **Escenario apocaliptico:**
  1. PC-A: turno abierto, 3 tickets pendientes, carrito con 8 items.
  2. PC-B: turno abierto, 1 ticket pendiente, a punto de cobrar.
  3. Apagar la red del servidor (backend inaccesible para ambas PCs).
  4. PC-A intenta cobrar → error de red. Ticket intacto.
  5. PC-B intenta cobrar → error de red. Ticket intacto.
  6. Restaurar red.
  7. PC-B cobra exitosamente su venta.
  8. PC-A cobra sus 3 tickets pendientes uno por uno.
  9. **Verificar:** 4 ventas registradas. 0 duplicados. Stock correcto. Folios secuenciales.
- [ ] **Apocalipsis con descuentos:**
  1. Tickets pendientes: T1 desc global 10%, T2 desc individual 25%, T3 sin desc.
  2. Red muere. Red revive. Cobrar los 3.
  3. **Verificar:** Cada descuento intacto. Totales correctos.

### 13.5 Datos Numericos Extremos

- [ ] **Venta de $0.01 (centavo):**
  1. Producto de $1.00. Descuento 99%.
  2. **Verificar:** Total = $0.01. Se puede cobrar. Aparece en historial.
- [ ] **Venta de $99,999.99:**
  1. Producto de $9,999.99. Cantidad: 10.
  2. **Verificar:** Total se calcula sin overflow. Se cobra correctamente.
- [ ] **Monto recibido extremo:**
  1. Venta de $50. Monto recibido: $10,000.
  2. **Verificar:** Cambio = $9,950.00. Se muestra correctamente.
- [ ] **Descuentos con redondeo problematico:**
  1. 3 productos de $33.33 cada uno. Total: $99.99.
  2. Descuento global 7%. Total esperado: $92.99 (redondeado).
  3. **Verificar:** Total es matematicamente consistente.
- [ ] **Descuento sobre precio con muchos decimales internos:**
  1. Producto $99.99. Descuento 13%. Esperado: $86.99 (redondeo HALF_UP).
  2. **Verificar:** Consistente en frontend y backend.
- [ ] **Descuento que da exactamente 0.005 (redondeo bancario):**
  1. Producto $1.00. Descuento 0.5%. Esperado: $0.995 → $1.00 o $0.99.
  2. **Verificar:** Redondeo consistente (HALF_UP = $1.00).

### 13.6 Integridad de Datos Post-Caos

- [ ] **Auditoria final de integridad:**
  1. Tras todas las pruebas, ir a Reportes. Generar reporte de todo el dia.
  2. Sumar TODAS las ventas del Historial (efectivo + tarjeta + transferencia).
  3. Comparar con el total del Reporte.
  4. **Verificar:** Los numeros coinciden al centavo.
  5. Seleccionar 10 productos al azar. Verificar stock = stock_inicial - unidades_vendidas.
  6. **Verificar:** Sin variaciones fantasma en ningun producto.
- [ ] **Auditoria de descuentos post-caos:**
  1. Seleccionar 10 ventas con descuento del dia.
  2. Recalcular manualmente cada una.
  3. **Verificar:** Cada total = precio * qty * (1-desc_individual%) * (1-desc_global%). Al centavo.
- [ ] **Auditoria de claves SAT post-caos:**
  1. Seleccionar 5 ventas con productos que tenian clave SAT especifica.
  2. **Verificar:** Cada `sale_item` tiene la clave SAT correcta del producto al momento de la venta.
- [ ] **Auditoria de folios post-caos:**
  1. Exportar/revisar todos los folios del dia.
  2. **Verificar:** Secuenciales, sin huecos, sin duplicados. Formato correcto (serie + terminal + numero).

---

## Resumen de Cobertura

| Fase | Escenarios | Enfoque |
|------|-----------|---------|
| 1 | 24 | Regresion V7 (empleados, clientes, polling, dirty state) |
| 2 | 55 | Operaciones cotidianas (productos, descuentos, SAT, ventas) |
| 3 | 24 | Escenarios complejos del dia a dia |
| 4 | 11 | Volumen y estres (500+ ventas con descuentos) |
| 5 | 10 | Concurrencia y race conditions |
| 6 | 8 | Caos de red y resiliencia |
| 7 | 11 | Fatiga de memoria y abuso UI |
| 8 | 10 | Cierre de turno masivo y auditoria |
| 9 | 26 | Escenarios caoticos extremos y matematicas de descuento |
| 10 | 14 | Dos terminales fisicas (2 PCs) |
| 11 | 24 | Mas escenarios cotidianos, IVA, descuentos VIP |
| 12 | 14 | Fiscal CFDI, claves SAT, monitoreo remoto |
| 13 | 16 | Escenarios caoticos terminales y auditoria final |
| **Total** | **~247** | **Cobertura integral con enfasis en descuentos y SAT** |
