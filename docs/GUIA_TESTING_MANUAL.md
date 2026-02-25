# TITAN POS - Guia de Testing Manual

**Version:** 1.0
**Fecha:** 2026-02-24
**Sistema:** Punto de Venta para tiendas retail en Mexico
**Stack:** FastAPI + asyncpg + PostgreSQL 15 (backend) | Electron + React 19 + TypeScript (frontend)

---

## Tabla de Contenidos

1. [Requisitos Previos](#1-requisitos-previos)
2. [Flujo de Login](#2-flujo-de-login)
3. [Modulo Ventas - Terminal (F1)](#3-modulo-ventas---terminal-f1)
4. [Modulo Clientes (F2)](#4-modulo-clientes-f2)
5. [Modulo Productos (F3)](#5-modulo-productos-f3)
6. [Modulo Inventario (F4)](#6-modulo-inventario-f4)
7. [Modulo Turnos (F5)](#7-modulo-turnos-f5)
8. [Modulo Reportes (F6)](#8-modulo-reportes-f6)
9. [Modulo Historial (F7)](#9-modulo-historial-f7)
10. [Modulo Ajustes (F8)](#10-modulo-ajustes-f8)
11. [Modulo Estadisticas (F9)](#11-modulo-estadisticas-f9)
12. [Modulo Mermas (F10)](#12-modulo-mermas-f10)
13. [Modulo Gastos (F11)](#13-modulo-gastos-f11)
14. [Como Reportar Bugs](#14-como-reportar-bugs)
15. [Checklist de Regresion](#15-checklist-de-regresion)
16. [Atajos de Teclado](#16-atajos-de-teclado)

---

## 1. Requisitos Previos

### 1.1 Levantar la Base de Datos

```bash
cd /home/uriel/Documentos/PUNTO\ DE\ VENTA/backend
docker compose up -d postgres
```

Verificar que PostgreSQL esta corriendo:

```bash
docker compose ps
# Debe mostrar postgres con estado "healthy"
```

### 1.2 Levantar el Backend

```bash
cd /home/uriel/Documentos/PUNTO\ DE\ VENTA/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Verificar que el backend responde:

```bash
curl http://localhost:8000/health
```

**Respuesta esperada:**

```json
{
  "status": "healthy",
  "service": "titan-pos"
}
```

> **Nota:** El backend NO usa `--reload`. Si se hacen cambios en el codigo, hay que reiniciar uvicorn manualmente.

### 1.3 Levantar el Frontend

```bash
cd /home/uriel/Documentos/PUNTO\ DE\ VENTA/frontend
npm install   # Solo la primera vez
npm run dev
```

Esto abre la aplicacion Electron en modo desarrollo.

### 1.4 Levantar Todo con Docker Compose (Alternativa)

```bash
cd /home/uriel/Documentos/PUNTO\ DE\ VENTA/backend
docker compose up -d
```

Esto levanta tanto PostgreSQL (puerto 5432) como la API (puerto 8000).

### 1.5 Variables de Entorno Importantes

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://titan_user:<TU_PASSWORD>@localhost:5432/titan_pos` | Conexion a la BD |
| `JWT_SECRET` | `<TU_JWT_SECRET>` | Clave para tokens JWT |
| `CORS_ORIGINS` | `*` | Origenes permitidos (LAN local) |
| `DEBUG` | `false` | Modo debug |

### 1.6 URL Base para Pruebas API

Todos los endpoints documentados a continuacion usan como base:

```
http://localhost:8000
```

Los endpoints de modulos estan bajo el prefijo `/api/v1/`.

---

## 2. Flujo de Login

### 2.1 Obtener Token de Autenticacion

**Endpoint:** `POST /api/v1/auth/login`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<TU_PASSWORD>"}'
```

**Respuesta esperada (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

**Guardar el token para usar en peticiones siguientes:**

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 2.2 Verificar Token

**Endpoint:** `GET /api/v1/auth/verify`

```bash
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200 OK):**

```json
{
  "success": true,
  "data": {
    "valid": true,
    "user": "1",
    "role": "admin"
  }
}
```

### 2.3 Casos de Error

**Credenciales incorrectas:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "incorrecta"}'
```

**Respuesta esperada (401):**

```json
{
  "detail": "Credenciales invalidas"
}
```

**Token expirado o invalido:**

```bash
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer token_invalido_aqui"
```

**Respuesta esperada (401):**

```json
{
  "detail": "Token invalido o expirado"
}
```

### 2.4 Prueba en Frontend

1. Abrir la aplicacion Electron
2. Ingresar usuario y contrasena en la pantalla de login
3. Verificar que redirige al dashboard principal
4. Verificar que el nombre del usuario aparece en el header
5. Cerrar sesion y verificar que regresa al login

---

## 3. Modulo Ventas - Terminal (F1)

### 3.1 Prerequisito: Turno Abierto

Antes de crear ventas, debe existir un turno abierto. Ver [seccion 7](#7-modulo-turnos-f5).

### 3.2 Buscar Producto por SKU/Barcode

**Endpoint:** `GET /api/v1/products/scan/{sku}`

```bash
# Busqueda exacta por SKU
curl http://localhost:8000/api/v1/products/scan/SKU001 \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta cuando se encuentra (200 OK):**

```json
{
  "success": true,
  "data": {
    "found": true,
    "product": {
      "id": 1,
      "sku": "SKU001",
      "name": "Shampoo 400ml",
      "price": 89.90,
      "stock": 25.0
    }
  }
}
```

**Respuesta cuando NO se encuentra (devuelve sugerencias):**

```json
{
  "success": true,
  "data": {
    "found": false,
    "suggestions": [
      {"id": 5, "sku": "SKU010", "name": "Shampoo 200ml", "stock": 10}
    ]
  }
}
```

### 3.3 Listar Productos (para busqueda manual)

**Endpoint:** `GET /api/v1/products/?search=shampoo`

```bash
curl "http://localhost:8000/api/v1/products/?search=shampoo&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.4 Crear una Venta - Pago en Efectivo

**Endpoint:** `POST /api/v1/sales/`

```bash
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "items": [
      {
        "product_id": 1,
        "qty": 2,
        "price": 89.90,
        "discount": 0,
        "price_includes_tax": true
      },
      {
        "product_id": 3,
        "qty": 1,
        "price": 45.00,
        "discount": 5.00,
        "price_includes_tax": true
      }
    ],
    "payment_method": "cash",
    "cash_received": 250.00,
    "branch_id": 1,
    "serie": "A"
  }'
```

**Respuesta esperada (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": 42,
    "uuid": "a1b2c3d4-...",
    "folio": "A1-000042",
    "subtotal": 188.62,
    "tax": 30.18,
    "total": 218.80,
    "change": 31.20,
    "payment_method": "cash",
    "status": "completed"
  }
}
```

**Verificaciones post-venta:**
- El campo `change` (cambio) debe ser correcto: `cash_received - total`
- El stock del producto debe haberse reducido
- Se debe haber creado un `inventory_movement` de tipo OUT
- El `folio_visible` debe seguir la secuencia

### 3.5 Crear una Venta - Pago con Tarjeta

```bash
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "items": [
      {"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}
    ],
    "payment_method": "card",
    "branch_id": 1,
    "serie": "A"
  }'
```

### 3.6 Crear una Venta - Pago Mixto

```bash
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "items": [
      {"product_id": 1, "qty": 3, "price": 100.00, "price_includes_tax": true}
    ],
    "payment_method": "mixed",
    "mixed_cash": 150.00,
    "mixed_card": 158.62,
    "mixed_transfer": 0,
    "branch_id": 1,
    "serie": "A"
  }'
```

**Nota:** La suma de `mixed_cash + mixed_card + mixed_transfer + mixed_wallet + mixed_gift_card` debe ser igual al total (tolerancia de $0.02).

### 3.7 Crear una Venta - Credito

```bash
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "items": [
      {"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}
    ],
    "payment_method": "credit",
    "customer_id": 1,
    "branch_id": 1,
    "serie": "A"
  }'
```

**Verificaciones:**
- El `customer_id` es obligatorio para ventas a credito
- El cliente debe tener credito habilitado (`credit_authorized = true`)
- El saldo no debe exceder el limite de credito
- Se crea un registro en `credit_history` con tipo `CHARGE`

### 3.8 Consultar Detalle de una Venta

**Endpoint:** `GET /api/v1/sales/{sale_id}`

```bash
curl http://localhost:8000/api/v1/sales/42 \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta incluye la venta completa con sus items.**

### 3.9 Cancelar una Venta

**Endpoint:** `POST /api/v1/sales/{sale_id}/cancel`

> **RBAC:** Solo roles `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl -X POST http://localhost:8000/api/v1/sales/42/cancel \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200 OK):**

```json
{
  "success": true,
  "data": {"id": 42, "status": "cancelled"}
}
```

**Verificaciones post-cancelacion:**
- El stock de los productos se restaura
- Se crean `inventory_movements` de tipo IN/cancellation
- Si fue venta a credito, el saldo del cliente se revierte
- Si fue pago con monedero, el saldo se restaura
- Solo se pueden cancelar ventas con status `completed`

### 3.10 Casos de Error Importantes

**Sin turno abierto:**

```json
{"detail": "No hay turno abierto. Debe abrir un turno antes de crear ventas."}
```

**Stock insuficiente:**

```json
{"detail": "Stock insuficiente para 'Shampoo 400ml'. Disponible: 2, Solicitado: 5"}
```

**Credito sin customer_id:**

```json
{"detail": "Venta a credito requiere customer_id"}
```

**Producto bloqueado por otra venta concurrente:**

```json
{"detail": "Productos bloqueados por otra venta en proceso. Intenta de nuevo."}
```

### 3.11 Prueba en Frontend

1. Presionar **F1** para ir a la terminal de ventas
2. Escanear un codigo de barras o escribir el SKU en el campo de busqueda
3. Verificar que el producto aparece en el carrito
4. Ajustar cantidad si es necesario
5. Seleccionar metodo de pago
6. Para efectivo: ingresar el monto recibido y verificar el cambio calculado
7. Completar la venta
8. Verificar que el ticket se genera correctamente con folio, items, totales e IVA

---

## 4. Modulo Clientes (F2)

### 4.1 Listar Clientes

**Endpoint:** `GET /api/v1/customers/`

```bash
# Listar todos los clientes activos
curl "http://localhost:8000/api/v1/customers/?limit=20" \
  -H "Authorization: Bearer $TOKEN"

# Buscar por nombre, telefono, email o RFC
curl "http://localhost:8000/api/v1/customers/?search=Juan" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Juan Perez",
      "phone": "5551234567",
      "email": "juan@email.com",
      "rfc": "PEPJ800101ABC",
      "credit_limit": 5000.0,
      "credit_balance": 1200.0,
      "is_active": 1
    }
  ]
}
```

### 4.2 Crear Cliente

**Endpoint:** `POST /api/v1/customers/`

```bash
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Maria Garcia Lopez",
    "phone": "5559876543",
    "email": "maria@email.com",
    "rfc": "GALM900515XYZ",
    "address": "Calle Reforma 123, Col. Centro, CDMX",
    "credit_limit": 3000.00,
    "notes": "Cliente frecuente"
  }'
```

**Respuesta esperada (200 OK):**

```json
{"success": true, "data": {"id": 15}}
```

### 4.3 Actualizar Cliente

**Endpoint:** `PUT /api/v1/customers/{customer_id}`

```bash
curl -X PUT http://localhost:8000/api/v1/customers/15 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "phone": "5551112233",
    "credit_limit": 5000.00
  }'
```

> **RBAC:** Cambiar `credit_limit` o `is_active` requiere rol de gerente+.

### 4.4 Desactivar Cliente (Soft-Delete)

**Endpoint:** `DELETE /api/v1/customers/{customer_id}`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl -X DELETE http://localhost:8000/api/v1/customers/15 \
  -H "Authorization: Bearer $TOKEN"
```

### 4.5 Consultar Credito del Cliente

**Endpoint:** `GET /api/v1/customers/{customer_id}/credit`

```bash
curl http://localhost:8000/api/v1/customers/1/credit \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "customer_id": 1,
    "name": "Juan Perez",
    "credit_limit": 5000.0,
    "credit_balance": 1200.0,
    "available_credit": 3800.0,
    "pending_sales": [
      {"id": 10, "folio": "A1-000010", "total": 600.0, "timestamp": "2026-02-20T14:30:00"}
    ]
  }
}
```

### 4.6 Historial de Compras del Cliente

**Endpoint:** `GET /api/v1/customers/{customer_id}/sales`

```bash
curl "http://localhost:8000/api/v1/customers/1/sales?limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.7 Prueba en Frontend

1. Presionar **F2** para ir al modulo de clientes
2. Buscar un cliente por nombre o telefono
3. Crear un nuevo cliente con todos los campos
4. Editar un cliente existente (cambiar telefono, email)
5. Verificar el estado de credito del cliente
6. Ver historial de compras

---

## 5. Modulo Productos (F3)

### 5.1 Listar Productos

**Endpoint:** `GET /api/v1/products/`

```bash
# Todos los productos activos
curl "http://localhost:8000/api/v1/products/?limit=50" \
  -H "Authorization: Bearer $TOKEN"

# Buscar por nombre, SKU o barcode
curl "http://localhost:8000/api/v1/products/?search=shampoo" \
  -H "Authorization: Bearer $TOKEN"

# Filtrar por categoria
curl "http://localhost:8000/api/v1/products/?category=Higiene" \
  -H "Authorization: Bearer $TOKEN"
```

### 5.2 Crear Producto

**Endpoint:** `POST /api/v1/products/`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sku": "SHAM-001",
    "name": "Shampoo Anticaspa 400ml",
    "price": 89.90,
    "price_wholesale": 75.00,
    "cost": 45.00,
    "stock": 50,
    "category": "Higiene",
    "department": "Cuidado Personal",
    "provider": "Proveedor ABC",
    "min_stock": 10,
    "max_stock": 200,
    "tax_rate": 0.16,
    "sale_type": "unit",
    "barcode": "7501234567890",
    "description": "Shampoo anticaspa para uso diario"
  }'
```

**Respuesta esperada:**

```json
{"success": true, "data": {"id": 101}}
```

**Validaciones:**
- `sku` es obligatorio y debe ser unico
- `name` es obligatorio
- `price` debe ser >= 0
- Si el SKU ya existe, retorna error 400

### 5.3 Actualizar Producto

**Endpoint:** `PUT /api/v1/products/{product_id}`

```bash
curl -X PUT http://localhost:8000/api/v1/products/101 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "price": 99.90,
    "min_stock": 15
  }'
```

**Verificaciones:**
- Cambios de precio (`price`, `price_wholesale`, `cost`, `tax_rate`) requieren rol gerente+
- Los cambios de precio se registran automaticamente en `price_history`
- Solo se actualizan los campos enviados (los demas quedan sin cambio)

### 5.4 Desactivar Producto (Soft-Delete)

**Endpoint:** `DELETE /api/v1/products/{product_id}`

```bash
curl -X DELETE http://localhost:8000/api/v1/products/101 \
  -H "Authorization: Bearer $TOKEN"
```

### 5.5 Consultar Producto por ID

**Endpoint:** `GET /api/v1/products/{product_id}`

```bash
curl http://localhost:8000/api/v1/products/1 \
  -H "Authorization: Bearer $TOKEN"
```

### 5.6 Consultar Producto por SKU

**Endpoint:** `GET /api/v1/products/sku/{sku}`

```bash
curl http://localhost:8000/api/v1/products/sku/SHAM-001 \
  -H "Authorization: Bearer $TOKEN"
```

### 5.7 Listar Categorias

**Endpoint:** `GET /api/v1/products/categories/list`

```bash
curl http://localhost:8000/api/v1/products/categories/list \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": ["Alimentos", "Bebidas", "Higiene", "Limpieza"]
}
```

### 5.8 Productos con Stock Bajo

**Endpoint:** `GET /api/v1/products/low-stock`

```bash
curl "http://localhost:8000/api/v1/products/low-stock?limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 5.9 Stock por Sucursal

**Endpoint:** `GET /api/v1/products/{product_id}/stock-by-branch`

```bash
curl http://localhost:8000/api/v1/products/1/stock-by-branch \
  -H "Authorization: Bearer $TOKEN"
```

### 5.10 Actualizar Precio Remoto

**Endpoint:** `POST /api/v1/products/price`

```bash
curl -X POST http://localhost:8000/api/v1/products/price \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "SHAM-001", "new_price": 94.90}'
```

### 5.11 Prueba en Frontend

1. Presionar **F3** para ir al modulo de productos
2. Buscar un producto por nombre o SKU
3. Crear un producto nuevo con todos los campos
4. Editar el precio de un producto existente
5. Verificar que la categoria aparece en la lista de categorias
6. Verificar la lista de productos con stock bajo

---

## 6. Modulo Inventario (F4)

### 6.1 Listar Movimientos de Inventario

**Endpoint:** `GET /api/v1/inventory/movements`

```bash
# Todos los movimientos recientes
curl "http://localhost:8000/api/v1/inventory/movements?limit=20" \
  -H "Authorization: Bearer $TOKEN"

# Movimientos de un producto especifico
curl "http://localhost:8000/api/v1/inventory/movements?product_id=1&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Solo entradas
curl "http://localhost:8000/api/v1/inventory/movements?movement_type=IN" \
  -H "Authorization: Bearer $TOKEN"
```

### 6.2 Ajustar Stock

**Endpoint:** `POST /api/v1/inventory/adjust`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

**Agregar stock (entrada de mercancia):**

```bash
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "product_id": 1,
    "quantity": 50,
    "reason": "Recepcion de mercancia - Factura F-2024-001"
  }'
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "product_id": 1,
    "previous_stock": 25.0,
    "adjustment": 50.0,
    "new_stock": 75.0
  }
}
```

**Restar stock (merma, danio, conteo fisico):**

```bash
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "product_id": 1,
    "quantity": -3,
    "reason": "Conteo fisico - diferencia detectada"
  }'
```

**Verificaciones:**
- Usa `FOR UPDATE` para prevenir condiciones de carrera
- No permite stock negativo resultante
- Registra automaticamente un `inventory_movement` para auditoria
- `quantity` positiva = entrada, negativa = salida

### 6.3 Actualizar Stock Remoto (por SKU)

**Endpoint:** `POST /api/v1/products/stock`

```bash
curl -X POST http://localhost:8000/api/v1/products/stock \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sku": "SHAM-001",
    "quantity": 20,
    "operation": "add",
    "reason": "Restock semanal"
  }'
```

**Operaciones validas:** `add`, `subtract`, `set`

### 6.4 Alertas de Stock Bajo

**Endpoint:** `GET /api/v1/inventory/alerts`

```bash
curl http://localhost:8000/api/v1/inventory/alerts \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": [
    {
      "id": 5,
      "sku": "SHAM-001",
      "name": "Shampoo Anticaspa 400ml",
      "stock": 3.0,
      "min_stock": 10.0,
      "category": "Higiene",
      "alert_type": "low_stock"
    }
  ]
}
```

**Tipos de alerta:** `low_stock` (por debajo del minimo) y `out_of_stock` (stock = 0).

### 6.5 Prueba en Frontend

1. Presionar **F4** para ir al modulo de inventario
2. Ver la lista de movimientos recientes
3. Realizar un ajuste de inventario (agregar stock)
4. Verificar que el stock del producto se actualizo
5. Realizar un ajuste negativo y verificar que no permite stock < 0
6. Revisar las alertas de stock bajo

---

## 7. Modulo Turnos (F5)

### 7.1 Abrir un Turno

**Endpoint:** `POST /api/v1/turns/open`

```bash
curl -X POST http://localhost:8000/api/v1/turns/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "initial_cash": 1000.00,
    "branch_id": 1,
    "notes": "Turno matutino"
  }'
```

**Respuesta esperada:**

```json
{"success": true, "data": {"id": 5, "status": "open"}}
```

**Validaciones:**
- No se puede abrir un turno si ya hay uno abierto para el mismo usuario
- `initial_cash` debe ser >= 0

### 7.2 Consultar Turno Actual

**Endpoint:** `GET /api/v1/turns/current`

```bash
curl http://localhost:8000/api/v1/turns/current \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta si hay turno abierto:**

```json
{
  "success": true,
  "data": {
    "id": 5,
    "user_id": 1,
    "initial_cash": 1000.0,
    "status": "open",
    "start_timestamp": "2026-02-24T09:00:00+00:00"
  }
}
```

**Respuesta si NO hay turno abierto:**

```json
{"success": true, "data": null}
```

### 7.3 Registrar Movimiento de Caja

**Endpoint:** `POST /api/v1/turns/{turn_id}/movements`

**Entrada de efectivo (retiro de banco, por ejemplo):**

```bash
curl -X POST http://localhost:8000/api/v1/turns/5/movements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "amount": 500.00,
    "movement_type": "in",
    "reason": "Cambio adicional del banco"
  }'
```

**Retiro de efectivo:**

```bash
curl -X POST http://localhost:8000/api/v1/turns/5/movements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "amount": 2000.00,
    "movement_type": "out",
    "reason": "Retiro parcial a caja fuerte",
    "manager_pin": "1234"
  }'
```

**Nota:** Cajeros (no gerentes) necesitan proporcionar `manager_pin` para movimientos de caja.

### 7.4 Ver Resumen del Turno

**Endpoint:** `GET /api/v1/turns/{turn_id}/summary`

```bash
curl http://localhost:8000/api/v1/turns/5/summary \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "turn_id": 5,
    "status": "open",
    "initial_cash": 1000.0,
    "sales_by_method": [
      {"payment_method": "cash", "count": 15, "total": 4500.0},
      {"payment_method": "card", "count": 8, "total": 3200.0}
    ],
    "total_sales": 7700.0,
    "cash_in": 500.0,
    "cash_out": 2000.0,
    "expenses": 150.0,
    "expected_cash": 3850.0
  }
}
```

### 7.5 Cerrar Turno con Conteo de Efectivo

**Endpoint:** `POST /api/v1/turns/{turn_id}/close`

```bash
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "final_cash": 3825.00,
    "notes": "Diferencia de -$25 por redondeos",
    "denominations": [
      {"denomination": 1000, "count": 3},
      {"denomination": 500, "count": 1},
      {"denomination": 200, "count": 1},
      {"denomination": 100, "count": 1},
      {"denomination": 20, "count": 1},
      {"denomination": 5, "count": 1}
    ]
  }'
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "id": 5,
    "status": "closed",
    "expected_cash": 3850.0,
    "final_cash": 3825.0,
    "difference": -25.0
  }
}
```

**Verificaciones:**
- `expected_cash` = initial_cash + ventas_efectivo + entradas - salidas - gastos
- `difference` = final_cash - expected_cash
- Diferencia positiva = sobrante, negativa = faltante
- El conteo por denominaciones es opcional pero recomendado
- Solo el dueno del turno o un gerente+ puede cerrarlo

### 7.6 Prueba en Frontend

1. Presionar **F5** para ir al modulo de turnos
2. Abrir un turno ingresando el efectivo inicial
3. Realizar varias ventas (regresar con F1)
4. Regresar a F5 y ver el resumen del turno
5. Hacer un retiro de efectivo (salida)
6. Cerrar el turno con conteo de denominaciones
7. Verificar que la diferencia (sobrante/faltante) es correcta
8. Intentar abrir un segundo turno (debe fallar)

---

## 8. Modulo Reportes (F6)

### 8.1 Resumen Diario de Ventas

**Endpoint:** `GET /api/v1/sales/reports/daily-summary`

```bash
curl "http://localhost:8000/api/v1/sales/reports/daily-summary?limit=7" \
  -H "Authorization: Bearer $TOKEN"
```

### 8.2 Ranking de Productos

**Endpoint:** `GET /api/v1/sales/reports/product-ranking`

```bash
curl "http://localhost:8000/api/v1/sales/reports/product-ranking?limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 8.3 Mapa de Calor por Horas

**Endpoint:** `GET /api/v1/sales/reports/hourly-heatmap`

```bash
curl http://localhost:8000/api/v1/sales/reports/hourly-heatmap \
  -H "Authorization: Bearer $TOKEN"
```

### 8.4 Buscar Ventas por Folio o Fecha

**Endpoint:** `GET /api/v1/sales/search`

```bash
# Por folio
curl "http://localhost:8000/api/v1/sales/search?folio=A1-000042" \
  -H "Authorization: Bearer $TOKEN"

# Por rango de fechas
curl "http://localhost:8000/api/v1/sales/search?date_from=2026-02-01&date_to=2026-02-24" \
  -H "Authorization: Bearer $TOKEN"
```

### 8.5 Listar Ventas con Filtros

**Endpoint:** `GET /api/v1/sales/`

```bash
# Ventas completadas
curl "http://localhost:8000/api/v1/sales/?status=completed&limit=20" \
  -H "Authorization: Bearer $TOKEN"

# Ventas de un cliente especifico
curl "http://localhost:8000/api/v1/sales/?customer_id=1&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Ventas canceladas
curl "http://localhost:8000/api/v1/sales/?status=cancelled" \
  -H "Authorization: Bearer $TOKEN"

# Por rango de fechas
curl "http://localhost:8000/api/v1/sales/?start_date=2026-02-20&end_date=2026-02-24" \
  -H "Authorization: Bearer $TOKEN"
```

### 8.6 Prueba en Frontend

1. Presionar **F6** para ir a reportes
2. Ver el resumen de ventas del dia
3. Filtrar por rango de fechas
4. Verificar que los totales coinciden con las ventas realizadas
5. Revisar el ranking de productos mas vendidos

---

## 9. Modulo Historial (F7)

### 9.1 Buscar Tickets

```bash
# Buscar por folio
curl "http://localhost:8000/api/v1/sales/search?folio=A1-000042" \
  -H "Authorization: Bearer $TOKEN"
```

### 9.2 Ver Detalle de un Ticket

```bash
curl http://localhost:8000/api/v1/sales/42 \
  -H "Authorization: Bearer $TOKEN"
```

**La respuesta incluye todos los items de la venta para reimprimir el ticket.**

### 9.3 Ver Eventos de Auditoria de una Venta

**Endpoint:** `GET /api/v1/sales/{sale_id}/events`

```bash
curl http://localhost:8000/api/v1/sales/42/events \
  -H "Authorization: Bearer $TOKEN"
```

### 9.4 Prueba en Frontend

1. Presionar **F7** para ir al historial
2. Buscar un ticket por numero de folio
3. Buscar ventas por rango de fechas
4. Abrir el detalle de una venta
5. Verificar que se pueden reimprimir tickets
6. Verificar que las ventas canceladas se muestran con su estado

---

## 10. Modulo Ajustes (F8)

### 10.1 Verificar Conexion con el Servidor

```bash
curl http://localhost:8000/api/v1/sync/status \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2026-02-24T12:00:00+00:00"
}
```

### 10.2 Sincronizar Productos

```bash
curl http://localhost:8000/api/v1/sync/products \
  -H "Authorization: Bearer $TOKEN"
```

### 10.3 Sincronizar Clientes

```bash
curl http://localhost:8000/api/v1/sync/customers \
  -H "Authorization: Bearer $TOKEN"
```

### 10.4 Buscar Claves SAT

**Endpoint:** `GET /api/v1/sat/search?q=shampoo`

```bash
curl "http://localhost:8000/api/v1/sat/search?q=shampoo&limit=10"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "results": [
      {"code": "53131500", "description": "Productos para el cuidado de la piel"}
    ],
    "total": 1
  }
}
```

> **Nota:** Los endpoints del catalogo SAT no requieren autenticacion.

### 10.5 Consultar Descripcion de Clave SAT

**Endpoint:** `GET /api/v1/sat/{code}`

```bash
curl http://localhost:8000/api/v1/sat/01010101
```

### 10.6 Gestion de Empleados

**Listar empleados:**

```bash
curl "http://localhost:8000/api/v1/employees/?limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

**Crear empleado:**

```bash
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "employee_code": "EMP-005",
    "name": "Ana Martinez Ruiz",
    "position": "cajero",
    "base_salary": 8000.00,
    "commission_rate": 0.02,
    "phone": "5554443322",
    "email": "ana@tienda.com",
    "notes": "Turno vespertino"
  }'
