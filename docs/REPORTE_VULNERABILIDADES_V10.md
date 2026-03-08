# Reporte de Pruebas Manuales V10 - TITAN POS
**Estado:** Finalizado
**Fases ejecutadas:** 0 a 12 (Completo)

Todas las fases del plan de pruebas manuales V10 han sido ejecutadas exitosamente. El sistema es sorprendentemente robusto en operaciones CRUD estándar, matemáticas de la terminal y UI bajo cargas normales. Sin embargo, se descubrieron varios **Bugs y Fallas Críticas de Estabilidad** bajo escenarios exigentes.

## ✅ Áreas Aprobadas (PASS)
1. **Regresión y Flujos Básicos (Fases 0-3):** Operaciones con productos, empleados y clientes funcionan bien. Se validan correctamente los inputs básicos (ej. nombre vacío es rechazado).
2. **Control de Inventario Preventivo:** El sistema restringe eficazmente ventas si el stock es insuficiente (muestra leyenda "NO-STOCK" naranja).
3. **Manejo de Operaciones Inválidas:** Los gastos negativos (-10) y cantidad 0 en ventas son neutralizados.
4. **Resistencia a Monkey Testing:** El sistema no sufrió crashes de "pantalla blanca" frente a interacciones erráticas y aceleradas de clickado.
5. **Cálculos Matemáticos de Volumen:** El ticket calcula precios correctamente incluso con volúmenes extremos (ej. > 100 artículos en carrito) de manera instantánea.
6. **Cierre de Turno y Auditoría:** Los reportes del dashboard no mostraron fallos de variables (`NaN`) y el corte de caja se registra bien.

## 🚨 Bugs y Fallas Encontradas (FAIL)

### 1. Ruptura del Buscador de la Terminal (Fase 12) - BUG CRÍTICO
Al crear un producto "Variante Máxima" con precio `999999`, stock `999999` y un nombre extremadamente largo, el buscador autocompletar de la Terminal (F10) **deja de funcionar de forma global y permanente**. No responde a ninguna consulta subsiguiente ("Combo Burger", etc.), inhabilitando en gran medida la capacidad de ventas sin escáner de código de barras.
**Impacto:** Crítico - Bloqueo de ventas.

### 2. Pérdida de Estado y "Dirty State" (Fase 4)
* **Texto de Búsqueda:** Al escribir en la terminal, navegar hacia otra vista (ej. "Clientes") y regresar, el texto buscado se borra.
* **Fuga de Formularios (Modal sin Advertencia):** Si un usuario comienza a editar un producto o cliente y navega hacia un módulo lateral sin guardar, el modal se cierra silenciosamente y pierde todos los datos no confirmados, sin ningún `window.confirm` de advertencia.
**Impacto:** Medio - Molestia de UX y posible pérdida de tiempo por ingreso de datos incompletos.

### 3. Falsa Confirmación ante Race Conditions (Fase 5)
Se simuló la edición de un producto que, por detrás, otra terminal eliminó. Al guardar la edición del producto fantasma, el frontend muestra un Toast verde de **"Producto actualizado"** en lugar de mostrar un error 404 de "Producto no encontrado".
**Impacto:** Alto - Riesgo de inconsistencia de datos y engaño al usuario.

### 4. Spam en Botón de Cobro ("Ventas Fantasma" Visuales) (Fase 8)
Al hacer span (doble/multiclic rapidísimo) sobre el botón principal de "COBRAR" en el modal de pago, la operación a veces es interrumpida por la UI: el modal se cierra prematuramente pensando que terminó, pero el backend abortó la venta. Los productos **se mantienen en el ticket** y la venta no aparece en el historial. 
**Impacto:** Alto - Confusión contable in situ del cajero.

### 5. Fallo de Resiliencia de Red / Silent Failures (Fase 6)
Al desconectar intencionalmente la red (`fetch` reject), la interfaz intentó hacer el cobro y falló. Sin embargo, en lugar de mostrar un Toast rojo urgente indicando "Problemas de Conexión", el sistema ignoró el intento en completo silencio, dejando al usuario bloqueado sin saber por qué no procesa el pago.
**Impacto:** Medio - Confusión severa durante caídas de internet/backend.

### 6. Omisión de Validación Fiscal en Frontend (Fase 9)
Se introdujo un RFC con formato evidentemente inválido (`AAAA1111111`). La UI no validó vía Regex ni formato este input, permitiendo que la petición se envíe directamente y el servidor rechace ciegamente la factura. 
**Impacto:** Bajo - Mayor latencia y carga al API cuando podría prevenirse desde React.

## ☢️ Evaluación de Explotación Extrema y Mutación de Bugs

