# Log de pruebas de ruptura — 2026-03-07

Objetivo: intentar romper el POS y su entorno inmediato con pruebas automatizadas, stress y E2E para detectar fallos reales, degradaciones y gaps de tooling.

---

## Alcance

- Backend FastAPI activo en `http://127.0.0.1:8000`
- Frontend browser build vía Playwright
- Scripts agresivos existentes `v11` a `v16`
- Suites automáticas backend/frontend para baseline

## Baseline antes de romper

- Backend subset crítico: `71 passed`
- Backend regresiones extra (`security`, `auth`, `remote`): `27 passed`
- Frontend Vitest: `69 passed`
- Health backend antes y después de la carga: `200 OK`

## Pruebas ejecutadas

### 1. Stress / ruptura backend

- `python3 backend/v11_edge.py`
- `python3 backend/v12_ddos.py`
- `python3 backend/v14_heavy_tickets.py`
- `python3 backend/v15_math_audit.py`
- `python3 backend/v16_megaticket_x10.py`

### 2. E2E browser

- `E2E_START_SERVER=1 npx playwright test --max-failures=1 --reporter=line`

## Resultados

### Backend

- Busqueda concurrente con payload tipo SQLi/XSS/null bytes: `50/50` respuestas `200`, sin `500`.
- Flood por endpoint:
  - `/products`, `/customers`, `/inventory/movements`, `/dashboard/quick`, `/sales/search`: `500/500` respuestas `200`.
  - `/sales/` con payload vacio: `500/500` respuestas `4XX`, `0` respuestas `5XX`.
- Flood global: `3000` requests mezcladas, `2500` éxitos `200`, `500` errores cliente `4XX`, `0` errores servidor `5XX`.
- Ticket pesado V14: `50/50` ventas exitosas.
- Mega ticket mixto V16: `500/500` ventas exitosas en `9.53s`.
- Health final del backend: sano, sin crash observable.

### E2E

- El run E2E completo falló desde el primer caso.
- Con `E2E_START_SERVER=1` el primer fallo real fue login:
  - el spec usa `admin/admin123`
  - el backend activo acepta `admin/admin`
  - resultado: la UI permanece en `/#/login` con mensaje `Credenciales invalidas`

## Hallazgos prioritarios

### 1. El suite E2E no es ejecutable out-of-the-box

Severidad: alta

Detalles:

- `frontend/e2e/e2e-browser-v7.spec.ts` usa por defecto `E2E_PASS || 'admin123'`
- el backend local activo acepta `admin/admin`
- además `npm run test:e2e` falla si no existe frontend en `5173`; requiere `E2E_START_SERVER=1` o levantar `dev:browser` manualmente

Impacto:

- falso negativo inmediato en CI/local
- reduce confianza en la suite E2E

Mejora sugerida:

- alinear credenciales por defecto o exigir `E2E_USER` / `E2E_PASS`
- documentar en el script/package o cambiar `test:e2e` para autoarrancar frontend

### 2. El rate limit del login penaliza la recuperacion inmediata tras flood

Severidad: media-alta

Detalles:

- después del flood global, `POST /api/v1/auth/login` respondió `429`
- siguió devolviendo `429` a los `0s` y `5s`
- recuperó acceso normal hasta ~`15s`
- mensaje observado: `Rate limit exceeded: 5 per 1 minute`

Impacto:

- un pico agresivo o una tanda de reintentos puede bloquear temporalmente login legítimo
- complica soporte y recuperación operativa tras incidentes o pruebas

Mejora sugerida:

- revisar límites y ventana del login
- considerar llave por IP + usuario + backoff más granular
- separar más claramente flood general de autenticación legítima

### 3. Hay una discrepancia contable de 1 centavo en el desglose de IVA

Severidad: media

Detalles:

- en `backend/v15_math_audit.py`
- venta auditada:
  - subtotal DB: `1530.17`
  - IVA DB: `244.83`
  - total DB: `1775.00`
- recálculo Python línea por línea:
  - subtotal: `1530.17`
  - IVA: `244.84`
  - total teórico: `1775.01`

Impacto:

- el total cobrado cuadra, pero el desglose fiscal/contable tiene una diferencia de redondeo
- puede volverse relevante en auditorías o conciliaciones masivas

Mejora sugerida:

- revisar una política única de redondeo por línea vs total
- fijar tests de regresión para tickets grandes con precios IVA-incluido

## Hallazgos secundarios

### 4. `v11_edge.py` no valida bien su propio escenario de ventas concurrentes

Severidad: baja

Detalles:

- reportó `0` ventas exitosas en la fase concurrente
- inspección posterior mostró que el script toma el primer producto disponible y este tenía stock `0`
- error observado: `Stock insuficiente para '<script>alert('XSS_PROD')</script>'`

Impacto:

- el script puede dar una falsa impresión de fallo del backend

Mejora sugerida:

- seleccionar explícitamente un producto activo con stock positivo antes del test

### 5. El tooling E2E depende demasiado del estado manual del entorno

Severidad: baja-media

Detalles:

- sin frontend corriendo en `5173`, el run original queda inválido
- el comando correcto para ejecución autónoma fue con `E2E_START_SERVER=1`