```

> **RBAC:** CRUD de empleados requiere rol gerente+.
> **Nota:** `employee_code` es obligatorio y debe ser unico.

**Actualizar empleado:**

```bash
curl -X PUT http://localhost:8000/api/v1/employees/5 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"base_salary": 8500.00, "notes": "Aumento trimestral"}'
```

**Desactivar empleado:**

```bash
curl -X DELETE http://localhost:8000/api/v1/employees/5 \
  -H "Authorization: Bearer $TOKEN"
```

### 10.7 Prueba en Frontend

1. Presionar **F8** para ir a ajustes/configuracion
2. Verificar la conexion con el servidor
3. Realizar una sincronizacion de productos
4. Administrar empleados (crear, editar, desactivar)
5. Buscar claves SAT para facturacion
6. Configurar parametros del sistema

---

## 11. Modulo Estadisticas (F9)

### 11.1 Dashboard Rapido

**Endpoint:** `GET /api/v1/dashboard/quick`

```bash
curl http://localhost:8000/api/v1/dashboard/quick \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "ventas_hoy": 23,
    "total_hoy": 15680.50,
    "mermas_pendientes": 2,
    "timestamp": "2026-02-24T12:00:00+00:00"
  }
}
```

### 11.2 Dashboard RESICO (Fiscal)

**Endpoint:** `GET /api/v1/dashboard/resico`

```bash
curl http://localhost:8000/api/v1/dashboard/resico \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "serie_a": 1250000.0,
    "serie_b": 350000.0,
    "total": 1600000.0,
    "limite_resico": 3500000.0,
    "restante": 2250000.0,
    "porcentaje": 35.71,
    "proyeccion_anual": 2800000.0,
    "status": "GREEN",
    "dias_restantes": 310
  }
}
```

**Semaforo RESICO:**
- `GREEN`: < 70% del limite ($3,500,000 MXN)
- `YELLOW`: 70-90% del limite
- `RED`: > 90% del limite

### 11.3 Dashboard de Gastos

**Endpoint:** `GET /api/v1/dashboard/expenses`

```bash
curl http://localhost:8000/api/v1/dashboard/expenses \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "month": 12500.0,
    "year": 85000.0
  }
}
```

### 11.4 Dashboard de Riqueza

**Endpoint:** `GET /api/v1/dashboard/wealth`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl http://localhost:8000/api/v1/dashboard/wealth \
  -H "Authorization: Bearer $TOKEN"
```

