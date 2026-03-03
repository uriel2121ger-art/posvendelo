# Plan de Pruebas Manuales V9 — TITAN POS

Guia de pruebas manuales consolidada. Organizada por prioridad de ejecucion, sin duplicados, con criterios de pase/fallo explicitos.

**Prerequisitos:**
- Backend corriendo en `localhost:8090`
- Al menos 10 productos con stock variado (0, 1, 5, 20, 50+)
- Al menos 3 clientes registrados
- Al menos 1 producto con precio mayoreo definido
- Al menos 1 producto con clave SAT especifica (no default `01010101`)
- Usuario admin/manager logueado

**Nota fiscal:** El backend asume `price_includes_tax=True`. Producto $116.00 = base $100.00 + IVA $16.00. Descuentos se aplican al precio con IVA; el desglose fiscal se calcula despues.

**Convencion de esta guia:**
- `[P]` = Paso individual
- `[V]` = Verificacion (criterio de pase/fallo)
- `BLOCKER` = Si falla, detener pruebas y reportar
- Cada seccion indica tiempo estimado para el tester

---

## FASE 0: Regresion de Bugs V8 (EJECUTAR PRIMERO)

> Tiempo estimado: 20 min
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

### 0.3 Carrito vacio — Cobro bloqueado

**Bug V8:** Se podia procesar venta en $0.00 con carrito vacio.

- [ ] **Intentar cobrar sin productos:**
  - [P] Terminal con carrito vacio. Clic Cobrar.
  - [V] Boton Cobrar esta deshabilitado (gris) cuando `cart.length === 0`.
  - [V] Si se fuerza de alguna forma: mensaje "No hay productos en el ticket."
  - [V] No se genera folio ni se registra venta.

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

### 0.5 Monitoreo remoto — Consistencia de datos

**Bug V8:** Dashboard reportaba monto total pero 0 ventas y tabla vacia.

- [ ] **Feed de ventas en vivo:**
  - [P] Hacer 3 ventas en Terminal.
  - [P] Ir a Remoto. Esperar auto-refresh (10s).
  - [V] La tabla "Ventas en Vivo" muestra las ventas recientes (no vacia).
  - [V] El contador de "Ventas" coincide con la cantidad de filas visibles (o cercano — puede haber desfase de 1 por timing).
  - [V] El "Total del Turno" coincide con la suma real.

### 0.6 Disaster recovery — Badge con conteo real

**Bug V8:** Al recuperar turno perdido, badge mostraba "0 ventas" pero monto correcto.

- [ ] **Recuperar turno con historial:**
  - [P] Abrir turno. Hacer 5 ventas ($50 c/u = $250 total).
  - [P] `localStorage.removeItem('titan.currentShift')`. Recargar (F5).
  - [V] Modal detecta turno abierto y lo recupera.
  - [V] Tras recuperar, badge muestra `5 ventas / $250.00` (no `0 ventas / $250.00`).

---

## FASE 1: Flujo Critico de Negocio (Happy Path)

> Tiempo estimado: 30 min
> Prioridad: BLOCKER — es el dia a dia del cajero

### 1.1 Apertura y Primera Venta

- [ ] **Abrir turno con fondo:**
  - [P] Login. Abrir turno con fondo `$2,500.50` (con centavos).
  - [V] Badge muestra operador y "0 ventas / $0.00". Fondo registrado con centavos.
- [ ] **Venta con efectivo y cambio:**
  - [P] Buscar producto. Agregar 2 unidades. Total ~$X.
  - [P] Metodo: Efectivo. Monto recibido: $500.
  - [V] Cambio calculado = $500 - Total. Badge: "1 venta".
- [ ] **Venta con tarjeta:**
  - [P] 3 productos variados. Metodo: Tarjeta. Cobrar.
  - [V] No pide monto recibido. Venta registrada.
- [ ] **Venta por transferencia:**
  - [P] 1 producto. Metodo: Transferencia. Cobrar.
  - [V] Venta registrada con metodo `transfer`.
- [ ] **Pago exacto en efectivo (campo vacio):**
  - [P] Total $58. Monto recibido: vacio. Cobrar.
  - [V] Sistema asume pago exacto. Cambio: $0.00.

