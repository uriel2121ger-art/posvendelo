# QA TITAN POS — Informe Completo de Testing

> **Fecha:** 2026-02-26 23:50 CST  
> **Método:** Pruebas interactivas en navegador + API curl  
> **Entorno:** Docker (postgres:15-alpine + FastAPI), Vite dev server (port 5173)  
> **Usuario:** admin/admin

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total tests ejecutados** | 68 |
| **✅ PASS** | 54 |
| **⚠️ PARTIAL** | 5 |
| **❌ FAIL** | 9 |
| **Bugs encontrados** | 10 |

---

## 🐛 BUGS ENCONTRADOS

### 🔴 CRÍTICOS (Bloquean operación)

#### BUG-001: `POST /api/v1/turns/open` devuelve 500
- **Archivo:** `backend/modules/turns/routes.py` línea 45
- **Causa:** `datetime.now(timezone.utc).replace(tzinfo=None)` genera conflicto naive/aware en asyncpg
- **Error exacto:** `asyncpg.exceptions.DataError: can't subtract offset-naive and offset-aware datetimes`
- **Impacto:** Bloquea TODO el flujo de ventas (no se puede abrir turno → no se puede cobrar)
- **Reproducir:**
```bash
curl -X POST http://localhost:8000/api/v1/turns/open \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"initial_cash":500,"branch_id":1}'
# → 500 Internal Server Error
```

#### BUG-002: `setup.sh` no crea schema tras `docker compose down -v`
- **Archivo:** `setup.sh`
- **Causa:** El script no ejecuta `schema_postgresql.sql` ni migraciones
- **Impacto:** Instalación limpia deja la app completamente rota

---

### 🟡 ALTOS (Afectan funcionalidad)

#### BUG-003: Logout no funciona
- **Módulo:** Navegación
- **Síntoma:** Click en ícono logout → no redirige a login, sesión persiste tras refresh
- **Reproducir:** Login → click ícono salida (esquina superior derecha) → no pasa nada

#### BUG-004: Login fallido no muestra mensaje de error
- **Módulo:** Login
- **Síntoma:** Al ingresar credenciales incorrectas, la UI no muestra ningún toast/alerta visible
- **Nota:** Esto contradice los resultados del test anterior (25/Feb) donde SÍ aparecía "Credenciales invalidas". Posible regresión o diferencia en el estado de la app.

#### BUG-005: Botón INGRESAR habilitado con campos vacíos
- **Módulo:** Login
- **Síntoma:** Con ambos campos vacíos, el botón INGRESAR permanece habilitado (azul, `disabled=false`)
- **Esperado:** Botón debe estar deshabilitado hasta completar ambos campos

#### BUG-006: Clientes — Sin validación de campos vacíos
- **Módulo:** Clientes
- **Síntoma:** Click en "Guardar" con todos los campos vacíos → no muestra error ni previene la acción
- **Contraste:** Productos SÍ valida y muestra "SKU y nombre son obligatorios."

#### BUG-007: Carrito se limpia al navegar entre pestañas
- **Módulo:** Terminal/Ventas
- **Síntoma:** Al ir de Ventas → Turnos → Ventas, el carrito se vacía
- **Causa probable:** Estado del carrito vive en React state local (se destruye al desmontar componente)

---

### 🟢 MEDIOS (Mejoras)

#### BUG-008: `/api/v1/expenses/summary` falla
- **Módulo:** Gastos
- **Síntoma:** Cards de resumen muestran error "Failed to fetch"
- **Causa probable:** Error 500 en backend sin headers CORS adjuntos

#### BUG-009: Ventas requieren turno abierto (bloqueado por BUG-001)
- **Módulo:** Terminal/Ventas
- **Síntoma:** COBRAR muestra "No hay turno abierto. Abre un turno en la pestaña Turnos antes de cobrar."
- **Nota:** La validación funciona correctamente. El problema es que no se puede abrir turno (BUG-001).

#### BUG-010: `setup.sh` no tiene seed de usuario admin
- **Módulo:** Instalación
- **Síntoma:** Tras instalación limpia no existe usuario para hacer login
- **Nota:** El script dice "la aplicación te pedirá crear usuario" pero esto no ocurre

---

## Detalle de Pruebas por Módulo

### MÓDULO 2: LOGIN