### 11.5 Dashboard de IA (Alertas Inteligentes)

**Endpoint:** `GET /api/v1/dashboard/ai`

```bash
curl http://localhost:8000/api/v1/dashboard/ai \
  -H "Authorization: Bearer $TOKEN"
```

**Incluye:**
- Predicciones de desabasto (stockout)
- Productos mas vendidos con tendencias
- Anomalias detectadas

### 11.6 Dashboard Ejecutivo

**Endpoint:** `GET /api/v1/dashboard/executive`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl http://localhost:8000/api/v1/dashboard/executive \
  -H "Authorization: Bearer $TOKEN"
```

### 11.7 Prueba en Frontend

1. Presionar **F9** para ir a estadisticas
2. Verificar que el widget de ventas del dia muestra datos correctos
3. Revisar el semaforo RESICO (debe coincidir con las ventas acumuladas)
4. Verificar los gastos del mes y del anio
5. Revisar las alertas de stock inteligentes
6. Si se tiene rol gerente+, verificar el dashboard de riqueza y ejecutivo

---

## 12. Modulo Mermas (F10)

### 12.1 Ver Mermas Pendientes

**Endpoint:** `GET /api/v1/mermas/pending`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl http://localhost:8000/api/v1/mermas/pending \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "count": 2,
    "mermas": [
      {
        "id": 1,
        "product": "Shampoo 400ml",
        "sku": "SHAM-001",
        "quantity": 3.0,
        "unit_cost": 45.0,
        "total_value": 135.0,
        "loss_type": "damage",
        "reason": "Botellas rotas en almacen",
        "category": "Higiene",
        "has_photo": true,
        "witness": "Pedro Lopez",
        "created_at": "2026-02-24T08:30:00"
      }
    ]
  }
}
```

