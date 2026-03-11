# POSVENDELO V2 - Plan de Testing V6 (Chaos Engineering, Edge Cases y E2E Completo)

Tras la validación de resiliencia operativa en la V5 (Disaster Recovery, Concurrencia de Inventario, Auditoría Forense), la V6 combina **Chaos Engineering** con **E2E sistemático** de todas las pestañas y subapartados, y **edge cases** por módulo.

> [!IMPORTANT]
> **No se requiere ejecución aún.** Diseño conceptual para cuando los bugs de V1–V5 estén corregidos y el sistema esté listo para una nueva ronda de validación.

---

## Índice

1. [FASE 0: Regresión global](#fase-0-regresión-global-baseline--hotfixes)
2. [FASE E2E: Flujos E2E por pestaña y subapartado](#fase-e2e-flujos-e2e-por-pestaña-y-subapartado)
3. [FASE EC: Edge cases por módulo](#fase-ec-edge-cases-por-módulo)
4. [FASE 1–9: Chaos Engineering (original ampliado)](#fase-1-a-9-chaos-engineering)

---

## FASE 0: Regresión global (Baseline & Hotfixes)

Antes de someter al sistema a nuevas presiones, auditar que las reparaciones previas sigan vigentes.

| ID   | Prueba | Objetivo |
|------|--------|----------|
| 0.1  | **Sincronización de catálogo** | Re-test del vector “Edición fantasma de precios” (V5 Fase 2): frontend no debe enviar precios cacheados obsoletos; backend debe validar independientemente. |
| 0.2  | **Colisiones y deadlocks** | Re-test doble clic rápido en apertura de turnos (V4): no debe crearse más de un turno simultáneo. |
| 0.3  | **Sanitización del escáner** | Re-test inyección de barra estabilizadora (V5 Fase 6): caracteres `\t` en buscador SKU no deben saltar el DOM a acciones destructivas (ej. “Quitar producto”). |

---

## FASE E2E: Flujos E2E por pestaña y subapartado

Cada flujo debe ejecutarse con usuario autenticado, turno abierto cuando aplique, y verificar que la UI responde y que el estado/backend queda consistente.

### E2E-1: Login y arranque

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-1.1  | Login exitoso | Ingresar usuario/contraseña válidos → enviar | Redirección a `/terminal` o modal de turno; token y usuario en `localStorage`. |
| E2E-1.2  | Login fallido | Usuario/contraseña inválidos | Mensaje de error claro; no redirección; no token. |
| E2E-1.3  | Sin backend | Apagar backend, cargar login | Mensaje “No se encontró el servidor” (auto-descubrimiento). |
| E2E-1.4  | Ruta protegida sin token | Ir a `#/productos` sin token | Redirección a `#/login`. |
| E2E-1.5  | Cierre de sesión | Clic en “Cerrar sesión” en navbar | Token eliminado; redirección a login; limpieza de estado local relevante. |

### E2E-2: Terminal (Ventas) — F1

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-2.1  | Venta completa efectivo | Buscar producto (F10) → agregar al carrito → Cobrar (F11) → efectivo → monto recibido ≥ total → Confirmar | Venta creada en backend; ticket en historial; carrito vacío; cambio mostrado. |
| E2E-2.2  | Venta tarjeta/transferencia | Agregar ítems → Cobrar → método tarjeta o transferencia → Confirmar | Venta con `payment_method` correcto; sin validación de “monto recibido” en UI. |
| E2E-2.3  | Múltiples ítems y cantidades | Agregar mismo producto varias veces; cambiar cantidad; agregar otro producto | Subtotales y total correctos; descuentos por línea si aplican. |
| E2E-2.4  | Descuento por línea y global | Aplicar % descuento en línea y descuento global | Cálculo coherente con backend; total final correcto. |
| E2E-2.5  | Quitar ítem del carrito | Agregar ítems → seleccionar uno → quitar | Ítem desaparece; total actualizado. |
| E2E-2.6  | Verificador de precios (F9) | Abrir F9 → buscar SKU/nombre → cerrar | Resultados visibles; cierre sin afectar carrito. |
| E2E-2.7  | Entrada/Retiro de efectivo (F7/F8) | F7 monto + motivo → Registrar; F8 monto + motivo → Registrar | Movimientos en turno; mensaje éxito; cajón abierto si está configurado. |
| E2E-2.8  | Ticket pendiente: guardar y recuperar | Agregar ítems → “Guardar ticket” / cambiar de pestaña con ticket activo → volver a Terminal | Ticket restaurado; ítems y total conservados. |
| E2E-2.9  | Navegación por teclado F1–F9 | Desde Terminal, pulsar F2…F9 y volver F1 | Cambio de ruta correcto; modales F7/F8/F9 abren/cierran bien. |

### E2E-3: Clientes — F2

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-3.1  | Carga y listado | Entrar a Clientes | Lista cargada (pull); paginación si > 50. |
| E2E-3.2  | Búsqueda | Escribir en filtro por nombre/teléfono/email | Lista filtrada; página reseteada a 0. |
| E2E-3.3  | Alta cliente | Botón nuevo → nombre obligatorio, teléfono, email → Guardar | Cliente en lista; sync con backend. |
| E2E-3.4  | Edición cliente | Seleccionar → editar nombre/teléfono/email → Guardar | Cambios persistidos; mensaje éxito. |
| E2E-3.5  | Baja lógica | Seleccionar → Eliminar → confirmar | Cliente ya no disponible (o marcado inactivo según modelo). |
| E2E-3.6  | Ver crédito / ventas por cliente | Seleccionar cliente → “Crédito” o “Ventas” | Datos cargados; sin romper pestaña. |

### E2E-4: Productos — F3

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-4.1  | Carga y listado | Entrar a Productos | Lista y categorías cargadas; paginación. |
| E2E-4.2  | Búsqueda y filtro por categoría | Texto en buscador; elegir categoría | Lista filtrada; página 0. |
| E2E-4.3  | Alta producto | Nuevo → SKU, nombre, precio, stock, categoría → Guardar | Producto en lista; sync. |
| E2E-4.4  | Edición producto | Seleccionar → cambiar precio/stock/nombre → Guardar | Persistido; coherencia en Terminal/Inventario. |
| E2E-4.5  | Baja lógica | Seleccionar → Eliminar → confirmar | Producto no disponible para venta (según reglas). |
| E2E-4.6  | Escáner SKU | Simular entrada en campo escáner (código de barras) → Enter | Producto encontrado y seleccionado o agregado según UX. |
| E2E-4.7  | Bajo stock | Botón “Bajo stock” | Lista de productos con stock bajo; sin error. |

### E2E-5: Inventario — F4

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-5.1  | Carga y listado | Entrar a Inventario | Productos con stock; paginación 50. |
| E2E-5.2  | Búsqueda | Filtro por SKU/nombre | Filtrado y página 0. |
| E2E-5.3  | Movimiento entrada | Seleccionar producto (o SKU) → cantidad → tipo “entrada” → Aplicar | Stock incrementado en backend; mensaje éxito. |
| E2E-5.4  | Movimiento salida | Tipo “salida” → cantidad ≤ stock → Aplicar | Stock decrementado. |
| E2E-5.5  | Movimiento merma | Tipo “merma” → cantidad → Aplicar | Stock decrementado; posible registro en mermas. |
| E2E-5.6  | Alertas de stock | Botón “Alertas” | Lista de alertas; sin crash. |
| E2E-5.7  | Historial de movimientos | Botón “Movimientos” / filtro por tipo IN/OUT | Lista de movimientos; paginación si aplica. |

### E2E-6: Turnos — F5

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-6.1  | Apertura de turno | Efectivo inicial + operador → Abrir turno | Turno creado en backend; `CURRENT_SHIFT_KEY` en localStorage; duración visible. |
| E2E-6.2  | Cierre de turno | Efectivo final + notas → Cerrar turno → confirmar | Turno cerrado en backend; historial actualizado; sin turno activo. |
| E2E-6.3  | Movimiento de caja (entrada/salida/gasto) | Dentro de turno: tipo, monto, motivo, PIN si aplica → Registrar | Movimiento registrado; resumen actualizado. |
| E2E-6.4  | Conciliación | Ver resumen backend vs local; “Conciliar” si hay opción | Diferencias mostradas; estado reconciliado si aplica. |
| E2E-6.5  | Historial de turnos | Lista de turnos cerrados; seleccionar uno | Detalle o resumen visible; export CSV si existe. |
| E2E-6.6  | Bloqueo sin turno | Con turno cerrado, intentar venta en Terminal | Modal o mensaje “Abre un turno” (ShiftStartupModal). |

### E2E-7: Reportes — F6

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-7.1  | Sub-tab Local | Rango de fechas → Cargar/Consultar | Ventas cargadas; totales y por método de pago; productos más vendidos. |
| E2E-7.2  | Sub-tab Daily | Período diario → Cargar | Datos diarios; sin error. |
| E2E-7.3  | Sub-tab Ranking | Cargar ranking de productos | Lista ordenada por cantidad o ingresos. |
| E2E-7.4  | Sub-tab Heatmap | Cargar heatmap por hora | Datos por hora; visualización si existe. |
| E2E-7.5  | Export CSV | Tras cargar reporte local → Exportar CSV | Descarga de archivo; contenido coherente con datos mostrados. |

### E2E-8: Historial — (acceso por navbar)

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-8.1  | Búsqueda por fechas y folio | Rango fecha from/to; folio opcional → Buscar | Lista de ventas; paginación si aplica. |
| E2E-8.2  | Filtros (método de pago, monto min/max) | Aplicar filtros sobre resultados | Lista filtrada correctamente. |
| E2E-8.3  | Detalle de venta | Clic en una venta | Detalle (ítems, total, método, cliente); eventos si existen. |
| E2E-8.4  | Cancelación de venta (rol permitido) | Con rol manager+ → Cancelar venta → confirmar | Venta cancelada en backend; actualización de lista/detalle. |

### E2E-9: Configuraciones (Ajustes)

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-9.1  | Ver y editar conexión | Base URL, Token, Terminal ID → Guardar | `saveRuntimeConfig`; mensaje éxito. |
| E2E-9.2  | Validación URL inválida | URL mal formada → Guardar | Mensaje “Base URL inválida”. |
| E2E-9.3  | Perfiles: guardar actual | Nombre perfil → Guardar perfil | Perfil en lista (máx 20). |
| E2E-9.4  | Perfiles: cargar y eliminar | Seleccionar perfil → Cargar; seleccionar → Eliminar → confirmar | Campos actualizados; perfil eliminado. |
| E2E-9.5  | Estado de sincronización / Info sistema | Botones “Sync status” y “System info” | Respuesta mostrada sin romper la pestaña. |

### E2E-10: Estadísticas (Stats)

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-10.1 | Panel Quick | Cargar Quick | `ventas_hoy`, `total_hoy`, `mermas_pendientes` (o equivalente). |
| E2E-10.2 | Paneles Resico / Wealth / AI / Executive | Cargar cada panel (si rol lo permite) | Datos o mensaje de restricción; sin crash. |

### E2E-11: Mermas

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-11.1 | Listado de mermas pendientes | Entrar a Mermas | Lista desde backend; fotos si aplican. |
| E2E-11.2 | Aprobar merma | Aprobar → confirmar | Estado actualizado; sale de pendientes. |
| E2E-11.3 | Rechazar merma | Rechazar → confirmar | Estado actualizado. |
| E2E-11.4 | Notas por merma | Añadir nota a una merma (si hay campo) | Nota guardada o mostrada en detalle. |

### E2E-12: Gastos

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-12.1 | Resumen mes/año | Entrar a Gastos | Totales del mes y del año cargados. |
| E2E-12.2 | Registrar gasto | Monto + descripción (obligatoria) + motivo opcional → Enviar (con turno abierto) | Gasto registrado; resumen actualizado. |
| E2E-12.3 | Sin turno abierto | Intentar registrar gasto sin turno | Mensaje “Abre un turno en Turnos (F5)”. |

### E2E-13: Empleados

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-13.1 | Listado (rol con permiso) | Entrar a Empleados | Lista de empleados; paginación. |
| E2E-13.2 | Búsqueda | Filtro por nombre/código/teléfono/email | Lista filtrada. |
| E2E-13.3 | Alta empleado | Nuevo → código, nombre, puesto, salario, comisión, contacto → Guardar | Empleado creado en backend. |
| E2E-13.4 | Edición y baja | Editar campos → Guardar; Eliminar → confirmar | Cambios persistidos; eliminación según reglas. |

### E2E-14: Remoto

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-14.1 | Estado del turno | Entrar a Remoto | Estado remoto del turno cargado. |
| E2E-14.2 | Ventas en vivo | Ver sección “Ventas en vivo” | Lista actualizada (polling); sin error. |
| E2E-14.3 | Notificaciones | Ver notificaciones pendientes | Lista; marcar como leídas si aplica. |
| E2E-14.4 | Cambio de precio (admin) | SKU, nuevo precio, motivo → Enviar | Precio actualizado en backend. |
| E2E-14.5 | Abrir cajón remoto | Botón abrir cajón | Llamada exitosa al backend. |

### E2E-15: Fiscal

Sub-tabs: Facturación, Inventario (shadow), Logística, Federación, Auditoría, Wallet, Crypto, Seguridad.

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-15.1 | Facturación: generar CFDI | ID venta, RFC, nombre, régimen, uso, forma pago, CP → Generar | CFDI generado o mensaje de error claro. |
| E2E-15.2 | Facturación: CFDI global | Período (daily) + fecha → Generar global | Respuesta sin crash. |
| E2E-15.3 | Devolución | ID venta, ítems, motivo, responsable → Procesar devolución | Devolución registrada; resumen si existe. |
| E2E-15.4 | Shadow inventory: reconciliar | Product ID, stock fiscal → Reconciliar | Respuesta coherente. |
| E2E-15.5 | Logística: transferencia fantasma | Origen, destino, ítems, usuario, notas → Crear; recibir con código | Transferencia creada/recibida. |
| E2E-15.6 | Auditoría: análisis proveedor | Product ID, cantidades, precios A/B → Ejecutar | Resultado mostrado. |
| E2E-15.7 | Wallet: puntos y canje | Hash, monto venta / canje | Puntos añadidos/canjeados. |
| E2E-15.8 | Crypto / Seguridad / Federación | Navegar sub-tabs; ejecutar una acción por sub-tab si aplica | Sin crash; respuestas o mensajes de permiso. |

### E2E-16: Hardware

Secciones: Impresora, Negocio, Escáner, Cajón.

| ID       | Flujo | Pasos | Criterios de éxito |
|----------|--------|--------|---------------------|
| E2E-16.1 | Carga de configuración | Entrar a Hardware | Config actual (printer, business, scanner, drawer) cargada. |
| E2E-16.2 | Descubrir impresoras | Botón “Descubrir” | Lista de impresoras CUPS/local; mensaje con cantidad. |
| E2E-16.3 | Guardar impresora | Seleccionar impresora / nombre → Guardar | Config guardada en backend; caché local actualizada. |
| E2E-16.4 | Test impresión | “Imprimir prueba” | Ticket de prueba enviado; sin bloquear UI. |
| E2E-16.5 | Test cajón | “Abrir cajón prueba” | Cajón abierto; mensaje éxito. |
| E2E-16.6 | Secciones Negocio / Escáner / Cajón | Cambiar sección; editar campos y guardar | Guardado por sección; mensaje claro. |

### E2E-17: Navegación global y atajos

| ID       | Flujo | Criterios de éxito |
|----------|--------|---------------------|
| E2E-17.1 | Todas las rutas desde navbar | Cada ítem del navbar lleva a la ruta correcta; ruta activa resaltada. |
| E2E-17.2 | Ruta inexistente | `#/ruta-inexistente` → redirección a `#/` (luego a terminal o login según auth). |
| E2E-17.3 | F1–F11 con y sin foco en input | Con foco en input/select/textarea no se cambia de pestaña; sin foco sí. |
| E2E-17.4 | Error boundary por pestaña | Forzar error en una pestaña (ej. mock fallido): solo esa pestaña muestra error; “Reintentar” / “Ir a Terminal” funcionan. |

---

## FASE EC: Edge cases por módulo

Casos límite y entradas hostiles por pantalla, sin incluir aún el chaos de Fases 1–9.

### EC-Login

- Usuario vacío / contraseña vacía / ambos.
- Usuario o contraseña con espacios; solo espacios.
- Usuario o contraseña con caracteres Unicode, RTL, Zalgo.
- Respuesta 401 con `detail` string vs array de errores.
- Respuesta 200 sin `token` en body.
- Timeout de login (8 s): abort y mensaje.
- Múltiples clics en “Iniciar sesión”: una sola petición; botón deshabilitado mientras carga.

### EC-Terminal

- Carrito vacío → Cobrar: debe pedir ítems o bloquear.
- Monto recibido menor que total en efectivo: mensaje; no completar venta hasta cubrir.
- Cantidad 0 o negativa en ítem; cantidad con decimales según reglas.
- SKU inexistente en búsqueda F10: mensaje “no encontrado” o similar.
- Producto sin stock (si se valida): aviso o bloqueo.
- Descuento > 100% o negativo: clamp o validación.
- Doble clic en “Cobrar” o “Confirmar”: una sola venta; botón deshabilitado.
- Pérdida de conexión durante `createSale`: mensaje; retry o ticket en cola.
- LocalStorage de tickets corrupto (JSON inválido): app no crashea; se puede recuperar o empezar de cero.

### EC-Clientes / EC-Productos

- Nombre vacío en alta: validación y mensaje.
- Teléfono/email con formato inválido (Clientes): validación si existe.
- SKU duplicado en alta producto: mensaje de conflicto.
- Precio o stock negativo: validación o clamp.
- Búsqueda con solo espacios; con `%`, `_`, `\`.
- Paginación: última página vacía; ir a página > totalPages (clamp).
- Eliminar ítem seleccionado: selección se limpia; lista actualizada.

### EC-Inventario

- Movimiento salida con cantidad > stock: backend rechaza o avisa.
- Cantidad 0 o negativa en movimiento: validación.
- Producto no encontrado por SKU: mensaje claro.
- Múltiples movimientos rápidos al mismo producto: no duplicar ni invertir signos.

### EC-Turnos

- Abrir turno sin efectivo inicial (si es obligatorio): validación.
- Cerrar turno con efectivo final no numérico: validación.
- Cerrar turno ya cerrado: mensaje.
- Dos pestañas: una cierra el turno; la otra debe refrescar (storage/focus) y no permitir venta.

### EC-Reportes / EC-Historial

- Rango de fechas: “desde” > “hasta”: validación o intercambio.
- Fechas futuras: según reglas de negocio.
- Sin resultados: mensaje “Sin ventas” o similar; no error genérico.
- Export CSV con caracteres especiales (=, +, comillas): celdas escapadas (sin inyección fórmula).

### EC-Configuraciones

- Terminal ID no numérico o < 1: validación y mensaje.
- Perfiles: nombre vacío al guardar; máximo 20 perfiles (sustituir más antiguo o avisar).
- LocalStorage lleno al guardar perfil: mensaje “QuotaExceeded” o similar.

### EC-Mermas / EC-Gastos

- Aprobar/Rechazar la misma merma dos veces: idempotencia o mensaje.
- Gasto con monto 0 o negativo: validación.
- Gasto sin descripción: validación.

### EC-Empleados

- Código duplicado en alta: mensaje de conflicto.
- Eliminar empleado con ventas o turnos asociados: según reglas (bloqueo o cascada).

### EC-Fiscal

- CFDI con RFC inválido; con nombre vacío: validación backend.
- Devolución con más cantidad que la venta original: rechazo.
- Hash de wallet inexistente: mensaje claro.

### EC-Hardware

- Guardar sin impresora seleccionada (si es obligatorio): validación.
- Test impresión con impresora desconectada: error manejado; UI no bloqueada.
- Nombre legal / datos de negocio con caracteres especiales o muy largos: validación o truncado.

### EC-Navbar y modales globales

- F7/F8 sin turno abierto: mensaje “Abre un turno en Turnos”.
- Cerrar modal con Escape; cerrar con clic fuera: modal se cierra.
- Dos modales no pueden abrirse a la vez (F7 y F8 en el mismo frame): comportamiento definido (uno prevalece o se encolan).

---

## FASE 1 a 9: Chaos Engineering

*(Se mantienen las fases originales; se añaden referencias cruzadas con E2E donde aplique.)*

### FASE 1: Chronobiología y time travel

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 1.1 | **Desfase de zona horaria** | Cambiar fecha/hora del SO (ej. diciembre 2023); login, vender, cobrar. Backend debe detectar timestamps anómalos o asignar día correctamente. |
| 1.2 | **Turnos vampiro (medianoche / DST)** | Abrir turno 23:55, vender 23:59, cambiar hora a 00:05 del día siguiente (o cruzar DST), vender de nuevo, cerrar. Corte de caja debe unificar ingresos sin crashear. |

### FASE 2: Limitaciones físicas y throttling

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 2.1 | **Red 2G simulada** | Throttling 20 kbps + 15 s latencia (DevTools). 5 checkouts seguidos: sin colapso de React, sin duplicar peticiones; botón deshabilitado o spinner. |
| 2.2 | **Payload fragmentado** | Corromper 4 de 100 bytes del JSON de la venta. FastAPI debe rechazar deserialización; no insertar producto vacío. |

### FASE 3: Corrupción de almacenamiento

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 3.1 | **NaN/Undefined en estado** | En LocalStorage reemplazar valores (descuentos, tax, ID) por `NaN` o `undefined`. App debe sobrevivir rehidratación o mostrar Error Boundary recuperable. |
| 3.2 | **Secuestro de impresión** | Interceptar llamada a impresora e inyectar bucle infinito. UI principal no debe bloquearse; worker aísla fallo. |

### FASE 4: Volumetría y memoria

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 4.1 | **Ticket con 15 000 líneas** | Un ticket con 15 000 líneas. React debe renderizar (o virtualizar) sin derretir el navegador; backend debe aceptar o rechazar en tiempo límite. |
| 4.2 | **Historial 200 000 ventas** | Seed de 200k ventas; abrir Historial. Request con `limit`/`offset`; sin cargar todo en RAM. |

### FASE 5: Estrés dual (split brain)

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 5.1 | **Retiros y cobros cruzados** | PC1 vende; PC2 retira el total disponible en el mismo instante. Validación atómica debe evitar balance negativo. |
| 5.2 | **Deslogueo fantasma** | Cerrar turno en PC1; en PC2 intentar facturar ticket ya armado. Error graceful; no limbo de sesión. |

### FASE 6: Hardware hot-swap y periféricos

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 6.1 | **Impresora desconectada al imprimir** | Tras `200 OK` de venta, desconectar driver de impresión. Worker no crashea el thread principal; reintento o spooler al reconectar. |

### FASE 7: Trampas modales y event flooding

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 7.1 | **Macro de teclas superpuestas** | F10, F11, Escape, Enter en el mismo frame. Evitar modales superpuestos; al cerrar “Cobro”, fondo y foco correctos. |

### FASE 8: Corrupción Unicode (Zalgo, RTL)

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 8.1 | **Zalgo y RTL en nombre** | Cliente o producto con nombre Zalgo + RTL override. CSS y layout no se rompen; backend valida UTF-8 y longitud. |

### FASE 9: Límites numéricos (64 bits / BigInt)

| ID  | Prueba | Objetivo |
|-----|--------|----------|
| 9.1 | **Millonarios pícaros** | Cantidad 9 999 999 999 y cambio 999 999 999 999. Backend debe rechazar “Out of Range”; no notación científica en flujo de caja. |

---

## Resumen de cobertura

| Área | E2E | Edge cases | Chaos |
|------|-----|------------|-------|
| Login | E2E-1 | EC-Login | - |
| Terminal | E2E-2 | EC-Terminal | 2.1, 4.1, 7.1 |
| Clientes | E2E-3 | EC-Clientes | 8.1 |
| Productos | E2E-4 | EC-Productos | 0.3, 8.1 |
| Inventario | E2E-5 | EC-Inventario | 0.1 |
| Turnos | E2E-6 | EC-Turnos | 0.2, 1.1, 1.2, 5.1, 5.2 |
| Reportes | E2E-7 | EC-Reportes | 4.2 |
| Historial | E2E-8 | EC-Historial | 4.2 |
| Configuraciones | E2E-9 | EC-Configuraciones | 3.1 |
| Estadísticas | E2E-10 | - | - |
| Mermas | E2E-11 | EC-Mermas | - |
| Gastos | E2E-12 | EC-Gastos | - |
| Empleados | E2E-13 | EC-Empleados | - |
| Remoto | E2E-14 | - | - |
| Fiscal | E2E-15 | EC-Fiscal | - |
| Hardware | E2E-16 | EC-Hardware | 3.2, 6.1 |
| Navegación/Global | E2E-17 | EC-Navbar | 7.1 |

Este plan queda listo para priorizar (por ejemplo: primero FASE 0 + E2E críticos + EC por módulo, luego Chaos por fases) e implementar pruebas automáticas (Playwright/Cypress para E2E, tests unitarios/integración para edge cases y chaos controlado).