### 1.2 Busqueda de Productos

- [ ] **Por nombre parcial:** Buscar `coca`. [V] Resultados con "coca" en nombre.
- [ ] **Por SKU:** Buscar SKU exacto. [V] Producto encontrado.
- [ ] **Inexistente:** Buscar `XYZNOEXISTE999`. [V] Lista vacia, sin crash.
- [ ] **Caracteres especiales:** Buscar `%`, `'`, `"`. [V] Sin errores SQL. Resultados vacios o parciales.
- [ ] **Un solo caracter:** Buscar `a`. [V] Retorna resultados sin timeout.

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

### 1.4 Descuentos — Matriz Matematica

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
- [ ] **Doble pesado — ind 30% + global 20%:**
  - [P] $1000, desc ind 30% = $700. Desc global 20%.
  - [V] Total = $560.00. Efectivo = 44%.
- [ ] **Desc 100% (regalo):** $300, desc 100%. [V] Subtotal = $0. Se puede cobrar con otros items.
- [ ] **Desc 99.99%:** $10,000, desc 99.99%. [V] Subtotal = $1.00.
- [ ] **Quitar descuento:** Aplicar 50%, luego cambiar a 0%. [V] Precio original restaurado.

### 1.5 Tickets Pendientes

- [ ] **Pausar y retomar:**
  - [P] 5 productos en carrito. Guardar como pendiente. Hacer otra venta. Retomar.
  - [V] Los 5 productos originales siguen con sus cantidades y precios.
- [ ] **Pendiente con descuento individual:**
  - [P] 3 items, item 2 con 15% desc. Pausar. Retomar.
  - [V] Descuento sigue aplicado.
- [ ] **Pendiente con descuento global:**
  - [P] Ticket con desc global 10%. Pausar. Retomar.
  - [V] Descuento global intacto. Totales correctos.
- [ ] **Pendiente con cliente asignado:**
  - [P] Asignar cliente. Pausar. Retomar.
  - [V] Cliente sigue asignado.
- [ ] **Multiples pendientes (4):**
  - [P] Crear 4 tickets con diferentes productos. Navegar entre ellos.
  - [V] Cada ticket conserva carrito, cliente y metodo. Cobrar todos. Todos registrados.

### 1.6 Modo Mayoreo

- [ ] **Toggle mayoreo:**
  - [P] Activar mayoreo. Agregar producto con precio mayoreo.
  - [V] Precio mostrado = mayoreo. Desactivar: precio = normal.
- [ ] **Producto sin mayoreo en modo mayoreo:**
  - [P] Activar mayoreo. Agregar producto sin precio mayoreo.
  - [V] Usa precio normal como fallback.
- [ ] **Mayoreo + descuento individual:**
  - [P] Mayoreo $80. Desc ind 10%.
  - [V] $72.00.
- [ ] **Mayoreo en ticket pendiente:**
  - [P] Modo mayoreo. Agregar producto. Pausar. Retomar.
  - [V] Precio mayoreo se conserva.

### 1.7 Cierre de Turno y Reapertura

- [ ] **Cerrar turno con corte:**
  - [P] Tras varias ventas, ir a Turnos. Cerrar turno. Ingresar efectivo contado.
  - [V] Muestra: Esperado vs Contado vs Diferencia. Cierre < 8 segundos.
- [ ] **Diferencia en corte — sobrante:** Contado > Esperado. [V] Diferencia positiva.
- [ ] **Diferencia en corte — faltante:** Contado < Esperado. [V] Diferencia negativa.
- [ ] **Reapertura limpia:**
  - [P] Abrir nuevo turno $1,000. Hacer 1 venta de $40.
  - [V] Badge = "1 venta / $40.00". Sin arrastre del turno anterior.

---

## FASE 2: Integridad de Datos y Seguridad

> Tiempo estimado: 25 min
> Prioridad: ALTA — previene perdida de dinero y corrupcion

### 2.1 Stock y Sobreventa

- [ ] **Producto con stock 0:**
  - [P] Agregar producto con stock 0 al carrito. Cobrar.
  - [V] Backend rechaza: "Stock insuficiente para X. Disponible: 0, Solicitado: 1."