### 12.2 Aprobar una Merma

**Endpoint:** `POST /api/v1/mermas/approve`

```bash
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "merma_id": 1,
    "approved": true,
    "notes": "Verificado en bodega - producto danado"
  }'
```

**Respuesta esperada:**

```json
{"success": true, "data": {"status": "approved"}}
```

### 12.3 Rechazar una Merma

```bash
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "merma_id": 2,
    "approved": false,
    "notes": "El producto no presenta dano visible"
  }'
```

**Respuesta esperada:**

```json
{"success": true, "data": {"status": "rejected"}}
```

**Verificaciones:**
- Usa `FOR UPDATE` para evitar aprobacion doble (TOCTOU)
- Solo mermas con status `pending` pueden ser aprobadas/rechazadas
- Mermas ya procesadas retornan error 400

### 12.4 Prueba en Frontend

1. Presionar **F10** para ir al modulo de mermas
2. Ver la lista de mermas pendientes de aprobacion
3. Revisar los detalles de cada merma (producto, cantidad, razon, testigo)
4. Aprobar una merma con notas justificativas
5. Rechazar una merma
6. Verificar que la merma procesada ya no aparece en pendientes
7. Intentar aprobar una merma ya procesada (debe mostrar error)

---

## 13. Modulo Gastos (F11)