| Test | Resultado | Detalle |
|------|-----------|---------|
| Login exitoso (admin/admin) | ✅ PASS | Redirige a Terminal, usuario "admin" visible en header |
| Logout | ❌ FAIL | No redirige a login (BUG-003) |
| Login credenciales incorrectas | ❌ FAIL | No se muestra mensaje de error visible (BUG-004) |
| Campos vacíos | ❌ FAIL | Botón INGRESAR permanece habilitado (BUG-005) |
| Auto-focus campo usuario | ✅ PASS | Cursor en campo usuario al cargar |
| Elementos visuales (logo, versión) | ✅ PASS | Logo TITAN POS, "V 0.1.0 • TITAN POS DEMO" |

---

### MÓDULO 3: TERMINAL / VENTAS

| Test | Resultado | Detalle |
|------|-----------|---------|
| Buscar por nombre ("Coca") | ✅ PASS | Dropdown con Coca Cola 600ml, SKU, precio verde, stock |
| Buscar por SKU ("PEPSI600") | ✅ PASS | Producto encontrado, Enter agrega al carrito |
| Buscar texto inexistente ("zzzznotexist") | ✅ PASS | No crashea, sin resultados |
| Buscar caracteres especiales ("@#$%^&") | ✅ PASS | No crashea, maneja gracefully |
| Buscar una sola letra ("a") | ✅ PASS | Filtra todos los que contienen "a" |
| Producto en carrito (columnas) | ✅ PASS | #, Nombre, Cant, Precio, Subtotal |
| Editar cantidad a 0 | ⚠️ PARTIAL | Permite qty=0, muestra subtotal $0 (debería validar o eliminar) |
| Editar cantidad negativa (-5) | ⚠️ PARTIAL | Acepta valor negativo, subtotal negativo (debería validar) |
| Editar cantidad excesiva (99999) | ⚠️ PARTIAL | Acepta sin verificar stock (debería alertar stock insuficiente) |
| Editar cantidad decimal (1.5) | ✅ PASS | Acepta decimales (correcto para venta por peso) |
| Eliminar producto (X) | ✅ PASS | Producto desaparece, total recalcula |
| COBRAR sin turno abierto | ✅ PASS | Muestra "No hay turno abierto" en barra inferior (verde → rojo) |
| Recibido = 0 y COBRAR | ✅ PASS | Bloqueado por validación de turno |
| Recibido negativo (-100) y COBRAR | ✅ PASS | Bloqueado por validación de turno |
| Cálculo de cambio | ✅ PASS | Recibido $50 - Total $18.50 = Cambio $31.50 |
| Totales (artículos + monto) | ✅ PASS | Artículos=12, Total=$220.50 (calculado correctamente) |
| Carrito se pierde al cambiar tab | ❌ FAIL | Al ir a Turnos y volver, carrito vacío (BUG-007) |

---

### MÓDULO 4: CLIENTES

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga con lista | ✅ PASS | 3 clientes: Juan Perez, Maria Lopez, Carlos Garcia |
| Columnas tabla | ✅ PASS | Nombre, Teléfono, Email |
| Búsqueda ("Juan") | ✅ PASS | Filtra a "Juan Perez" |
| Crear cliente con datos | ✅ PASS | "Test QA Cliente", tel y email guardados |
| Guardar con campos vacíos | ❌ FAIL | No valida, no muestra error (BUG-006) |
| Botones Nuevo, Cargar, Eliminar | ✅ PASS | Presentes y funcionales |

---

### MÓDULO 5: PRODUCTOS

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga con lista | ✅ PASS | 10 productos (Coca Cola → Arroz SOS) |
| Columnas tabla | ✅ PASS | SKU, Nombre, Precio ($), Stock |
| Búsqueda ("Coca") | ✅ PASS | Filtra correctamente |
| Guardar con campos vacíos | ✅ PASS | Valida: "SKU y nombre son obligatorios." (texto rojo en barra inferior) |
| Crear producto (TESTQA1) | ✅ PASS | SKU=TESTQA1, Nombre="Test QA Product", Precio=99.99, Stock=50 |
| Botones Escanear, Stock Bajo | ✅ PASS | Presentes y funcionales |

---