- [ ] **Agotar stock parcial:**
  - [P] Producto con 5 unidades. Agregar 10 al carrito. Cobrar.
  - [V] Rechazado. Stock nunca llega a negativo.
- [ ] **Entrada de inventario:**
  - [P] Ir a Inventario (F4). Producto existente. Registrar entrada +24.
  - [V] Stock actualizado. En Terminal, producto refleja las 24 adicionales.

### 2.2 Precio en Vuelo (Backend Valida)

- [ ] **Cambiar precio con ticket abierto:**
  - [P] Agregar "Producto X" ($100) al carrito. En otra pestana, cambiar precio a $200. Cobrar $100.
  - [V] Backend rechaza por monto insuficiente (valida precio real de DB, no del frontend).

### 2.3 Cobro Fantasma Post-Turno

- [ ] **Ticket huerfano:**
  - [P] Pestana A: carrito con productos. Pestana B: cerrar turno.
  - [P] Pestana A: cobrar.
  - [V] Rechazado: "No hay turno abierto."

### 2.4 Doble Clic en Cobrar

- [ ] **Doble clic rapido:**
  - [P] Productos en carrito. Doble clic en Cobrar.
  - [V] Solo 1 venta registrada. Boton se deshabilita durante busy.

### 2.5 Inyeccion XSS y SQL

- [ ] **XSS en busqueda:** `<script>alert(1)</script>`. [V] No se ejecuta JS.
- [ ] **XSS en nombre de producto:** `<img onerror=alert(1) src=x>`. [V] Texto plano.
- [ ] **SQL injection:** `'; DROP TABLE products; --`. [V] Sin error SQL.
- [ ] **Zalgo text:** `T̴̡e̵s̷t̴`. [V] Sin crash. Busqueda funciona.
- [ ] **Caracteres nulos:** `\0\t\n`. [V] Caracteres de control stripeados.
- [ ] **Emojis:** Producto `Cerveza Premium`. [V] Se crea y busca correctamente.

### 2.6 Proteccion de Sesion

- [ ] **localStorage.clear() con ticket:**
  - [P] 10 items en carrito. `localStorage.clear()`. Cobrar.
  - [V] Error claro o redireccion a Login. Sin pantalla blanca.
- [ ] **Token invalido:**
  - [P] `localStorage.setItem('titan.token', 'expired.jwt.token')`. Cobrar.
  - [V] Error 401. Redireccion a Login.
- [ ] **Config corrupta:**
  - [P] `localStorage.setItem('titan.config', '{basura}')`. Recargar.
  - [V] App carga con defaults o muestra pantalla de config. Sin crash.
- [ ] **JSON roto en shift:**
  - [P] `localStorage.setItem('titan.currentShift', '{{{ROTO')`. Recargar.
  - [V] App detecta JSON invalido. Muestra modal de turno. Sin WSOD.

---

## FASE 3: CRUD Completo de Entidades

> Tiempo estimado: 25 min
> Prioridad: ALTA — operaciones diarias del manager

### 3.1 Productos

- [ ] **Crear basico:** SKU `AGUA-001`, Nombre `Agua Purificada 1L`, Precio $15, Stock 100. [V] Aparece en lista y en Terminal.
- [ ] **Crear con mayoreo:** SKU `JABON-001`, Precio $25, Mayoreo $20. [V] En Terminal: mayoreo = $20, normal = $25.
- [ ] **Editar precio:** Cambiar $100 a $120. [V] Terminal refleja $120.
- [ ] **Editar SKU:** Cambiar `AGUA-001` a `AGUA-PUR-001`. [V] Buscar por nuevo: encontrado. Por viejo: no.
- [ ] **Precio minimo $0.01:** Vender 5 uds. [V] Total = $0.05.
- [ ] **Precio alto $99,999.99:** Vender 1. [V] Total correcto sin overflow.
- [ ] **Nombre largo (150+ chars):** [V] Se crea. En Terminal truncado con ellipsis.
- [ ] **SKU con caracteres especiales:** `TORN-1/4x2`, `P&G-001`. [V] Ambos aceptados.
- [ ] **Desactivar producto:** [V] No aparece en busquedas de Terminal.
- [ ] **Stock negativo protegido:** Producto con 5, vender 10. [V] Rechazado.