### 13.1 Registrar un Gasto

**Endpoint:** `POST /api/v1/expenses/`

> **RBAC:** Solo `admin`, `manager`, `owner`, `gerente`, `dueño`.

```bash
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "amount": 350.00,
    "description": "Compra de material de limpieza",
    "reason": "Limpieza quincenal de tienda"
  }'
```

**Respuesta esperada:**

```json
{"success": true, "data": {"id": 8}}
```

**Notas:**
- El gasto se vincula automaticamente al turno abierto del usuario (si existe)
- Se registra como un `cash_movement` de tipo `expense`
- `amount` debe ser > 0

### 13.2 Ver Resumen de Gastos

**Endpoint:** `GET /api/v1/expenses/summary`

```bash
curl http://localhost:8000/api/v1/expenses/summary \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "data": {
    "month": 4500.0,
    "year": 32000.0
  }
}
```

### 13.3 Prueba en Frontend

1. Presionar **F11** para ir al modulo de gastos
2. Registrar un gasto con descripcion y monto
3. Verificar que aparece en el resumen del mes
4. Verificar que el gasto afecta el resumen del turno actual
5. Intentar registrar un gasto con rol de cajero (debe rechazar)

---

## 14. Como Reportar Bugs

### 14.1 Plantilla de Reporte de Bug