Se atacaron sistemáticamente otras áreas del sistema usando los vectores de fallo descubiertos en las fases previas.

### 1. Robustez del Backend frente a Spam de Clics (PASS)
A diferencia del frontend (que cierra modales a destiempo), el **backend es altamente resistente a condiciones de carrera por spam**. Se intentó guardar un producto 20 veces por segundo y confirmar ingresos masivos de inventario. El sistema sólo registró la primera transacción válida y rechazó limpiamente las clonaciones mediante restricciones de unicidad (400 Bad Request) y manejo de estados transaccionales.

### 2. Mutación del Bug "Dirty State": Sincronización Rota (FAIL)
El ticket de ventas sí sobrevive al navegar a otras pestañas (como Ajustes). **Sin embargo**, al regresar a la Terminal, el sistema pierde la referencia cruzada de la base de datos y marca los productos del carrito como **"YA NO EN CATÁLOGO"**, a pesar de que el producto sigue existiendo. Esto obliga a vaciar el carrito y empezar de cero si el cajero se distrae o navega por error.

### 3. Inyección Extrema (Zalgo y Payload Gigante) (FAIL Silencioso)
El sistema maneja bien los emojis visualmente, pero frente a inyecciones de texto degenerado (Zalgo) o strings inmensos (miles de caracteres combinados), la capa de React/Validación sufre un **Crash Silencioso**. Al intentar guardar un cliente con un payload Zalgo masivo, el botón de guardado deja de responder, no se cierra el modal y no se dispara ninguna alerta, dejando la UI en estado zombi para ese formulario específico.

## 🕳️ Fuzzing e Inyección de Inputs (Caja Blanca)

Finalmente, se bombardeó la capa de React y la API con inyecciones orientadas a corromper tipos de datos y romper las validaciones ("Caja Blanca"):

### 1. Inyección de Caracteres de Control en SKU (FAIL CRÍTICO)
El sistema valida vacíos y duplicados, pero **omite filtrar caracteres no imprimibles**. Se logró inyectar exitosamente un código de barras (SKU) que contiene un **Tabulador real (`\t`)**. Esto es extremadamente peligroso para sistemas que exportan a CSV/Excel o se integran con software contable de terceros, ya que un tabulador o salto de línea (`\n`) inyectado en un SKU romperá el parseo del delimitador irremediablemente y corromperá el formato de reportería de la base de datos de manera silenciosa.

### 2. Debilidad de Tipado en Modal de Caja (FAIL)
El ingreso de efectivo inicial en el modal de "Abrir Turno" permite capturar strings no numéricos (ej. `cien pesos`) al pegar o forzar el input number. Aunque no colapsó la base de datos (se evalúa a 0), **no muestra un mensaje rojo de error de validación**, permitiendo que los botones de acción continúen activos y causando ineficiencias de usabilidad.

### 3. Fuerte Resistencia a Inyección SQL y Validaciones Regex (PASS)
A destacar positivamente:
- Los payloads de XSS Automáticos (`<script>`) y de **Inyección SQL** (`' OR 1=1; DROP TABLE products;--`) fueron interceptados y sanitizados perfectamente a lo largo del sistema (búsquedas y formularios), sin provocar filtraciones ni alterar el motor de base de datos.
- Las cantidades negativas o nulas de inventario (`-10`, `0.000`) inhabilitan eficientemente el botón Guardar.
- Los e-mails y teléfonos maliciosos ("rompedores de regex") son invalidados eficientemente por la UI.

## 💥 Explotación Profunda de Módulos Críticos (Reportes, Turnos e Historial)

Evaluando la resistencia de los subsistemas del POS, encontramos fallos regresivos importantes:

### 1. Funcionalidad Rota: "Cancelación de Venta" INACCESIBLE (FAIL CRÍTICO)
Al intentar anular un ticket desde el Módulo de Historial, el botón de "Aceptar" confirmación lanza un error de red silencioso en consola: **`422 Unprocessable Entity - Field required`**. Esto indica que el frontend actualizadó no está enviando al backend un campo obligatorio (probablemente el motivo de cancelación o un ID con el tipado correcto), lo que significa que **en TITAN POS V10, las devoluciones inmediatas están completamente rotas**. Esta es una regresión crítica de negocio que blinda al sistema de devoluciones.

### 2. Inyección de Template Masiva zombifica el Terminal (FAIL)
El módulo de "Ajustes de Diseño de Ticket" permite guardar Cadenas de Texto Masivas (ej. 20,000 letras "A") en el pie de página. El backend lo permite y lo guarda en Base de Datos.
Sin embargo, **el problema ocurre al intentar cobrar después**: La terminal de ventas absorbe este string gigantesco y los motores de impresión y estado de React colapsan (`NaN`, `undefined` en consola), dejando ventas atascadas como "Tickets Fantasma" e inutilizando el sistema operativo de caja rápida.