### 3.2 Claves SAT en Productos

- [ ] **Default:** Crear producto sin clave SAT. [V] `sat_clave_prod_serv = '01010101'`, `sat_clave_unidad = 'H87'`.
- [ ] **Asignar especifica:** Galletas `50181700`, Refresco `50202300`. [V] Persisten tras recargar.
- [ ] **Cambiar clave existente:** De `01010101` a `50181700`. [V] Actualizada.
- [ ] **Clave unidad diferente:** Frijol a granel `KGM`. [V] Persiste como `KGM`.
- [ ] **Clave SAT se copia a sale_items:** Vender producto con clave `50202300`. [V] En historial/API: `sale_items.sat_clave_prod_serv = '50202300'`.

### 3.3 Clientes

- [ ] **Crear:** `Maria Lopez`, tel: `5559876543`. [V] Aparece en lista.
- [ ] **Duplicado local:** Crear `maria lopez` (minusculas). [V] Bloqueado SIN request al backend.
- [ ] **Duplicado backend (409):** Segunda pestana sin recargar. [V] Error 409.
- [ ] **Duplicado con espacios:** `  Roberto   Diaz  `. [V] Detectado (TRIM + LOWER).
- [ ] **Persiste tras recarga:** Crear, cerrar, reabrir. [V] Sigue ahi.
- [ ] **Solo nombre (sin tel/email):** [V] Se crea. Campos opcionales vacios.
- [ ] **Editar telefono:** Cambiar, guardar, recargar. [V] Persiste.
- [ ] **Asignar a venta:** [V] En historial la venta muestra el cliente correcto.
- [ ] **Cambiar cliente a mitad de captura:** Seleccionar A, agregar items, cambiar a B, cobrar. [V] Venta con cliente B.

### 3.4 Empleados — Ciclo Completo

- [ ] **CRUD:** Crear `EMP-TEST`, editar salario, eliminar. Recargar. [V] No reaparece.
- [ ] **Comision se guarda como decimal:** Crear con comision `15`. Recargar. [V] Muestra `15.00`.
- [ ] **Comision 0% y 100%:** [V] `0.00` y `100.00` respectivamente.
- [ ] **Comision con decimales:** `7.5`. [V] Muestra `7.50`.
- [ ] **Notas persisten:** Crear con notas. Recargar. [V] Notas completas.
- [ ] **Codigo duplicado:** Crear 2 con `DUP-001`. [V] Segundo rechazado.
- [ ] **Caracteres especiales:** `Maria Jose Nono-Garcia`. [V] Acentos y n intactos.

### 3.5 Gastos Operativos

- [ ] **Registrar gasto:** $350, `Compra de papel para tickets`. [V] Aparece con timestamp correcto.
- [ ] **Gasto invalido:** Monto 0. [V] Rechazado (422).
- [ ] **Gasto con centavos:** $123.45. [V] Centavos exactos.

---

## FASE 4: Navegacion, UX y Configuracion

> Tiempo estimado: 15 min
> Prioridad: MEDIA — usabilidad diaria

### 4.1 Teclas F — Navegacion Rapida

- [ ] **F1-F6 ciclo completo:** F1=Terminal, F2=Clientes, F3=Productos, F4=Inventario, F5=Turnos, F6=Reportes. [V] Instantaneo (< 200ms). Sin parpadeo.
- [ ] **F1 desde cualquier tab:** [V] Terminal visible. Carrito intacto.
- [ ] **F7 (Entrada), F8 (Retiro), F9 (Verificador):** Abren modal. Esc cierra. [V] Sin afectar estado.
- [ ] **F9 no afecta carrito:** Con 3 items, F9, buscar producto, Esc. [V] Carrito intacto.
- [ ] **Abrir/cerrar F9 x10 rapido:** [V] Sin leak de modales.

### 4.2 Movimientos de Caja

- [ ] **F7 entrada:** $1500, motivo: `Pago proveedor`. [V] Exito.
- [ ] **F8 retiro:** $800, motivo: `Pago repartidor`. [V] Registrado.
- [ ] **F8 con PIN gerente:** PIN correcto = aceptado. PIN incorrecto = rechazado.
- [ ] **Centavos:** F7 $1,234.56. [V] Monto exacto.