```
## Titulo del Bug
[Descripcion breve y descriptiva del problema]

## Severidad
[ ] CRITICAL — El sistema se cae, se pierde dinero, o la venta no se puede completar
[ ] HIGH — Funcionalidad principal no funciona, pero hay workaround
[ ] MEDIUM — Funcionalidad secundaria con problemas
[ ] LOW — Error cosmetico o de texto

## Ambiente
- Navegador/App: [Electron v1.0.0 / Chrome 121]
- Sistema Operativo: [Linux / Windows 10]
- Backend: [commit hash o version]
- Frontend: [commit hash o version]
- Fecha y hora: [2026-02-24 14:30]

## Pasos para Reproducir
1. Iniciar sesion como [rol: cajero/gerente/admin]
2. Ir a [pantalla/modulo - ejemplo: Terminal F1]
3. [Accion especifica - ejemplo: Escanear producto SKU-001]
4. [Accion siguiente - ejemplo: Cambiar cantidad a 5]
5. [Accion que causa el error]

## Resultado Esperado
[Que deberia pasar]

## Resultado Obtenido
[Que paso en realidad]

## Evidencia
- Screenshot: [adjuntar captura de pantalla]
- Logs del backend: [pegar las lineas relevantes del log]
- Console del navegador: [pegar errores de la consola F12]
- curl del endpoint: [si aplica, incluir el curl y la respuesta]

## Informacion Adicional
[Cualquier contexto extra, frecuencia del problema, datos de prueba usados]
```

### 14.2 Donde Obtener Logs

**Logs del backend:**