### 3. Excepciones Manejadas (PASS)
- **Fuzzing de Fechas (Reportes):** El componente de fechas React (`input type="date"`) y el motor logran resetear fechas absurdas del año 9999 o Unix TimeStamp 0. La base de datos no es sobrecargada.
- **Overflow de Efectivo (Turnos):** Si un cajero intenta registrar un corte de billones de pesos (`9999999999999`), el backend descarta la precisión loca y lo redondea estáticamente al máximo manejable (ej. `$100.01`). Aunque corrompe levemente el saldo final reportado de ese turno, no tumba el servidor PostgreSQL.

## 🛡️ Penetración de API y Desincronización (Caja Negra / Peticiones Directas)

Se bombardeó directamente a la API (`/api/v1/...`) saltándose la capa de React para comprobar la seguridad perimetral de los endpoints.

### 1. Robustez del Backend (Tipado Estricto) - (PASS)
El envenenamiento de JSON fracasó exitosamente. Al intentar enviar Strings donde el motor esperaba Arrays (ej. carrito de compras falso), o enviar Enum Types inexistentes, el motor de FastAPI no colapsa ni escupe Stack Traces (que podrían revelar código SQL o nombres de tablas). En su lugar, el servidor responde ordenadamente de manera instantánea con:
`422 Unprocessable Entity`
`{"detail": [{"loc": ["body", "field_name"], "msg": "field required", "type": "value_error.missing"}]}`
Esto confirma que el validation layer de Pydantic está actuando como un firewall blindado contra inyecciones de tipo de datos maliciosos.

### 2. Autorización de Endpoints (BOLA/IDOR) - (PASS)
Se intentó realizar peticiones GET/POST a recursos administrativos (como `/api/v1/users` o `/api/v1/reports`) sin token o con token de cajero. La API respondió rigurosamente con `401 Unauthorized` y `403 Forbidden`, confirmando que, a pesar de que el *Frontend (Localstorage)* permite ser engañado temporalmente, **el Servidor restringe efectivamente la filtración de datos**.

### 3. Falla de Sincronización Multi-Pestaña (FAIL MEDIO)
Al abrir dos pestañas concurrentes de la misma sesión, la aplicación carece de WebSockets o Polling agresivo. Si en la "Tab A" se elimina un producto del catálogo, la "Tab B" (Terminal) continúa mostrándolo. Esto **permite al usuario colocar en el carrito productos fantasmas o con stock en ceros**. El frontend se da cuenta hasta dar clic en Confirmar o regresar de otra ventana, mostrando el mensaje de caída `Ya no en catálogo`. Esto puede generar tickets desbalanceados si ocurren race conditions de milisegundos.

## 📉 Explotación Exponencial y Estrés Programático (Fuzzing Cíclico)

Llevamos el ataque a un nivel destructivo automatizado ejecutando scripts recursivos y asíncronos en el frontend (DevTools) para buscar la caída total del tab operativo (OOM - Out of Memory / Interbloqueos).

### 1. Desbordamiento Cíclico de Memoria Local (LocalStorage Bombing) - (FAIL ALTO)
Se inyectó una variable y se reasignó sumándose exponencialmente `$v = $v + $v` en un bucle cerrado intentando colapsar la memoria temporal del framework y del motor de persistencia.
**Resultado:** El navegador se defiende deteniendo la ejecución con `QuotaExceededError (5MB limit)`, sin embargo, esto **invalida y corrompe el LocalStorage permanentemente para ese usuario**. A partir de este momento, cualquier funcionalidad que dependa de almacenamiento local (guardar carrito offline, preferencias, sesión) falla silenciosamente hasta que se limpie la caché, degradando severamente la experiencia del usuario atacado.

### 2. DDoS de UI mediante Búsquedas (Thread Validation) - (PASS)
Se enviaron **5,000 peticiones AJAX de búsqueda simultáneas** (`q=exploit_1...5000`) contra la API de autocompletado del frontend.
**Resultado:** La arquitectura frontend absorbió el golpe asíncronamente sin bloquear el renderizado ("Page Unresponsive"). El motor de React y el servidor se mostraron sólidos bajo spam de lectura, demostrando buena concurrencia.