### 4.3 Verificador de Precios (F9)

- [ ] **Consulta rapida:** Buscar producto. [V] Muestra precio, mayoreo, stock.
- [ ] **Producto sin stock:** [V] Muestra precio y stock = 0.
- [ ] **Producto inexistente:** [V] "Sin resultados".

### 4.4 Dirty State — Settings y Hardware

- [ ] **Settings bloquea navegacion:**
  - [P] Cambiar URL. NO guardar. Presionar F1.
  - [V] Dialogo "cambios sin guardar". Cancelar: sigues en Settings. Aceptar: sale sin guardar.
- [ ] **Settings guardar limpia dirty:**
  - [P] Cambiar Token. Guardar. Presionar F1.
  - [V] NO aparece dialogo.
- [ ] **Hardware dirty state:** Cambiar nombre impresora. Navegar sin guardar. [V] Dialogo aparece.
- [ ] **Perfiles de config:** Guardar perfil `Caja 2`, cambiar config, cargar perfil. [V] Config restaurada.

### 4.5 Historial y Reportes

- [ ] **Buscar por folio:** [V] Venta con todos sus detalles.
- [ ] **Filtrar por fecha:** Solo hoy. [V] Coincide con badge de turno.
- [ ] **Verificar descuentos en historial:** Venta con 20% desc en $500. [V] Descuento = $100.
- [ ] **Metodo de pago en historial:** 3 ventas (efectivo, tarjeta, transferencia). [V] Cada una con metodo correcto.

---

## FASE 5: Concurrencia y Multi-Terminal

> Tiempo estimado: 30 min
> Prioridad: ALTA — previene corrupcion de datos en produccion multi-caja

### 5.1 Multi-Pestana — Mismo Backend

- [ ] **Badges sincronizados por polling:**
  - [P] 2 pestanas mismo turno. Pestana A: 3 ventas. Pestana B: esperar 60-70s.
  - [V] Badge en B refleja las 3 ventas.
- [ ] **5 pestanas, 20 ventas alternadas:**
  - [P] 5 pestanas. Ventas alternando. Mezcla metodos y montos.
  - [V] Folios secuenciales sin huecos ni duplicados.
- [ ] **Descuentos en pestanas separadas:**
  - [P] A: desc ind 20%. B: desc global 10%. C: ind 15% + global 5%. Cobrar casi simultaneo.
  - [V] Cada descuento correcto. Sin mezcla entre pestanas.

### 5.2 Colision de Stock

- [ ] **Stock bajo + cobros simultaneos:**
  - [P] Producto con 5 uds. A: 4 uds, B: 4 uds, C: 3 uds. Cobrar las 3 < 2 seg.
  - [V] Solo primer cobro pasa. Los demas rechazados. Stock nunca negativo.
- [ ] **Ultima unidad — carrera:**
  - [P] Producto con 1 ud. Ambas pestanas cobran simultaneo.
  - [V] Solo 1 pasa. Stock = 0.
- [ ] **Edicion simultanea de producto:**
  - [P] A: precio $99. B: precio $150. Guardar ambos casi al mismo tiempo.
  - [V] Uno gana. Sin corrupcion. Precio final es uno de los dos.

### 5.3 Operaciones Cruzadas

- [ ] **Cerrar turno en A, cobrar en B:**
  - [P] A cierra turno. B (sin recargar) intenta cobrar.
  - [V] B detecta turno cerrado. Error claro.
- [ ] **Editar precio en A, cobrar en B:**
  - [P] A cambia precio $100 a $200. B cobra con precio viejo.
  - [V] Backend usa precio real de DB.
- [ ] **Crear producto en A, vender en B:**
  - [P] A crea `Nuevo Producto`, stock 20. B busca y vende 3.
  - [V] Stock = 17.

### 5.4 Dos Terminales Fisicas (si hay 2 PCs)

> Requiere 2 PCs o 2 perfiles de navegador con diferente `terminalId`

- [ ] **Apertura de 2 cajas:**
  - [P] PC-A: cajero1, fondo $2,500. PC-B: cajero2, fondo $3,000.
  - [V] Cada PC muestra su operador. Backend ve 2 turnos abiertos.