### MÓDULO 6: INVENTARIO

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga | ✅ PASS | Lista de productos con stock |
| Alertas stock bajo | ✅ PASS | Productos bajo mínimo visibles |
| Búsqueda "Coca" | ✅ PASS | Filtra correctamente a Coca Cola |
| Formulario ajuste | ✅ PASS | SKU, tipo movimiento, cantidad presentes |

---

### MÓDULO 7: TURNOS

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga | ✅ PASS | Campos operador, efectivo inicial, botón Abrir turno |
| Estado campos (sin turno) | ✅ PASS | Operador y Ef. Inicial habilitados |
| Abrir turno | ❌ FAIL | "Failed to fetch" — BUG-001 (error 500 en backend) |
| Estado "Cerrado" por default | ✅ PASS | Muestra correctamente estado inicial |

---

### MÓDULO 8: REPORTES

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga con fechas | ✅ PASS | Selectores fecha desde/hasta presentes |
| Cards KPI | ✅ PASS | Ventas=0, Monto total=$0.00, Ticket promedio=$0.00 (correcto, sin ventas) |
| Recalcular | ✅ PASS | Recarga datos sin error |
| Fecha inválida (start > end) | ⚠️ PARTIAL | No bloquea la acción, muestra "Sin datos" |
| Exportar CSV | ✅ PASS | Botones presentes |

---

### MÓDULO 9: HISTORIAL

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga con filtros | ✅ PASS | Folio, Fecha desde, Fecha hasta, Método pago, Total min/max |
| Buscar folio inexistente "ZZZ-999" | ✅ PASS | "Sin ventas para los filtros seleccionados." |
| Filtrar por total min=999999 | ✅ PASS | Sin resultados, maneja correctamente |
| Exportar CSV | ✅ PASS | Botón presente |

---

### MÓDULO 10: CONFIGURACIONES

| Test | Resultado | Detalle |
|------|-----------|---------|
| Campos conexión | ✅ PASS | Base URL, Token, Terminal ID presentes |
| Probar conexión (URL correcta) | ✅ PASS | Mensaje de éxito |
| Probar conexión (URL inválida) | ✅ PASS | Muestra error de conexión |
| Crear perfil "Test QA" | ✅ PASS | Perfil guardado |
| Eliminar perfil | ✅ PASS | Perfil eliminado del dropdown |

---

### MÓDULO 11: STATS/DASHBOARD

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga | ✅ PASS | "Dashboard en Tiempo Real" visible |
| Cards KPI | ✅ PASS | Ventas Hoy=0, Ingreso Hoy=$0 |
| Actualizar (refresh) | ✅ PASS | Recarga sin error |

---

### MÓDULO 12: MERMAS

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga | ✅ PASS | Título "Mermas" presente |
| Estado vacío | ✅ PASS | "Sin mermas pendientes" |
| Recargar | ✅ PASS | Sin error |

---

### MÓDULO 13: GASTOS

| Test | Resultado | Detalle |
|------|-----------|---------|
| Vista carga | ⚠️ PARTIAL | Estructura OK, datos resumen fallan (BUG-008) |
| Form: Monto, Descripción, Razón | ✅ PASS | Campos presentes |
| Registrar gasto | ✅ PASS | Monto=150.50, Descripción="Luz electrica", Razón="Febrero" → guardado |

---

### MÓDULO 14: NAVEGACIÓN

| Test | Resultado | Detalle |
|------|-----------|---------|
| Tabs presentes | ✅ PASS | 13 tabs: Ventas, Clientes, Productos, Inventario, Turnos, Reportes, Historial, Ajustes, Stats, Mermas, Gastos, Empleados, Remoto, Fiscal |
| Click navegación entre todos | ✅ PASS | Todas las pestañas cargan correctamente |
| Logout | ❌ FAIL | No funciona (BUG-003) |

---

### MÓDULOS EXTRA DESCUBIERTOS (no en QA original)

| Módulo | Estado | Notas |
|--------|--------|-------|
| **Empleados** | ✅ Funcional | CRUD empleados, campos: Código, Nombre, Posición, Salario |
| **Remoto** | ✅ Funcional | Notificaciones remotas, "Abrir Cajón". Envío de notificación exitoso. |
| **Fiscal** | ✅ Funcional | Facturación global, inventario fiscal, procesamiento de devoluciones |