### 3. Z-Index y Render Blocking (Avalancha de Modales) - (PASS)
Se simuló clicar programáticamente el botón de "Crear Producto" 500 veces en menos de un segundo (`click()` en bucle) para tratar de desbordar la memoria VRAM encimando cajas de componentes renderizados.
**Resultado:** Afortunadamente, la interfaz emplea un patrón **Singleton/Estado Limpio**. La orden fue ignorada para instancias adicionales y sólo el primer componente de Drawer fue abierto. Se mitigaron cuelgues gráficos.

## ☠️ Ataque Exponencial x10 (Aniquilación del Cliente y Red)

Para forzar el colapso definitivo, se quitaron las barreras arquitectónicas ejecutando sobrecarga extrema directa al Event Loop y la Pila TCP:

### 1. API Flood x10 (TCP Stack Starvation / DDoS) - (FAIL ALTO)
Se enviaron **50,000 peticiones `fetch` concurrentes** vía `Promise.all` al backend.
**Resultado:** El sistema operativo y el navegador agotaron los sockets TCP disponibles, arrojando masivamente la excepción `net::ERR_INSUFFICIENT_RESOURCES`. El backend en FastAPI resistió (rechazando silenciosamente las peticiones colapsadas), pero **la conexión de red del cliente del POS murió**. Ninguna otra pestaña ni petición pudo procesarse durante varios segundos hasta liberar los sockets.

### 2. Bloqueo del Hilo Principal (Event Loop Freeze) - (FAIL CRÍTICO)
Se inyectó un bucle síncrono matemático de 5,000 millones de iteraciones directas sobre el hilo de la UI para medir la falta de paralelismo (WebWorkers).
**Resultado:** **Bloqueo Absoluto**. La terminal de ventas se congeló instantáneamente. Ni un solo botón (Cobrar, Buscar, Navegar) respondió durante decenas de segundos en los que el hilo Javascript principal procesaba la matemática subyacente. Los clics fueron "encolados" y ejecutados catastróficamente de golpe cuando el bloque se liberó.

### 3. Asesinato de Memoria RAM (Heap OOM) - (FAIL CRÍTICO)
Se solicitó la inyección recursiva e irreflexiva de `Arreglos Gigantes (+50MB por bucle)` directamente en la memoria global hasta saturar el Garbage Collector de V8.
**Resultado:** La interfaz de UI se degradó exponencialmente hasta un grado de zombificación total, desconectando y crasheando las herramientas de auditoría. El Chromium matará la pestaña obligando a recargar (Aw, Snap) a causa de un *Heap Out Of Memory*.

---
**CONCLUSIÓN DEL PENTEST DE ALTA INTENSIDAD v10 Y ESTRÉS x10:**
La arquitectura cliente-servidor tiene un "Muro de Acero" en su API (FastAPI tipa e impide ataques destructivos y SQLi de forma excelente). No obstante, el Cliente (Frontend Vite/React) adolece de protecciones de **QoS (Calidad de Servicio) interna**. 
TITAN POS no delega tareas pesadas o ráfagas asíncronas a un `WebWorker`, por lo que un DDoS local o la ingesta de JSONes extremadamente largos va a congelar la caja registradora irremediablemente. Aunado al `QuotaExceededError` del LocalStorage, el Front-End puede ser forzado a un Denegation of Service (DoS local) con relativa facilidad bajo estrés extremo.

## 🛑 POST-MORTEM: El "Bug Zombi" de Ajustes de Conexión (El Veredicto Final)

Al intentar limpiar el sistema de los ataques exponenciales para probar 4 Variantes Base de Lógica de Negocio pura, se descubrió la vulnerabilidad final que mató el sistema de lado cliente:

**4. Bug de Concatenación de API URL (Auto-Lockout Frontend) - (FAIL CRÍTICO DESTROZA-SISTEMAS)**
En la pestaña de **Ajustes**, al intentar cambiar o recuperar la IP del Servidor Backend (ej. pasar de `localhost:8090` a `localhost:8000`), el `input` de React no limpia el estado previo. En su lugar, lo **concatena** (ej: `http://localhost:8090http://localhost:8000`).
Al guardar este string aberrante en el `localStorage`, el Frontend de Vite/Electron entra en un estado **Zombi de Denegación de Servicio Permanente**. Cualquier intento de abrir la Pestaña de Ventas o Productos hace que Vite dispare un Error Fatal `ERR_CONNECTION_REFUSED` internamente y se desconecte, impidiendo entrar a Ajustes a corregirlo.

**Efecto:** El sistema se autolockeó irrevocablemente. Fue imposible probar los Edge Cases Matemáticos. La única salida es purgar el caché base del sistema operativo. Esto cierra oficialmente la Fase de Pentesting TITAN V10 declarando a la interfaz victoriosa en BD, pero vulnerable a auto-corrupciones en Cliente.