- [ ] **Ventas simultaneas:**
  - [P] Ambas PCs cobran al mismo tiempo. Repetir 20 veces.
  - [V] 20 ventas cada una. Folios unicos.
- [ ] **Agotamiento cruzado:**
  - [P] Producto con 3 uds. A: 2 uds, B: 2 uds. A cobra primero.
  - [V] A exitosa (stock = 1). B rechazada.
- [ ] **Cierre escalonado:**
  - [P] A cierra turno. B sigue operando normalmente.
  - [V] Cierre de A no afecta B. Cada corte muestra solo sus ventas.
- [ ] **Reportes muestran ambas terminales:**
  - [P] Generar reporte del dia.
  - [V] Total incluye ventas de AMBAS terminales.

---

## FASE 6: Resiliencia de Red

> Tiempo estimado: 15 min
> Prioridad: ALTA — la tienda no puede parar si cae la red

### 6.1 Desconexion Total

- [ ] **Cobrar sin red:**
  - [P] Ticket con productos. DevTools > Network > Offline. Cobrar.
  - [V] No se congela. Toast: "No se pudo conectar al servidor. El ticket sigue intacto."
- [ ] **Guardar pendiente sin red:**
  - [P] Mismo ticket. Clic Guardar.
  - [V] Se encola en "Pendientes (1)". Caja liberada.
- [ ] **Reconectar y cobrar:**
  - [P] Restaurar red. Retomar ticket. Cobrar.
  - [V] Venta exitosa. Sin duplicados en historial.

### 6.2 Micro-Cortes

- [ ] **Apagar red al momento de cobrar (5 intentos):**
  - [P] Preparar venta. Al presionar Cobrar, apagar red. Esperar 2s. Encender.
  - [V] Venta se registro O muestra error limpio. Revisar historial: 0 duplicados.

### 6.3 Backend Muerto

- [ ] **Detener FastAPI:**
  - [P] Matar servidor. Intentar: cobrar, buscar, abrir turno.
  - [V] Cada operacion: error claro. Sin pantalla blanca.
- [ ] **Reiniciar backend:**
  - [P] Reiniciar servidor.
  - [V] Operaciones funcionan sin recargar pagina.

### 6.4 Latencia Extrema

- [ ] **3G Lento:**
  - [P] DevTools > Network > Slow 3G. Buscar, cobrar, corte de caja.
  - [V] Spinner visible. UI no se congela. Boton Cobrar muestra busy/disabled. Sin doble envio.

---

## FASE 7: Estres y Volumen

> Tiempo estimado: 45+ min (puede ser en segundo plano)
> Prioridad: MEDIA — valida rendimiento bajo carga real

### 7.1 Rafaga de Ventas (50 rapidas)

- [ ] **50 ventas en < 30 min:**
  - [P] Ventas de 1-3 items. Alternar: 60% efectivo, 25% tarjeta, 15% transferencia.
  - [P] Cada ~10 ventas, aplicar descuento variado (5-30% individual o 5-20% global).
  - [P] Cada ~15 ventas, movimiento de caja (F7 o F8).
  - [V] Sin lag acumulado. Cada cobro limpia carrito. Badge actualizado.
  - [V] Descuentos correctos en cada caso.

### 7.2 Ventas con Complejidad

- [ ] **Tickets de 5+ items con descuentos:**
  - [P] 10 ventas de 5+ items. Mezclar: solo individuales, solo globales, compuestos, sin descuento.
  - [V] Todos los totales matematicamente correctos.
- [ ] **Tickets con pendientes activos:**
  - [P] Mantener 2-3 pendientes mientras se hacen ventas rapidas. Cada 10 ventas, cobrar un pendiente.
  - [V] Sin acumulacion de memoria. Sin lag progresivo.

### 7.3 Carrito Masivo

- [ ] **100+ items en un ticket:** [V] Scroll fluido. Se cobra exitosamente.
- [ ] **Mismo producto x999 unidades:** [V] Total correcto. Backend rechaza si supera stock.
- [ ] **50 items con descuento global 12%:** [V] Total = sum(subtotales) * 0.88.

### 7.4 Sesion Prolongada