Mejora sugerida:

- convertir `npm run test:e2e` en un wrapper robusto con servidor frontend automático

## Conclusión

El backend mostró buena resiliencia bajo carga agresiva:

- `0` errores `5XX` en flood global
- ventas pesadas y mega tickets completados sin crash
- salud general preservada

Los principales problemas encontrados no fueron caídas del core transaccional, sino:

- fragilidad del entorno E2E
- rate limiting demasiado visible en recuperación post-flood
- discrepancia de 1 centavo en desglose de impuestos para tickets grandes

## Acciones recomendadas

1. Corregir `frontend/e2e/e2e-browser-v7.spec.ts` y/o el comando `test:e2e` para que el suite sea realmente ejecutable.
2. Ajustar o revalidar el rate limit de login después de pruebas de saturación.
3. Añadir pruebas contables de regresión para redondeos de IVA con tickets grandes IVA-incluido.
4. Corregir `backend/v11_edge.py` para que use un producto con stock positivo y no genere falsos negativos.

---

## Segunda ronda profunda — 2026-03-07

Se ejecutó una segunda tanda enfocada en descubrir fallos posteriores al primer login/E2E y en someter wrappers del `control-plane` a escenarios incompletos.

### Pruebas ejecutadas

- `python3 backend/v13_volumen_ventas.py`
- inspección manual del payload real usado por V13
- `E2E_START_SERVER=1 E2E_PASS=admin npx playwright test --max-failures=5 --reporter=line`
- ejecución ad hoc de `release_manifest()` y `dashboard_alerts_send()` con escenarios faltantes

### Hallazgos nuevos

#### 6. `v13_volumen_ventas.py` es otro falso negativo de carga

Severidad: baja-media

Detalles:

- V13 reportó `10000` errores `4XX` y `0` éxitos, pero `0` errores `5XX`
- inspección posterior mostró que toma el primer producto del catálogo, que en este entorno fue:
  - `sku: XSS-01`
  - `stock: 0`
  - `description: None`
- por eso el script no estaba estresando ventas válidas sino validaciones de stock insuficiente

Impacto:

- TPS reportado sin ventas exitosas no mide el camino transaccional real
- puede ocultar regresiones verdaderas o exagerar falsas conclusiones

#### 7. El spec E2E de login tiene un caso inválido contra la UI real

Severidad: media

Detalles:

- con `E2E_PASS=admin`, login exitoso y login fallido sí avanzaron
- el caso `EC-Login: Campos vacíos` falla por timeout porque intenta hacer click sobre un botón deshabilitado
- la UI real deshabilita el botón mientras usuario o contraseña estén vacíos

Impacto:

- el spec falla aunque el comportamiento del producto sea correcto
- genera ruido y bloquea la detección de bugs posteriores

#### 8. El spec E2E de navegación espera un link que no existe como link visible

Severidad: media

Detalles:

- el test `E2E-17.1` busca `getByRole('link', { name: 'Stats' })`
- el navbar real expone `Estadísticas` dentro del menú `Más`, no como link primario visible con texto `Stats`
- resultado: timeout al intentar encontrar/clickear ese link

Impacto:

- la suite E2E no refleja la navegación real del producto

#### 9. Los tests posteriores de tabs parecen contaminados por login repetido / rate limit

Severidad: media

Detalles:

- tras fallos/reintentos, el caso `E2E-6.1: Turnos` volvió a fallar dentro de `loginAndCloseModal()`
- el síntoma fue quedar otra vez en `/#/login`
- no se confirmó el body exacto en este run, pero es consistente con el problema ya observado de `429` en login tras múltiples intentos

Impacto:

- las fallas de autenticación contaminan resultados de tabs que no están relacionadas con login

#### 10. `releases/manifest` puede devolver éxito con backend faltante

Severidad: media

Detalles:

- se ejecutó un escenario controlado donde solo existía release de app y no de backend
- resultado observado:
  - `success: true`
  - `artifacts.backend: null`

Impacto:

- el cliente/updater recibe un manifest incompleto pero aparentemente válido
- el error se mueve aguas abajo y complica diagnóstico

#### 11. `dashboard/alerts/send` falla duro si Telegram no está configurado

Severidad: baja-media

Detalles:

- al invocar la ruta/lógica sin `TELEGRAM_BOT_TOKEN` ni `TELEGRAM_CHAT_ID`, se lanzó `RuntimeError`
- no hay degradación controlada tipo `400/412` con mensaje operativo

Impacto:

- experiencia pobre de operación
- si se invoca desde UI/automatización puede parecer error interno en vez de problema de configuración

### Recomendaciones adicionales

5. Corregir `backend/v13_volumen_ventas.py` para filtrar por productos con stock positivo.
6. Reescribir `EC-Login: Campos vacíos` en E2E para validar estado deshabilitado en vez de intentar click.
7. Alinear `E2E-17.1` con el navbar actual (`Estadísticas` dentro de `Más`) o cambiar la UI si ese link debe ser primario.
8. Hacer que `releases/manifest` responda error cuando falten artefactos obligatorios.
9. Convertir `dashboard/alerts/send` en una respuesta operativa controlada cuando falte configuración de Telegram.