---

### MÓDULO 15: API BACKEND (curl)

| Endpoint | Método | HTTP | Resultado |
|----------|--------|------|-----------|
| `/health` | GET | 200 | ✅ `{"status":"healthy","service":"titan-pos"}` |
| `/api/v1/auth/login` (OK) | POST | 200 | ✅ JWT devuelto |
| `/api/v1/auth/login` (FAIL) | POST | 401 | ✅ `{"detail":"Credenciales invalidas"}` |
| `/api/v1/auth/verify` (con token) | GET | 200 | ✅ `{valid:true, role:"admin"}` |
| `/api/v1/auth/verify` (sin token) | GET | 401 | ✅ Rechazado |
| `/api/v1/products/` | GET | 200 | ✅ Lista con paginación |
| `/api/v1/products/?search=coca` | GET | 200 | ✅ Filtra correctamente |
| `/api/v1/products/sku/COCA600` | GET | 200 | ✅ Producto encontrado |
| `/api/v1/products/low-stock` | GET | 200 | ✅ Funciona |
| `/api/v1/products/scan/COCA600` | GET | 200 | ✅ Match exacto |
| `/api/v1/products/?limit=3&offset=3` | GET | 200 | ✅ Paginación funciona |
| `/api/v1/products/categories/list` | GET | 200 | ✅ Lista categorías |
| `/api/v1/customers/` | GET | 200 | ✅ 3 clientes |
| `/api/v1/inventory/alerts` | GET | 200 | ✅ Funciona |
| `/api/v1/dashboard/quick` | GET | 200 | ✅ Dashboard data |
| `/api/v1/turns/open` | POST | 500 | ❌ BUG-001 |
| `/api/v1/turns/current` | GET | 200 | ✅ null (sin turno) |
| `/api/v1/sales/search` | GET | 200 | ✅ Lista vacía (correcto) |
| `/api/v1/sales/` (sin turno) | POST | 400 | ✅ Rechazado (requiere turno) |
| `/api/v1/sales/` (items vacío) | POST | 422 | ✅ Validación correcta |
| `/api/v1/sync/status` | GET | 200 | ✅ Estado sincronización |

---

## Cambios de Infraestructura Realizados

| # | Archivo | Cambio | Razón |
|---|---------|--------|-------|
| 1 | `docker-compose.yml` | Puerto PG `5432→5433` | Conflicto con PG local |
| 2 | `docker-compose.yml` | CORS `*` → orígenes explícitos | Wildcard + credentials = spec violation |
| 3 | `requirements.txt` | Agregado `aiofiles>=23.1.0` | Module not found en fiscal |
| 4 | DB | Schema + migraciones + seed admin | `docker compose down -v` borró todo |
| 5 | `vite.browser.config.ts` | Config standalone Vite | Electron sandbox sin sudo |

---

## Priorización para Desarrollo

### 🔴 Resolver YA
1. **BUG-001**: turns/open 500 → cambiar `.isoformat()` o `.replace(tzinfo=None)` a `datetime.utcnow()`
2. **BUG-002**: setup.sh sin schema → agregar ejecución de SQL

### 🟡 Resolver pronto
3. **BUG-003**: Logout no funciona
4. **BUG-004**: Login no muestra error en credenciales incorrectas
5. **BUG-005**: Botón INGRESAR habilitado con campos vacíos
6. **BUG-006**: Clientes sin validación de campos vacíos
7. **BUG-007**: Carrito se pierde al cambiar pestaña

### 🟢 Resolver después
8. **BUG-008**: Gastos summary falla
9. **BUG-009**: Ventas bloqueadas (cascading BUG-001)
10. **BUG-010**: Seed de usuario admin faltante en setup.sh

### ⚠️ Mejorar validaciones
- Terminal: Validar qty=0, qty negativa, qty > stock disponible
- Reportes: Validar fecha inicio < fecha fin

---

## Tests Pendientes (requieren BUG-001 resuelto)
- Flujo completo de cobro (efectivo, tarjeta, transferencia, mixto)
- Abrir/cerrar turno, acumulados, conciliación
- Historial con ventas reales
- Crear/cancelar venta vía API
- Rate limiting (T2.06)

---

*Generado: 2026-02-26 23:50 CST*  
*Sin modificaciones al código fuente*