- [ ] **4+ horas sin recargar:**
  - [P] Dejar app abierta toda la sesion de pruebas. Verificar al final.
  - [V] Busquedas y cobros siguen fluidos. Tab < 500MB en DevTools > Memory.

### 7.5 Corte Masivo

- [ ] **Cerrar turno con 100+ ventas:**
  - [P] Ir a Turnos. Cerrar turno.
  - [V] Calculo < 8 segundos. Sin "La pagina no responde". Esperado/Contado/Diferencia correctos.

---

## FASE 8: Escenarios Caoticos

> Tiempo estimado: 20 min
> Prioridad: MEDIA — valida robustez ante lo inesperado

### 8.1 Disaster Recovery

- [ ] **Cerrar navegador a la fuerza mid-cobro (Alt+F4):**
  - [P] Cobrar. Inmediatamente Alt+F4. Reabrir.
  - [V] Turno se recupera. Venta se registro o no (sin duplicado). Pendientes intactos.
- [ ] **Matar backend mid-transaccion:**
  - [P] Cobrar. `kill -9` al proceso FastAPI. Reiniciar.
  - [V] Venta atomica: completa o no existe. Sin items parciales.
- [ ] **F5 durante cobro:**
  - [P] Cobrar. Inmediatamente F5. Revisar historial.
  - [V] Venta registrada 1 sola vez O no se registro (reintentar).

### 8.2 Login Simultaneo

- [ ] **Mismo usuario en 2 navegadores:**
  - [P] Nav A: abrir turno, hacer 5 ventas. Nav B: intentar abrir otro turno.
  - [V] B rechazado (turno ya abierto) O recupera el mismo.
  - [P] B cierra turno. A intenta cobrar.
  - [V] Error claro en A.

### 8.3 Cascada de Errores

- [ ] **Red muere con tickets pendientes:**
  - [P] 3 tickets pendientes (uno con desc ind, otro con global, otro sin desc). Apagar red.
  - [P] Intentar cobrar (fallan). Encender red. Cobrar los 3.
  - [V] 3 ventas registradas. 0 duplicados. Descuentos intactos.

### 8.4 Abuso de UI

- [ ] **Texto de 10,000 chars en buscador:** [V] Sin congelamiento. Sin resultados.
- [ ] **Escribir/borrar rapido (debounce):** `coca` rapido, borrar, `pepsi`. [V] Solo resultado final.
- [ ] **Buscar 50 veces en 30 seg:** [V] UI no se congela. Sin memory leak.

### 8.5 Datos Numericos Extremos

- [ ] **Venta de $0.01:** Producto $1, desc 99%. [V] Total = $0.01. Se cobra.
- [ ] **Venta de $99,999.90:** Producto $9,999.99 x 10. [V] Total correcto.
- [ ] **Cambio extremo:** Venta $50, recibido $10,000. [V] Cambio = $9,950.00.
- [ ] **Descuento sub-centavo:** $3.00, desc 33.33%. [V] Redondeado a 2 decimales.

---

## FASE 9: Fiscal y Facturacion

> Tiempo estimado: 15 min
> Prioridad: MEDIA — requerido para facturacion SAT

### 9.1 CFDI Individual

- [ ] **Generar con datos validos:**
  - [P] Venta reciente. RFC `XAXX010101000`, CP `01000`, Uso `G03`.
  - [V] Feedback visible (loader + resultado/error). Nunca silencio.
- [ ] **Datos invalidos:** RFC `ABC`, sin CP. [V] Rechazado con mensaje.
- [ ] **CFDI con claves SAT en conceptos:**
  - [P] Venta con productos: clave `50181700`, `50202300`, `01010101`.
  - [V] Cada concepto tiene su `ClaveProdServ` correcta.
- [ ] **CFDI con clave unidad diferente:**
  - [P] Producto a granel `KGM`. Vender. Facturar.
  - [V] Concepto muestra `ClaveUnidad="KGM"`.
- [ ] **CFDI con descuento:**
  - [P] Venta con desc ind 15% en producto de $1000.
  - [V] Nodo `Descuento` con monto correcto en concepto.
- [ ] **CFDI metodo de pago:** Efectivo=01, Tarjeta=04, Transferencia=03. [V] Correcto.