```bash
# Si se ejecuta directamente
# Los logs aparecen en la terminal donde se inicio uvicorn

# Si se ejecuta con Docker
docker compose logs -f api
```

**Logs del frontend (Electron):**
- Abrir DevTools con `Ctrl+Shift+I`
- Ir a la pestana "Console"
- Copiar errores en rojo

**Logs de la base de datos:**

```bash
docker compose logs -f postgres
```

### 14.3 Ejemplos de Bugs por Severidad

**CRITICAL:**
- Venta se completa pero no descuenta stock
- Se puede vender con stock negativo
- Token de autenticacion no expira nunca
- Datos de credito del cliente se corrompen

**HIGH:**
- No se puede cancelar una venta desde el frontend
- El conteo de cierre de turno no coincide con las ventas
- La busqueda por barcode no encuentra productos existentes

**MEDIUM:**
- El resumen de gastos muestra el mes anterior en vez del actual
- La paginacion de productos no funciona despues de la pagina 5
- El campo de descuento acepta valores negativos

**LOW:**
- Error de ortografia en un mensaje de error
- El boton de "Cancelar" esta desalineado
- El tooltip de un campo no se muestra correctamente

---

## 15. Checklist de Regresion

Ejecutar antes de cada release o despliegue:

### 15.1 Autenticacion

- [ ] Login con credenciales validas devuelve token
- [ ] Login con credenciales invalidas devuelve 401
- [ ] Token expirado es rechazado
- [ ] Endpoints protegidos rechazan peticiones sin token
- [ ] Verificar que `/api/v1/auth/verify` funciona

### 15.2 Turnos

- [ ] Se puede abrir un turno con efectivo inicial
- [ ] No se puede abrir dos turnos a la vez para el mismo usuario
- [ ] Se puede cerrar un turno con conteo de efectivo
- [ ] El calculo de efectivo esperado es correcto
- [ ] La diferencia (sobrante/faltante) se calcula bien

### 15.3 Ventas

- [ ] Se puede crear una venta con pago en efectivo
- [ ] El cambio se calcula correctamente
- [ ] Se puede crear una venta con tarjeta
- [ ] Se puede crear una venta con pago mixto
- [ ] La suma de pagos mixtos debe coincidir con el total
- [ ] Se puede crear una venta a credito (con cliente)
- [ ] No se puede vender a credito sin `customer_id`
- [ ] No se puede vender mas stock del disponible
- [ ] El stock se descuenta correctamente tras la venta
- [ ] El folio se genera secuencialmente
- [ ] Se puede cancelar una venta (solo gerente+)
- [ ] Al cancelar, el stock se restaura
- [ ] Al cancelar venta a credito, el saldo del cliente se revierte
- [ ] No se puede crear venta sin turno abierto

### 15.4 Productos

- [ ] Se pueden listar productos con paginacion
- [ ] Se puede buscar por nombre, SKU y barcode
- [ ] Se puede crear un producto con todos los campos
- [ ] No se puede crear producto con SKU duplicado
- [ ] Se puede actualizar precio (solo gerente+)
- [ ] Los cambios de precio se registran en price_history
- [ ] Se puede soft-delete un producto
- [ ] El scan por barcode/SKU funciona

### 15.5 Clientes

- [ ] Se pueden listar clientes con busqueda
- [ ] Se puede crear un cliente
- [ ] Se puede actualizar un cliente
- [ ] Solo gerentes pueden cambiar `credit_limit`
- [ ] La informacion de credito es correcta
- [ ] El historial de compras se muestra

### 15.6 Inventario

- [ ] Se puede ajustar stock positivamente (entrada)
- [ ] Se puede ajustar stock negativamente (salida)
- [ ] No se permite stock resultante negativo
- [ ] Se registran movimientos de auditoria
- [ ] Las alertas de stock bajo funcionan

### 15.7 Mermas

- [ ] Se listan mermas pendientes
- [ ] Se puede aprobar una merma
- [ ] Se puede rechazar una merma
- [ ] No se puede procesar una merma ya procesada

### 15.8 Gastos

- [ ] Se puede registrar un gasto (solo gerente+)
- [ ] El resumen muestra totales correctos del mes y anio
- [ ] El gasto se vincula al turno abierto

### 15.9 Dashboards

- [ ] Dashboard rapido muestra ventas del dia
- [ ] Dashboard RESICO muestra acumulado anual
- [ ] Semaforo RESICO es correcto segun el porcentaje
- [ ] Dashboard de gastos muestra datos del periodo

### 15.10 Sincronizacion

- [ ] `/api/v1/sync/status` responde correctamente
- [ ] `/api/v1/sync/products` devuelve todos los productos activos
- [ ] `/api/v1/sync/customers` devuelve todos los clientes activos
- [ ] `/api/v1/sync/shifts` devuelve turnos abiertos

### 15.11 Frontend

- [ ] Todos los atajos F1-F11 navegan a la pantalla correcta
- [ ] Escape cierra modales abiertos
- [ ] La interfaz se ve correcta en resolucion 1366x768 y 1920x1080
- [ ] No hay errores en la consola del navegador
- [ ] El polling del header no causa errores 401 sin sesion activa

### 15.12 RBAC (Control de Acceso)

- [ ] Cajero NO puede: crear productos, cancelar ventas, ajustar inventario, aprobar mermas, registrar gastos
- [ ] Gerente SI puede: todo lo anterior
- [ ] Cajero necesita PIN de gerente para movimientos de caja

---

## 16. Atajos de Teclado

| Tecla | Pantalla | Ruta Frontend |
|---|---|---|
| **F1** | Terminal de Ventas | `/terminal` |
| **F2** | Clientes | `/clientes` |
| **F3** | Productos | `/productos` |
| **F4** | Inventario | `/inventario` |
| **F5** | Turnos | `/turnos` |
| **F6** | Reportes | `/reportes` |
| **F7** | Historial de Ventas | `/historial` |
| **F8** | Configuraciones / Ajustes | `/configuraciones` |
| **F9** | Estadisticas / Dashboard | `/estadisticas` |
| **F10** | Mermas | `/mermas` |
| **F11** | Gastos / Egresos | `/gastos` |
| **Escape** | Cerrar modal activo | (global) |