### 9.2 IVA — Desglose Fiscal

- [ ] **Venta simple:** $116.00 (con IVA). [V] Base=$100, IVA=$16, Total=$116.
- [ ] **Con descuento individual:** $116, desc 10% = $104.40. [V] Base=$90, IVA=$14.40.
- [ ] **Con descuento global:** $116+$232=$348, desc 10%=$313.20. [V] Base=$270, IVA=$43.20.

### 9.3 Monitoreo Remoto

- [ ] **Ventas en tiempo real:** Hacer venta. Ir a Remoto. [V] Venta aparece en feed.
- [ ] **Estado del turno:** [V] Estadisticas actualizadas tras refresh.
- [ ] **Remoto muestra descuentos:** Venta con desc 20%. [V] Visible en feed.

---

## FASE 10: Auditoria Final Post-Pruebas

> Tiempo estimado: 15 min
> Prioridad: ALTA — cierre de la sesion de QA

### 10.1 Cuadre Matematico

- [ ] **10 tickets aleatorios:**
  - [P] Seleccionar 10 del historial (mezcla metodos, con/sin descuento).
  - [P] Con calculadora, sumar subtotales, impuestos, descuentos.
  - [V] Coinciden centavo a centavo.
- [ ] **5 productos — cuadre de stock:**
  - [P] Stock Inicial - Unidades Vendidas (historial) = Stock Actual.
  - [V] Exacto para los 5.
- [ ] **Ventas por metodo de pago:**
  - [P] Sumar efectivo + tarjeta + transferencia.
  - [V] = Total general del reporte.
- [ ] **Movimientos de caja:**
  - [P] Sumar entradas (F7) - retiros (F8).
  - [V] Neto coincide con corte de caja.

### 10.2 Folios

- [ ] **Secuencialidad:**
  - [P] Ordenar folios en historial.
  - [V] Consecutivos, sin huecos, sin duplicados.

### 10.3 Claves SAT en Ventas

- [ ] **5 ventas con claves especificas:**
  - [P] Revisar sale_items de ventas con productos que tenian clave SAT asignada.
  - [V] Cada sale_item tiene la clave SAT correcta del producto al momento de la venta.

### 10.4 Descuentos en Historial

- [ ] **5 ventas con descuento:**
  - [P] Recalcular: precio * qty * (1-desc_ind%) para individuales, subtotal * (1-desc_global%) para globales.
  - [V] Todos coinciden centavo a centavo.

---

## Resumen de Cobertura V9

| Fase | Tests | Enfoque | Prioridad |
|------|-------|---------|-----------|
| 0 | 8 | Regresion bugs V8 | BLOCKER |
| 1 | 34 | Flujo critico (ventas, descuentos, pendientes, mayoreo) | BLOCKER |
| 2 | 17 | Integridad de datos y seguridad | ALTA |
| 3 | 28 | CRUD productos, clientes, empleados, SAT, gastos | ALTA |
| 4 | 16 | Navegacion, UX, configuracion | MEDIA |
| 5 | 16 | Concurrencia y multi-terminal | ALTA |
| 6 | 7 | Resiliencia de red | ALTA |
| 7 | 7 | Estres y volumen | MEDIA |
| 8 | 10 | Escenarios caoticos | MEDIA |
| 9 | 11 | Fiscal, IVA, monitoreo remoto | MEDIA |
| 10 | 7 | Auditoria final | ALTA |
| **Total** | **~161** | | |

### Cambios respecto a V8 (247 tests)

1. **-86 tests eliminados:** Removidos duplicados (nombres largos x2, descuentos repetitivos, escenarios numericos redundantes).
2. **+Fase 0:** Regresion explicita de los 6 bugs encontrados en V8.
3. **Prioridad explicita:** Cada fase tiene nivel BLOCKER/ALTA/MEDIA para que el tester sepa que ejecutar primero.
4. **Tiempos estimados:** Cada fase tiene duracion aproximada.
5. **Criterios unificados:** Formato `[P]` (paso) y `[V]` (verificacion) consistente.
6. **Multi-terminal como seccion unificada:** No como fase separada redundante.
7. **Fases 4+10+13 de V8 consolidadas** en Fase 7 (Estres) y Fase 8 (Caos).