**Notas sobre atajos:**
- Los atajos F1-F11 solo funcionan cuando hay una sesion activa (token almacenado)
- Los atajos se desactivan cuando hay un modal abierto o un campo de texto enfocado (depende del componente)
- En algunos navegadores, F5 puede recargar la pagina; la aplicacion Electron previene esto con `event.preventDefault()`
- F11 en algunos sistemas operativos activa pantalla completa; el frontend lo previene

---

## Apendice: Referencia Rapida de Endpoints

### Autenticacion (`/api/v1/auth`)

| Metodo | Ruta | Descripcion | Auth |
|---|---|---|---|
| POST | `/login` | Iniciar sesion | No |
| GET | `/verify` | Verificar token | Si |

### Productos (`/api/v1/products`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/` | Listar productos | Si | Todos |
| GET | `/{id}` | Obtener por ID | Si | Todos |
| GET | `/sku/{sku}` | Obtener por SKU | Si | Todos |
| GET | `/scan/{sku}` | Buscar por barcode/SKU | Si | Todos |
| GET | `/low-stock` | Productos bajo stock | Si | Todos |
| GET | `/categories/list` | Listar categorias | Si | Todos |
| GET | `/{id}/stock-by-branch` | Stock por sucursal | Si | Todos |
| POST | `/` | Crear producto | Si | Gerente+ |
| PUT | `/{id}` | Actualizar producto | Si | Gerente+ (precios) |
| DELETE | `/{id}` | Desactivar producto | Si | Gerente+ |
| POST | `/stock` | Actualizar stock remoto | Si | Todos |
| POST | `/price` | Actualizar precio remoto | Si | Gerente+ |

### Clientes (`/api/v1/customers`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/` | Listar clientes | Si | Todos |
| GET | `/{id}` | Obtener por ID | Si | Todos |
| GET | `/{id}/sales` | Historial de compras | Si | Todos |
| GET | `/{id}/credit` | Info de credito | Si | Todos |
| POST | `/` | Crear cliente | Si | Todos |
| PUT | `/{id}` | Actualizar cliente | Si | Gerente+ (credito) |
| DELETE | `/{id}` | Desactivar cliente | Si | Gerente+ |

### Ventas (`/api/v1/sales`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/` | Listar ventas | Si | Todos |
| GET | `/search` | Buscar ventas | Si | Todos |
| GET | `/{id}` | Detalle de venta | Si | Todos |
| GET | `/{id}/events` | Eventos de auditoria | Si | Todos |
| POST | `/` | Crear venta | Si | Todos |
| POST | `/{id}/cancel` | Cancelar venta | Si | Gerente+ |
| GET | `/reports/daily-summary` | Resumen diario | Si | Todos |
| GET | `/reports/product-ranking` | Ranking productos | Si | Todos |
| GET | `/reports/hourly-heatmap` | Mapa calor horario | Si | Todos |

### Inventario (`/api/v1/inventory`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/movements` | Listar movimientos | Si | Todos |
| GET | `/alerts` | Alertas de stock bajo | Si | Todos |
| POST | `/adjust` | Ajustar stock | Si | Gerente+ |

### Turnos (`/api/v1/turns`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| POST | `/open` | Abrir turno | Si | Todos |
| POST | `/{id}/close` | Cerrar turno | Si | Dueno/Gerente+ |
| GET | `/current` | Turno actual | Si | Todos |
| GET | `/{id}` | Detalle turno | Si | Dueno/Gerente+ |
| GET | `/{id}/summary` | Resumen turno | Si | Dueno/Gerente+ |
| POST | `/{id}/movements` | Movimiento de caja | Si | Todos (PIN gerente) |

### Mermas (`/api/v1/mermas`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/pending` | Listar pendientes | Si | Gerente+ |
| POST | `/approve` | Aprobar/rechazar | Si | Gerente+ |

### Gastos (`/api/v1/expenses`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/summary` | Resumen mes/anio | Si | Todos |
| POST | `/` | Registrar gasto | Si | Gerente+ |

### Dashboard (`/api/v1/dashboard`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/quick` | Status rapido | Si | Todos |
| GET | `/resico` | Monitoreo RESICO | Si | Todos |
| GET | `/expenses` | Gastos mes/anio | Si | Todos |
| GET | `/wealth` | Riqueza real | Si | Gerente+ |
| GET | `/ai` | Alertas IA | Si | Todos |
| GET | `/executive` | Ejecutivo completo | Si | Gerente+ |

### Empleados (`/api/v1/employees`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/` | Listar empleados | Si | Todos |
| GET | `/{id}` | Obtener por ID | Si | Todos |
| POST | `/` | Crear empleado | Si | Gerente+ |
| PUT | `/{id}` | Actualizar empleado | Si | Gerente+ |
| DELETE | `/{id}` | Desactivar empleado | Si | Gerente+ |

### Sincronizacion (`/api/v1/sync`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| GET | `/status` | Estado conexion | Si | Todos |
| GET | `/products` | Pull productos | Si | Todos |
| GET | `/customers` | Pull clientes | Si | Todos |
| GET | `/sales` | Pull ventas | Si | Todos |
| GET | `/shifts` | Pull turnos | Si | Todos |
| POST | `/{table}` | Push datos | Si | Gerente+ |

### Remoto (`/api/v1/remote`)

| Metodo | Ruta | Descripcion | Auth | RBAC |
|---|---|---|---|---|
| POST | `/open-drawer` | Abrir cajon | Si | Gerente+ |
| GET | `/turn-status` | Estado turno | Si | Todos |
| GET | `/live-sales` | Ventas en vivo | Si | Todos |
| POST | `/notification` | Enviar notificacion | Si | Gerente+ |
| GET | `/notifications/pending` | Obtener pendientes | Si | Todos |
| POST | `/change-price` | Cambiar precio | Si | Gerente+ |
| GET | `/system-status` | Estado del sistema | Si | Todos |

### Catalogo SAT (`/api/v1/sat`)

| Metodo | Ruta | Descripcion | Auth |
|---|---|---|---|
| GET | `/search?q=texto` | Buscar claves SAT | No |
| GET | `/{code}` | Descripcion de clave | No |

---

*Documento generado para TITAN POS v1.0 - Febrero 2026*
