# QA Manual Completo — TITAN POS

Cobertura exhaustiva de toda la aplicacion: cada pantalla, boton, campo, filtro, endpoint y caso borde.

**Version:** 1.0
**Ultima actualizacion:** 2026-02-25
**Archivos bajo prueba:** Frontend (Electron + React), Backend (FastAPI), Instalador (setup.sh)

---

## Indice

1. [Instalador](#1-instalador)
2. [Login](#2-login)
3. [Terminal / Punto de Venta](#3-terminal--punto-de-venta)
4. [Clientes](#4-clientes)
5. [Productos](#5-productos)
6. [Inventario](#6-inventario)
7. [Turnos](#7-turnos)
8. [Reportes](#8-reportes)
9. [Historial](#9-historial)
10. [Configuraciones](#10-configuraciones)
11. [Dashboard / Estadisticas](#11-dashboard--estadisticas)
12. [Mermas](#12-mermas)
13. [Gastos](#13-gastos)
14. [Navegacion Global y Atajos](#14-navegacion-global-y-atajos)
15. [API Backend](#15-api-backend)
16. [Seguridad y RBAC](#16-seguridad-y-rbac)
17. [Concurrencia y Casos Borde](#17-concurrencia-y-casos-borde)
18. [Inputs Inesperados y Monkey Testing](#18-inputs-inesperados-y-monkey-testing)
19. [Registro de Resultados](#19-registro-de-resultados)

---

## Convenciones

- **[CAMPO]** = campo de texto/numero
- **[BOTON]** = boton clickeable
- **[DROPDOWN]** = menu desplegable
- **[CHECK]** = verificacion sin accion del tester
- Prioridad: CRITICA > ALTA > MEDIA > BAJA
- Cada prueba indica: Precondicion → Pasos → Resultado esperado

---

## 1. Instalador

### T1.01 — Instalacion limpia (CRITICA)

**Precondicion:** Docker instalado, `.env` NO existe, contenedores abajo.

```bash
docker compose down -v 2>/dev/null
rm -f .env CREDENCIALES.txt
rm -f ~/Escritorio/TITAN-POS.desktop ~/Desktop/TITAN-POS.desktop
```

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Doble clic en `INSTALAR TITAN POS` | Se abre terminal |
| 2 | Observar banner | "TITAN POS — INSTALADOR" con bordes unicode |
| 3 | Fase 1 | `[■□□□□□]` → `✔ Docker y Docker Compose encontrados` |
| 4 | Fase 2 | `[■■□□□□]` → `✔ Archivo .env generado` + `✔ Credenciales guardadas` |
| 5 | Fase 3 | `[■■■□□□]` → `✔ Contenedores construidos` |
| 6 | Fase 4 | `[■■■■□□]` → puntos animados → `✔ Base de datos lista` |
| 7 | Fase 5 | `[■■■■■□]` → puntos animados → `✔ Servidor listo` |
| 8 | Fase 6 | `[■■■■■■]` → `✔ Acceso directo creado` |
| 9 | Mensaje final | `✅ ¡INSTALACION COMPLETADA!` |
| 10 | Navegador | Se abre en `http://localhost:8000` |
| 11 | Terminal | `Presiona Enter para cerrar...` y espera |

**Verificaciones post:**

```bash
grep POSTGRES_PASSWORD .env         # alfanumerico ~24 chars, NO "change-me"
grep JWT_SECRET .env                # hex 64 chars
grep ADMIN_API_PASSWORD .env        # alfanumerico ~16 chars
grep '@postgres:' .env              # DATABASE_URL apunta a Docker, NO localhost
cat CREDENCIALES.txt                # mismos valores que .env
docker compose ps                   # postgres y api en "Up"
curl -s http://localhost:8000/health # responde JSON healthy
ls ~/Escritorio/TITAN-POS.desktop 2>/dev/null || ls ~/Desktop/TITAN-POS.desktop
```

### T1.02 — Sin Docker instalado (ALTA)

**Precondicion:** Docker NO instalado (VM limpia o `sudo apt remove docker.io`).

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | `bash setup.sh` | `⚠ Docker no encontrado. Intentando instalar...` |
| 2a | (con sudo + internet) | `✔ Docker instalado correctamente` + warning cerrar sesion |
| 2b | (sin permisos) | `✖ No se pudo instalar` + instrucciones claras |
| 3 | (caso 2b) | `ERROR: Docker es necesario` y sale con codigo != 0 |

### T1.03 — Re-ejecucion idempotente (CRITICA)

**Precondicion:** T1.01 completado. `.env` y contenedores existen.

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Anotar `grep POSTGRES_PASSWORD .env` | Valor X |
| 2 | `bash setup.sh` | Fase 2: `✔ Archivo .env ya existe (no se modifica)` |
| 3 | | NO aparece "Credenciales guardadas" |
| 4 | Completa 6 fases | Sin errores |
| 5 | `grep POSTGRES_PASSWORD .env` | **Mismo valor X** |

### T1.04 — Contenedores caidos (ALTA)

**Precondicion:** `.env` existe, `docker compose down`.

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | `bash setup.sh` | No regenera .env |
| 2 | | Reconstruye y levanta contenedores |
| 3 | `curl -s localhost:8000/health` | Responde OK |

### T1.05 — Falta .env.example (MEDIA)

```bash
mv .env.example .env.example.bak && rm -f .env
```

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | `bash setup.sh` | `ERROR: No se encontro .env.example` y sale |

Restaurar: `mv .env.example.bak .env.example`

### T1.06 — Puerto 8000 ocupado (MEDIA)

```bash
python3 -m http.server 8000 &
```

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | `bash setup.sh` | Fase 5 falla o timeout |
| 2 | | Mensaje de error claro |

Limpiar: `kill %1`

### T1.07 — Acceso directo escritorio (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Ir al escritorio | Icono "TITAN POS" visible |
| 2 | Doble clic | Se abre navegador en localhost:8000 |
| 3 | | App responde (no error conexion) |
| 4 | GNOME: no pide confirmacion | `gio set trusted` funciono |

### T1.08 — Escritorio espanol (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Sistema en espanol | `~/Escritorio/TITAN-POS.desktop` existe |
| 2 | | NO se creo en `~/Desktop` |

### T1.09 — Escritorio ingles (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Sistema en ingles (no existe ~/Escritorio) | `~/Desktop/TITAN-POS.desktop` existe |

### T1.10 — Ruta con espacios (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Proyecto en ruta con espacios (ej: `PUNTO DE VENTA`) | |
| 2 | Doble clic en INSTALAR | NO falla por espacios |
| 3 | | .env creado en ruta correcta |

### T1.11 — Proyecto copiado/USB (ALTA)

```bash
cp -r "/ruta/proyecto" /tmp/titan-usb-test
```

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Doble clic en INSTALAR desde /tmp/titan-usb-test | Funciona |
| 2 | | .env creado en /tmp/titan-usb-test/ (no en ubicacion original) |

### T1.12 — Seguridad de secretos (CRITICA)

| # | Verificacion | Comando | Esperado |
|---|-------------|---------|----------|
| 1 | CREDENCIALES.txt ignorado | `git status CREDENCIALES.txt` | No rastreado |
| 2 | .env ignorado | `git status .env` | No rastreado |
| 3 | Secretos aleatorios | Comparar 2 instalaciones | Valores diferentes |
| 4 | Sin chars problematicos | `grep -E '[/+=]' .env` (excluyendo URLs) | Limpio |
| 5 | DATABASE_URL Docker | `grep DATABASE_URL .env` | `@postgres:5432` |
| 6 | JWT hex 64 chars | `grep JWT .env \| cut -d= -f2 \| wc -c` | 65 |

### T1.13 — make setup (BAJA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | `make setup` | Ejecuta setup.sh, identico a T1.01 |

### T1.14 — Ejecucion terminal directa (BAJA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | `bash setup.sh` | Funciona |
| 2 | `./setup.sh` | Funciona (shebang + chmod +x) |

---

## 2. Login

### T2.01 — Login exitoso (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Abrir app | Pantalla de login visible |
| 2 | [CAMPO] Usuario: escribir usuario valido | Texto aparece, icono User |
| 3 | [CAMPO] Contraseña: escribir password valido | Texto enmascarado (••••), icono Lock |
| 4 | [BOTON] INGRESAR | Spinner, redirige a Terminal |

### T2.02 — Login con credenciales incorrectas (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Usuario correcto, password incorrecto | Mensaje de error (pulso animado) |
| 2 | Usuario inexistente | Mensaje de error |
| 3 | El mensaje NO revela si es usuario o password | Generico: "Credenciales invalidas" |

### T2.03 — Login con campos vacios (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Usuario vacio | [BOTON] INGRESAR deshabilitado |
| 2 | [CAMPO] Password vacio | [BOTON] INGRESAR deshabilitado |
| 3 | Ambos vacios | [BOTON] INGRESAR deshabilitado |

### T2.04 — Auto-focus (BAJA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Abrir pantalla de login | Cursor en campo usuario automaticamente |

### T2.05 — Elementos visuales (BAJA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Panel izquierdo (desktop) | Logo TITAN POS, icono Terminal, subtitulo |
| 2 | Indicadores estado | "Server Online", "Local Database" |
| 3 | Footer | "V 0.1.0 • TITAN POS DEMO" |

### T2.06 — Rate limiting login (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Enviar 6+ intentos fallidos en 1 minuto | Error 429 Too Many Requests |
| 2 | Esperar 1 minuto | Puede intentar de nuevo |

---

## 3. Terminal / Punto de Venta

### Busqueda de Productos

#### T3.01 — Buscar por nombre (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: escribir nombre parcial | Dropdown con resultados filtrados |
| 2 | Cada resultado muestra | SKU (mono), Nombre, Precio (verde), Stock (derecha) |
| 3 | Max 20 resultados visibles | No mas de 20 |
| 4 | Click en resultado | Producto agregado al carrito |

#### T3.02 — Buscar por SKU (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Escribir SKU exacto | Producto aparece en dropdown |
| 2 | Enter | Primer resultado se agrega al carrito |

#### T3.03 — Busqueda sin resultados (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Escribir texto que no coincide | Dropdown vacio o mensaje "sin resultados" |

#### T3.04 — Atajo F10 (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Presionar F10 | Focus en barra de busqueda |

### Selector de Cantidad

#### T3.05 — Cantidad por defecto (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | [CAMPO] Cant: valor inicial | 1 |

#### T3.06 — Cambiar cantidad antes de agregar (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Cant: escribir 5 | Valor 5 |
| 2 | Agregar producto | Se agrega con cantidad 5 |

#### T3.07 — Cantidad minima (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Cant: escribir 0 | No permite (min: 1) |
| 2 | [CAMPO] Cant: escribir negativo | No permite |

### Carrito

#### T3.08 — Carrito vacio (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Sin productos en carrito | Icono carrito, "Sin productos en el ticket" |
| 2 | [BOTON] COBRAR | Deshabilitado |

#### T3.09 — Agregar producto al carrito (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Buscar y seleccionar producto | Aparece fila en carrito |
| 2 | Fila muestra | #, Nombre (bold), Cantidad, Precio unitario, Subtotal |
| 3 | [BOTON] COBRAR | Habilitado |

#### T3.10 — Agregar mismo producto dos veces (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Agregar producto A | Fila con cant: 1 |
| 2 | Agregar producto A otra vez | Cantidad incrementa a 2 (o se agrega nueva fila segun implementacion) |

#### T3.11 — Editar cantidad en carrito (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en campo cantidad de un item | Campo editable (resaltado azul) |
| 2 | Cambiar a 3 | Subtotal se recalcula |
| 3 | Total del ticket se actualiza | Correcto |

#### T3.12 — Eliminar producto del carrito (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en X de un item | Item desaparece |
| 2 | Total se recalcula | Correcto |
| 3 | Si era el ultimo item | Carrito muestra estado vacio |

#### T3.13 — Seleccionar item con click (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en fila de item | Fila resaltada azul |
| 2 | Presionar Delete/Backspace | Item eliminado |
| 3 | Presionar +/- | Cantidad incrementa/decrementa |

#### T3.14 — Producto comun Ctrl+P (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Ctrl+P | Agrega producto comun al carrito |
| 2 | Nota "(comun)" visible | Texto amber |

#### T3.15 — Descuento por item Ctrl+D (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar item → Ctrl+D | Prompt o modal de descuento |
| 2 | Ingresar porcentaje | Badge rose "-%X" aparece en item |
| 3 | Subtotal recalculado | Con descuento aplicado |

#### T3.16 — Descuento global Ctrl+G (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Ctrl+G | Prompt o modal descuento global |
| 2 | Ingresar porcentaje | Label "Descuento [X]%" con monto rose |
| 3 | Total recalculado | Con descuento global |

### Metodo de Pago y Cobro

#### T3.17 — Pago en efectivo (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Pago: "Efectivo" (default) | Campo "Recibido" visible |
| 2 | [CAMPO] Recibido: monto mayor al total | Label "Cambio" con monto amber |
| 3 | [CAMPO] Recibido: monto menor al total | Label "Falta" con monto rose |
| 4 | [BOTON] COBRAR | Venta procesada, carrito se limpia |

#### T3.18 — Pago con tarjeta (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Pago: "Tarjeta" | Campo "Recibido" DESAPARECE |
| 2 | [BOTON] COBRAR | Venta procesada |

#### T3.19 — Pago transferencia (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Pago: "Transferencia" | Campo "Recibido" DESAPARECE |
| 2 | [BOTON] COBRAR | Venta procesada |

#### T3.20 — Cambiar metodo limpia recibido (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Efectivo, escribir $500 en recibido | Muestra cambio |
| 2 | Cambiar a Tarjeta | Campo recibido desaparece |
| 3 | Cambiar de vuelta a Efectivo | Campo recibido vacio (no $500) |

#### T3.21 — Cliente en venta (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Cliente: vacio | Default "Publico General" |
| 2 | [CAMPO] Cliente: escribir nombre | Se guarda con la venta |

#### T3.22 — Cobrar con carrito vacio (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Sin productos | [BOTON] COBRAR deshabilitado |

#### T3.23 — Cobrar F12 (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Carrito con productos → F12 | Misma accion que click COBRAR |

#### T3.24 — Doble cobro (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click rapido 2 veces en COBRAR | Solo UNA venta se procesa |
| 2 | | Boton muestra "Procesando..." y se deshabilita |

### Totales y Resumen

#### T3.25 — Calculo de articulos (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | 3 productos: cant 1, 2, 1 | "Articulos: 4" |

#### T3.26 — Calculo de total (CRITICA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Producto $50 x2 + producto $30 x1 | Total: $130.00 |
| 2 | Con descuento item 10% en $50 | Total: $120.00 |
| 3 | Con descuento global 5% sobre $130 | Total: $123.50 |

### Tickets Multiples

#### T3.27 — Crear nuevo ticket (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] + (nuevo ticket) | Carrito se limpia, nuevo ticket activo |
| 2 | Ticket anterior queda guardado | |
| 3 | Dropdown muestra tickets | Lista de tickets activos |

#### T3.28 — Cambiar entre tickets (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Agregar productos a ticket 1 | |
| 2 | Crear ticket 2, agregar otros productos | |
| 3 | Seleccionar ticket 1 en dropdown | Productos de ticket 1 visibles |

#### T3.29 — Cerrar ticket (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] X (cerrar ticket) | Ticket eliminado |
| 2 | Solo 1 ticket activo | Boton X deshabilitado |

#### T3.30 — Limite de tickets (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Crear 8 tickets | |
| 2 | [BOTON] + | Deshabilitado (max 8) |

### Tickets Pendientes

#### T3.31 — Guardar ticket pendiente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Carrito con productos → [BOTON] Guardar | Ticket guardado |
| 2 | Carrito se limpia | |
| 3 | [DROPDOWN] Pendientes (N) | Contador incremento |

#### T3.32 — Recuperar ticket pendiente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Pendientes → seleccionar ticket | Carrito se llena con productos del ticket |
| 2 | Muestra label + conteo de items | |

#### T3.33 — Guardar con carrito vacio (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Sin productos → [BOTON] Guardar | Deshabilitado |

### Estado del Turno

#### T3.34 — Indicador de turno (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Turno abierto | Punto verde, "Turno: [Operador]", ventas, total |
| 2 | Sin turno | Punto gris, "Sin turno" |

### Atajos de Teclado Terminal

#### T3.35 — Todos los atajos (MEDIA)

| Atajo | Accion esperada |
|-------|----------------|
| F10 | Focus barra busqueda |
| F12 | Cobrar |
| + | Incrementar cantidad item seleccionado |
| - | Decrementar cantidad item seleccionado |
| Delete | Eliminar item seleccionado |
| Backspace | Eliminar item seleccionado |
| Ctrl+P | Agregar producto comun |
| Ctrl+D | Descuento item |
| Ctrl+G | Descuento global |
| Ctrl+N | Nuevo ticket |

### Barra de Estado

#### T3.36 — Referencia de atajos visible (BAJA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Desktop | Barra inferior muestra: F10, F12, +/-, Del, Ctrl+P, Ctrl+D |
| 2 | Conteo productos | "[N] productos" visible |

---

## 4. Clientes

### CRUD

#### T4.01 — Crear cliente (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Nombre: "Juan Perez" | Texto aparece |
| 2 | [CAMPO] Telefono: "9991234567" | Texto aparece |
| 3 | [CAMPO] Email: "juan@test.com" | Texto aparece |
| 4 | [BOTON] Guardar | Cliente creado, aparece en lista |

#### T4.02 — Crear sin nombre (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Nombre vacio → [BOTON] Guardar | Deshabilitado |

#### T4.03 — Cargar clientes (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Cargar | Lista de clientes se llena |
| 2 | Tabla muestra | Nombre, Telefono, Email |

#### T4.04 — Seleccionar cliente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en fila de cliente | Fila resaltada (borde azul izquierdo) |
| 2 | | Campos de formulario se llenan con datos del cliente |
| 3 | [BOTON] cambia a "Actualizar" | |

#### T4.05 — Actualizar cliente (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar cliente | Datos en formulario |
| 2 | Cambiar telefono | |
| 3 | [BOTON] Actualizar | Cambio guardado, tabla actualizada |

#### T4.06 — Eliminar cliente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar cliente | |
| 2 | [BOTON] Eliminar | Popup de confirmacion |
| 3 | Confirmar | Cliente eliminado (soft delete) |

#### T4.07 — Eliminar sin seleccion (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Sin cliente seleccionado | [BOTON] Eliminar deshabilitado |

#### T4.08 — Nuevo (limpiar form) (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar cliente → [BOTON] Nuevo | Formulario se limpia |
| 2 | | Boton vuelve a "Guardar" |

### Busqueda

#### T4.09 — Buscar por nombre (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: "Juan" | Lista filtrada por nombre |

#### T4.10 — Buscar por telefono (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: "999" | Lista filtrada por telefono |

#### T4.11 — Buscar por email (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: "@test" | Lista filtrada por email |

#### T4.12 — Busqueda sin resultados (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Buscar texto inexistente | "Sin resultados para la busqueda." |

#### T4.13 — Lista vacia (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Sin clientes cargados | "Sin clientes. Haz clic en Cargar." |

### Paginacion

#### T4.14 — Paginacion (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Mas de 50 clientes | Paginacion visible |
| 2 | [BOTON] Sig >> | Pagina 2 |
| 3 | [BOTON] << Ant | Pagina 1 |
| 4 | En primera pagina | << Ant deshabilitado |
| 5 | En ultima pagina | Sig >> deshabilitado |
| 6 | Contador | "1 / N" visible |

---

## 5. Productos

### CRUD

#### T5.01 — Crear producto (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] SKU: "PROD001" | Texto aparece |
| 2 | [CAMPO] Nombre: "Coca Cola 600ml" | Texto aparece |
| 3 | [CAMPO] Precio: 18.50 | Numero aceptado |
| 4 | [CAMPO] Stock: 100 | Numero aceptado |
| 5 | [BOTON] Guardar | Producto creado, aparece en lista |

#### T5.02 — SKU duplicado (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Crear con SKU existente | Error: SKU ya existe |

#### T5.03 — Precio invalido (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Precio: 0 | Error o validacion |
| 2 | Precio: negativo | No permite |
| 3 | Precio: vacio | Validacion falla |

#### T5.04 — Seleccionar producto (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en fila | Formulario se llena |
| 2 | [CAMPO] SKU | Deshabilitado (no editable en existente) |
| 3 | [BOTON] cambia a "Actualizar" | |

#### T5.05 — Actualizar producto (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar → cambiar precio | |
| 2 | [BOTON] Actualizar | Precio actualizado en lista |

#### T5.06 — Eliminar producto (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar → [BOTON] Eliminar | Confirmacion popup |
| 2 | Confirmar | Producto eliminado (soft delete) |

#### T5.07 — Cargar productos (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Cargar | Lista llena con productos |
| 2 | Columnas: SKU, Nombre, Precio, Stock | Correctas |

### Busqueda

#### T5.08 — Buscar por SKU (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: "PROD" | Filtrado por SKU |

#### T5.09 — Buscar por nombre (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: "Coca" | Filtrado por nombre |

---

## 6. Inventario

#### T6.01 — Carga inventario (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Cargar | Tabla: SKU, Nombre, Stock |

#### T6.02 — Movimiento entrada (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] SKU: "PROD001" | |
| 2 | [DROPDOWN] Tipo: "Entrada" | |
| 3 | [CAMPO] Cantidad: 50 | |
| 4 | [BOTON] Aplicar | Confirmacion popup |
| 5 | Confirmar | Stock incrementa en 50 |

#### T6.03 — Movimiento salida (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Tipo: "Salida" | |
| 2 | [CAMPO] Cantidad: 10 | |
| 3 | [BOTON] Aplicar → Confirmar | Stock decrementa en 10 |

#### T6.04 — Salida mayor que stock (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Salida cantidad > stock actual | Error: stock insuficiente |

#### T6.05 — Cantidad invalida (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Cantidad: 0 | No permite (min: 1) |
| 2 | Cantidad negativa | No permite |

#### T6.06 — SKU vacio (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | SKU vacio → [BOTON] Aplicar | Deshabilitado |

#### T6.07 — Click en fila auto-llena SKU (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en fila de producto en tabla | [CAMPO] SKU se llena automaticamente |

#### T6.08 — Busqueda inventario (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Buscar: "PROD" | Filtrado por SKU o nombre |

---

## 7. Turnos

### Apertura/Cierre

#### T7.01 — Abrir turno (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Operador: "Lupita" | |
| 2 | [CAMPO] Efectivo inicial: 500 | |
| 3 | [BOTON] Abrir turno | Turno abierto |
| 4 | Card "Estado" | "Abierto" |
| 5 | Card "Operador actual" | "Lupita" |
| 6 | Card "Duracion turno" | "00:00" y contando |

#### T7.02 — Abrir turno duplicado (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Con turno ya abierto | [BOTON] Abrir turno deshabilitado |

#### T7.03 — Cerrar turno (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Efectivo cierre: 1500 | |
| 2 | [BOTON] Cerrar turno | Confirmacion popup |
| 3 | Confirmar | Turno cerrado, diferencia calculada |

#### T7.04 — Cerrar sin turno abierto (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Sin turno abierto | [BOTON] Cerrar turno deshabilitado |

### Cards de Acumulados

#### T7.05 — Acumulados correctos (CRITICA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | "Ventas turno" | Cuenta de ventas del turno actual |
| 2 | "Total turno" | Suma total en moneda |
| 3 | "Efectivo acumulado" | Solo ventas en efectivo |
| 4 | "Esperado sugerido cierre" | inicial + efectivo_acumulado |

#### T7.06 — Conciliacion backend (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Conciliar con Backend | Datos del servidor cargados |
| 2 | Cards conciliacion | Diferencia verde si $0, amber si > $0 |

### Historial y Operaciones

#### T7.07 — Historial de turnos (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Tabla historial | Apertura, Cierre, Operador, Inicial, Ventas, Total, etc. |
| 2 | Diferencia color | Rojo si negativa, verde si positiva |

#### T7.08 — Exportar turno CSV (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Exportar turno CSV | Descarga archivo .csv |
| 2 | Contenido | Datos del turno seleccionado |

#### T7.09 — Corte de impresion (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Imprimir corte | Vista previa de impresion |

#### T7.10 — Dropdown seleccion turno (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Turno: seleccionar historico | Datos de ese turno en cards |
| 2 | Default: "Turno activo" | |

#### T7.11 — Aplicar sugerencia esperado (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Aplicar sugerencia de esperado | [CAMPO] Esperado se llena |

#### T7.12 — Notas de turno (BAJA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Notas: escribir nota | Se guarda con el turno |

### Campos deshabilitados

#### T7.13 — Estados de campos (ALTA)

| Condicion | Operador | Ef. Inicial | Ef. Cierre | Ef. Esperado |
|-----------|----------|-------------|------------|--------------|
| Sin turno | Habilitado | Habilitado | Deshabilitado | Deshabilitado |
| Turno abierto | Deshabilitado | Deshabilitado | Habilitado | Habilitado |

---

## 8. Reportes

#### T8.01 — Cargar reportes (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Fecha desde: 7 dias atras (default) | |
| 2 | [CAMPO] Fecha hasta: hoy (default) | |
| 3 | [BOTON] Recalcular | Datos cargados |

#### T8.02 — KPIs (CRITICA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | "Ventas" | Numero entero de ventas en periodo |
| 2 | "Monto total" | Suma en formato moneda |
| 3 | "Ticket promedio" | Monto total / Ventas |

#### T8.03 — Metodos de pago (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Card "Metodos de pago" | Lista metodos con monto |
| 2 | Sin ventas | "Sin datos." |

#### T8.04 — Top productos (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Tabla top 10 | SKU/Nombre, Cantidad, Importe |
| 2 | Ordenados | Por cantidad descendente |

#### T8.05 — Filtro de fechas (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Fecha desde > Fecha hasta | No permite (validacion) |
| 2 | Rango de 1 dia | Solo ventas de ese dia |

#### T8.06 — Exportar resumen CSV (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Exportar resumen CSV | Descarga .csv con metricas |
| 2 | Sin ventas | Boton deshabilitado |

#### T8.07 — Exportar top CSV (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Exportar top CSV | Descarga .csv con top 10 |
| 2 | Sin datos top | Boton deshabilitado |

---

## 9. Historial

### Filtros

#### T9.01 — Filtros completos (CRITICA)

| Campo | Tipo | Default | Verificar |
|-------|------|---------|-----------|
| Folio | Texto | vacio | Busqueda parcial |
| Fecha desde | Date picker | 7 dias atras | |
| Fecha hasta | Date picker | hoy | |
| Metodo pago | [DROPDOWN] | "Todos metodos" | Efectivo, Tarjeta, Transferencia |
| Total min | Numero (min: 0) | vacio | |
| Total max | Numero (min: 0) | vacio | |

#### T9.02 — Buscar por folio (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Folio: "A-001" | |
| 2 | [BOTON] Buscar | Solo ventas con ese folio |

#### T9.03 — Filtrar por metodo de pago (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Metodo: "Efectivo" | Solo ventas en efectivo |
| 2 | [DROPDOWN] Metodo: "Tarjeta" | Solo ventas con tarjeta |
| 3 | [DROPDOWN] Metodo: "Transferencia" | Solo transferencias |
| 4 | [DROPDOWN] Metodo: "Todos metodos" | Todas las ventas |

#### T9.04 — Filtrar por rango de total (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Total min: 100, Total max: 500 | Solo ventas entre $100-$500 |
| 2 | Solo Total min: 200 | Ventas >= $200 |
| 3 | Solo Total max: 50 | Ventas <= $50 |

#### T9.05 — Filtrar por fecha (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Fecha desde: ayer, hasta: ayer | Solo ventas de ayer |

#### T9.06 — Combinacion de filtros (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Efectivo + rango fecha + total min | Interseccion de todos los filtros |

#### T9.07 — Sin resultados (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Filtros que no coinciden | "Sin ventas para los filtros seleccionados." |

### Detalle de Venta

#### T9.08 — Ver detalle (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click en venta de la lista izquierda | Panel derecho muestra detalle |
| 2 | Detalle muestra | Folio, Cliente, Metodo, Total |
| 3 | JSON detalle | Items completos en formato pre |

#### T9.09 — Exportar historial CSV (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Exportar CSV | Descarga con filas visibles |

### Lista de Ventas

#### T9.10 — Formato lista (MEDIA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Columnas | Folio, Fecha, Cliente, Total (derecha) |
| 2 | Hover en fila | Efecto visual |
| 3 | Click en fila | Detalle carga a la derecha |
| 4 | Scroll | Max-height 65vh, scrollable |

---

## 10. Configuraciones

### Conexion

#### T10.01 — Configurar conexion (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Base URL: "http://localhost:8000" | |
| 2 | [CAMPO] Token: (token JWT) | Campo tipo password |
| 3 | [CAMPO] Terminal ID: 1 | Numero min: 1 |
| 4 | [BOTON] Guardar | Guardado en localStorage |

#### T10.02 — Test conexion (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Config correcta → [BOTON] Test conexion | Mensaje exito |
| 2 | URL incorrecta → [BOTON] Test conexion | Mensaje error |

### Perfiles

#### T10.03 — Guardar perfil (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Nombre perfil: "Caja 1" | |
| 2 | [BOTON] Guardar perfil | Perfil creado |
| 3 | [DROPDOWN] Perfil | "Caja 1" aparece en lista |

#### T10.04 — Cargar perfil (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [DROPDOWN] Perfil: "Caja 1" | Campos se llenan con config del perfil |

#### T10.05 — Eliminar perfil (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Seleccionar perfil → [BOTON] Eliminar perfil | Confirmacion popup |
| 2 | Confirmar | Perfil eliminado de dropdown |
| 3 | Sin perfil seleccionado | Boton deshabilitado |

### Paneles Info

#### T10.06 — Info del sistema (BAJA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Panel "Info del sistema" | JSON formateado scrollable |
| 2 | Sin info | "Sin informacion." |

#### T10.07 — Estado sincronizacion (BAJA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Panel "Estado de sincronizacion" | JSON formateado scrollable |
| 2 | Sin info | "Sin informacion." |

---

## 11. Dashboard / Estadisticas

#### T11.01 — Carga dashboard (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Navegar a Estadisticas (F9) | "Dashboard en Tiempo Real" |
| 2 | [BOTON] Refresh | Recarga datos |

#### T11.02 — Cards KPI (CRITICA)

| Card | Icono | Color | Verificar |
|------|-------|-------|-----------|
| Ventas Hoy | TrendingUp | Emerald | Numero entero |
| Ingreso Hoy | DollarSign | Blue | Formato moneda |
| Mermas Pendientes | AlertTriangle | Amber/zinc | Amber si > 0 |

#### T11.03 — Auto-refresh (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Esperar 30 segundos | Datos se actualizan automaticamente |
| 2 | Timestamp "Ultima actualizacion" | Cambia cada 30s |

#### T11.04 — Error de carga (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Backend caido | Error rose con mensaje |
| 2 | Backend vuelve | Proximo refresh recupera |

#### T11.05 — Estado loading (BAJA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Durante carga | Spinner RefreshCw animado |

---

## 12. Mermas

#### T12.01 — Cargar mermas (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Navegar a Mermas (F10) | Titulo "Mermas" |
| 2 | Badge pendientes | Numero amber (si > 0) |
| 3 | [BOTON] Refresh | Recarga lista |

#### T12.02 — Tabla mermas (ALTA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Columnas | Producto, Cantidad, Valor, Tipo, Razon, Fecha, Notas, Acciones |
| 2 | Producto | Nombre + SKU (texto xs zinc) |
| 3 | Valor | Formato moneda, alineado derecha |
| 4 | Fecha | Formato legible, texto xs |

#### T12.03 — Aprobar merma (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Check (verde) en fila | Merma aprobada |
| 2 | | Stock del producto se reduce |
| 3 | | Merma desaparece de pendientes |

#### T12.04 — Rechazar merma (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] X (rose) en fila | Merma rechazada |
| 2 | | Stock NO se reduce |
| 3 | | Merma desaparece de pendientes |

#### T12.05 — Notas inline (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Escribir en campo notas de una merma | Texto se guarda |

#### T12.06 — Sin mermas (MEDIA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Todas procesadas | Icono AlertTriangle, "Sin mermas pendientes" |

#### T12.07 — Accion en progreso (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click aprobar en merma A | Botones de TODAS las mermas deshabilitados |
| 2 | Completada | Botones se rehabilitan |

---

## 13. Gastos

#### T13.01 — Cards resumen (ALTA)

| Card | Verificar |
|------|-----------|
| Total este mes | Icono Receipt azul, formato moneda |
| Total este anio | Icono Receipt morado, formato moneda |

#### T13.02 — Registrar gasto (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [CAMPO] Monto: 150.50 | step 0.01, min 0.01 |
| 2 | [CAMPO] Descripcion: "Luz electrica" | Requerido |
| 3 | [CAMPO] Razon: "Recibo febrero" | Opcional |
| 4 | [BOTON] Registrar | Gasto guardado |
| 5 | | Mensaje exito verde (auto-desaparece 3s) |
| 6 | | Cards resumen se actualizan |

#### T13.03 — Campos requeridos (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Monto vacio | No permite registrar |
| 2 | Descripcion vacia | No permite registrar |
| 3 | Monto: 0 | No permite (min: 0.01) |

#### T13.04 — Estado submitting (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Click Registrar | Spinner en boton |
| 2 | | Todos los campos deshabilitados |
| 3 | | Boton deshabilitado (previene doble envio) |

#### T13.05 — Error al registrar (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Backend caido → Registrar | Mensaje error rose |

#### T13.06 — Refresh (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Refresh | Recarga resumen |
| 2 | Durante carga | Boton deshabilitado |

---

## 14. Navegacion Global y Atajos

### Navegacion

#### T14.01 — Barra navegacion (CRITICA)

| Pestana | Icono | Ruta | Tecla |
|---------|-------|------|-------|
| Ventas | ShoppingCart | /terminal | F1 |
| Clientes | Users | /clientes | F2 |
| Productos | Box | /productos | F3 |
| Inventario | ClipboardList | /inventario | F4 |
| Turnos | Clock | /turnos | F5 |
| Reportes | BarChart3 | /reportes | F6 |
| Historial | FileText | /historial | F7 |
| Ajustes | Settings | /configuraciones | F8 |
| Stats | TrendingUp | /estadisticas | F9 |
| Mermas | AlertTriangle | /mermas | F10 |
| Gastos | Receipt | /gastos | F11 |

**Verificar cada una:** click navega correctamente, icono correcto, tecla F funciona.

#### T14.02 — Atajos F1-F11 (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Presionar F1 desde cualquier pantalla | Navega a Terminal |
| 2 | Presionar F2 | Navega a Clientes |
| 3 | ... hasta F11 | Cada una navega correctamente |

#### T14.03 — Logout (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | [BOTON] Logout (LogOut icon) | Verifica tickets pendientes |
| 2 | Sin tickets pendientes | Cierra sesion, redirige a login |
| 3 | Con tickets pendientes | Aviso de confirmacion |
| 4 | Con turno abierto | Aviso de confirmacion |

### Error Boundaries

#### T14.04 — Error en pestana (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Error en una pestana | "Error en [NombrePestana]" |
| 2 | | "Las demas pestanas siguen funcionando" |
| 3 | [BOTON] Reintentar | Recarga la pestana |
| 4 | [BOTON] Ir a Terminal | Navega a Terminal |
| 5 | Otras pestanas | Siguen funcionando (F1-F11) |

#### T14.05 — Error global (BAJA)

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Error critico no capturado | "Error inesperado" (rose) |
| 2 | [BOTON] Volver al inicio | Redirige a / |

---

## 15. API Backend

### Health y Sistema

#### T15.01 — Health check (CRITICA)

```bash
curl -s http://localhost:8000/health
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Status code | 200 |
| 2 | Body | `{"status": "healthy", "service": "titan-pos"}` |

### Auth

#### T15.02 — Login API (CRITICA)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Status 200 | `{access_token, expires_in}` |
| 2 | Token valido | JWT decodificable con sub y role |

#### T15.03 — Login fallido (ALTA)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d '{"username":"admin","password":"wrong"}'
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Status | 401 |
| 2 | No timing leak | Respuesta ~mismo tiempo que login exitoso |

#### T15.04 — Verify token (ALTA)

```bash
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer $TOKEN"
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Token valido | `{valid: true, user, role}` |
| 2 | Token expirado | 401 |
| 3 | Sin token | 401 |

### Productos API

#### T15.05 — CRUD productos API (CRITICA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/products/` | GET | Lista con paginacion (limit, offset) |
| `/api/v1/products/` | GET `?search=coca` | Busqueda fuzzy nombre/SKU/barcode |
| `/api/v1/products/` | GET `?category=bebidas` | Filtro categoria |
| `/api/v1/products/` | GET `?is_active=0` | Solo inactivos |
| `/api/v1/products/{id}` | GET | Producto por ID (404 si no existe) |
| `/api/v1/products/sku/{sku}` | GET | Producto por SKU |
| `/api/v1/products/low-stock` | GET | Productos bajo min_stock |
| `/api/v1/products/scan/{sku}` | GET | Match exacto + fuzzy sugerencias |
| `/api/v1/products/` | POST | Crear (requiere manager+) |
| `/api/v1/products/{id}` | PUT | Actualizar (precio requiere manager+) |
| `/api/v1/products/{id}` | DELETE | Soft delete (requiere manager+) |
| `/api/v1/products/stock` | POST | Ajustar stock remoto (FOR UPDATE) |
| `/api/v1/products/price` | POST | Cambiar precio remoto + audit |
| `/api/v1/products/categories/list` | GET | Lista categorias unicas |
| `/api/v1/products/{id}/stock-by-branch` | GET | Stock desglosado por sucursal |

#### T15.06 — Paginacion API (ALTA)

```bash
curl "$URL/api/v1/products/?limit=10&offset=0" -H "Authorization: Bearer $T"
curl "$URL/api/v1/products/?limit=10&offset=10" -H "Authorization: Bearer $T"
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | limit=10 | Max 10 resultados |
| 2 | offset=10 | Segunda pagina |
| 3 | limit=0 | Error validacion |
| 4 | limit=1001 | Error validacion (max 1000) |

### Ventas API

#### T15.07 — Crear venta completa (CRITICA)

```bash
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{"product_id": 1, "qty": 2, "price": 18.50}],
    "payment_method": "cash",
    "cash_received": 50,
    "serie": "A"
  }'
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Status 200 | id, uuid, folio, subtotal, tax, total, change |
| 2 | Stock reducido | Producto tiene 2 menos |
| 3 | Folio unico | Secuencial, atomico |

#### T15.08 — Todos los metodos de pago (CRITICA)

| Metodo | Request extra | Verificar |
|--------|-------------|-----------|
| cash | cash_received | change calculado |
| card | - | Total completo |
| transfer | - | Total completo |
| mixed | mixed_cash, mixed_card, etc. | Suma ±$0.02 del total |
| credit | customer_id | credit_balance actualizado |
| wallet | customer_id | wallet_balance reducido |

#### T15.09 — Validaciones venta (ALTA)

| Escenario | Resultado esperado |
|-----------|-------------------|
| items vacio | 400 |
| qty: 0 | 400 |
| qty: NaN | 400 |
| price: Infinity | 400 |
| Stock insuficiente | 400 |
| credit sin customer_id | 400 |
| mixed suma != total (fuera de tolerancia) | 400 |

#### T15.10 — Cancelar venta (ALTA)

```bash
curl -X POST http://localhost:8000/api/v1/sales/{id}/cancel \
  -H "Authorization: Bearer $TOKEN"
```

| # | Verificacion | Resultado esperado |
|---|-------------|-------------------|
| 1 | Status 200 | status: "cancelled" |
| 2 | Stock revertido | Cantidades restauradas |
| 3 | Credito revertido (si aplica) | Balance restaurado |
| 4 | Cancelar ya cancelada | 400 |

#### T15.11 — Reportes CQRS (ALTA)

| Endpoint | Verificar |
|----------|-----------|
| `/api/v1/sales/reports/daily-summary` | Ventas por dia |
| `/api/v1/sales/reports/product-ranking` | Top productos por revenue |
| `/api/v1/sales/reports/hourly-heatmap` | Ventas por dia/hora |

### Clientes API

#### T15.12 — CRUD clientes API (ALTA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/customers/` | GET | Lista con search, paginacion |
| `/api/v1/customers/{id}` | GET | Por ID |
| `/api/v1/customers/{id}/sales` | GET | Historial ventas (limit) |
| `/api/v1/customers/{id}/credit` | GET | Credito disponible |
| `/api/v1/customers/` | POST | Crear |
| `/api/v1/customers/{id}` | PUT | Actualizar (credit_limit requiere manager+) |
| `/api/v1/customers/{id}` | DELETE | Soft delete (manager+) |

### Inventario API

#### T15.13 — Inventario API (ALTA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/inventory/movements` | GET | Lista con filtros product_id, movement_type |
| `/api/v1/inventory/alerts` | GET | Productos bajo min_stock |
| `/api/v1/inventory/adjust` | POST | Ajuste + audit trail (manager+) |

### Turnos API

#### T15.14 — Turnos API (ALTA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/turns/open` | POST | Abrir (previene duplicados) |
| `/api/v1/turns/{id}/close` | POST | Cierra con denominaciones |
| `/api/v1/turns/current` | GET | Turno actual |
| `/api/v1/turns/{id}` | GET | Detalle (RBAC: propio o manager+) |
| `/api/v1/turns/{id}/summary` | GET | Resumen con ventas por metodo |
| `/api/v1/turns/{id}/movements` | POST | Mov. efectivo (PIN si no manager) |

### Sync API

#### T15.15 — Sincronizacion API (ALTA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/sync/products` | GET | Pull cursor-based (after_id) |
| `/api/v1/sync/customers` | GET | Pull cursor-based |
| `/api/v1/sync/sales` | GET | Pull con since (datetime) |
| `/api/v1/sync/shifts` | GET | Solo turnos abiertos |
| `/api/v1/sync/status` | GET | Health: database connected |
| `/api/v1/sync/{table}` | POST | Bulk upsert (manager+) |

### Dashboard API

#### T15.16 — Dashboard endpoints (ALTA)

| Endpoint | Verificar |
|----------|-----------|
| `/api/v1/dashboard/quick` | ventas_hoy, total_hoy, mermas_pendientes |
| `/api/v1/dashboard/resico` | Serie A/B, limite RESICO, status |
| `/api/v1/dashboard/expenses` | month, year |
| `/api/v1/dashboard/wealth` | utilidad, disponible_retiro (manager+) |
| `/api/v1/dashboard/ai` | Alertas stock, top products, anomalias |
| `/api/v1/dashboard/executive` | KPIs, hourly_sales, top_products (manager+) |

### Mermas y Gastos API

#### T15.17 — Mermas API (ALTA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/mermas/pending` | GET | Lista pendientes (manager+) |
| `/api/v1/mermas/approve` | POST | Aprueba/rechaza + ajuste stock |

#### T15.18 — Gastos API (ALTA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/expenses/summary` | GET | month, year |
| `/api/v1/expenses/` | POST | Registrar (manager+) |

### Remote API

#### T15.19 — Control remoto (MEDIA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/remote/open-drawer` | POST | Abre cajon (manager+) |
| `/api/v1/remote/turn-status` | GET | Estado turno actual |
| `/api/v1/remote/live-sales` | GET | Ventas recientes (limit) |
| `/api/v1/remote/notification` | POST | Enviar notificacion (manager+) |
| `/api/v1/remote/notifications/pending` | GET | Fetch + mark sent |
| `/api/v1/remote/change-price` | POST | Cambio precio remoto + audit |
| `/api/v1/remote/system-status` | GET | Resumen estado general |

### SAT API

#### T15.20 — Catalogo SAT (MEDIA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/sat/search?q=refresco` | GET | Resultados con code + description |
| `/api/v1/sat/search?q=x` | GET | Error (min 2 chars) |
| `/api/v1/sat/{code}` | GET | Info codigo (404 si no existe) |

### Fiscal API

#### T15.21 — Fiscal endpoints (MEDIA)

| Endpoint | Metodo | Verificar |
|----------|--------|-----------|
| `/api/v1/fiscal/generate` | POST | Genera CFDI |
| `/api/v1/fiscal/global/generate` | POST | CFDI global (daily/weekly/monthly) |
| `/api/v1/fiscal/dashboard` | GET | Metricas fiscales |
| `/api/v1/fiscal/noise/start-daily` | POST | Inicia generador ruido |
| `/api/v1/fiscal/noise/stats` | GET | Estadisticas ruido |
| `/api/v1/fiscal/discrepancy/expense` | POST | Gasto discrepancia |
| `/api/v1/fiscal/discrepancy/analysis` | GET | Analisis year/month |
| `/api/v1/fiscal/wealth/dashboard` | GET | Dashboard riqueza |
| `/api/v1/fiscal/wealth/summary` | GET | Resumen riqueza |
| `/api/v1/fiscal/cash/extraction` | POST | Extraccion efectivo |
| `/api/v1/fiscal/cash/balance` | GET | Balance caja |
| `/api/v1/fiscal/returns/process` | POST | Procesar devolucion |
| `/api/v1/fiscal/returns/summary` | GET | Resumen devoluciones |
| `/api/v1/fiscal/variance/calculate-loss` | POST | Calculo perdida |
| `/api/v1/fiscal/variance/optimal-date` | GET | Fecha optima |
| `/api/v1/fiscal/merge/purchase` | POST | Registrar compra |
| `/api/v1/fiscal/merge/product/{id}` | GET | Vista costo dual |
| `/api/v1/fiscal/merge/global-report` | GET | Reporte global costos |
| `/api/v1/fiscal/xml/parse` | POST | Parse XML CFDI (multipart) |

---

## 16. Seguridad y RBAC

#### T16.01 — Endpoints sin token (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | GET /api/v1/products/ sin Authorization | 401 |
| 2 | POST /api/v1/sales/ sin Authorization | 401 |
| 3 | GET /health sin Authorization | 200 (no requiere auth) |

#### T16.02 — Token expirado (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Usar token expirado | 401 en todos los endpoints |

#### T16.03 — RBAC por rol (CRITICA)

| Operacion | admin/manager | cajero/vendedor |
|-----------|---------------|-----------------|
| Crear producto | 200 | 403 |
| Cambiar precio | 200 | 403 |
| Eliminar producto | 200 | 403 |
| Aprobar merma | 200 | 403 |
| Registrar gasto | 200 | 403 |
| Cerrar turno ajeno | 200 | 403 |
| Ver ventas | 200 | 200 |
| Crear venta | 200 | 200 |

#### T16.04 — Rate limiting (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | 6 POST /api/v1/auth/login en 1 min | 429 en el 6to |
| 2 | Esperar 1 minuto | Funciona de nuevo |

#### T16.05 — CORS (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Request desde origen permitido | Headers CORS presentes |
| 2 | Request desde origen no permitido | Sin headers CORS / bloqueado |

#### T16.06 — Inyeccion SQL (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | search=`'; DROP TABLE products; --` | Sin efecto (parametrizado) |
| 2 | name=`<script>alert(1)</script>` | Se guarda como texto plano |

---

## 17. Concurrencia y Casos Borde

#### T17.01 — Venta concurrente mismo producto (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Producto con stock=1 | |
| 2 | 2 ventas simultaneas de qty=1 | Solo 1 exitosa, otra error stock |
| 3 | Stock final | 0 (no negativo) |

#### T17.02 — Folio atomico (CRITICA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | 10 ventas simultaneas | 10 folios unicos consecutivos |
| 2 | Sin gaps ni duplicados | |

#### T17.03 — Turno concurrente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | 2 intentos de abrir turno simultaneos | Solo 1 exitoso |

#### T17.04 — Ajuste stock concurrente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | 2 ajustes simultaneos al mismo producto | Ambos se serializan (FOR UPDATE) |
| 2 | Stock final correcto | Suma de ambos ajustes |

#### T17.05 — Credito concurrente (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Cliente con credito=$100 disponible | |
| 2 | 2 ventas credito de $80 simultaneas | Solo 1 exitosa |

#### T17.06 — Valores extremos (MEDIA)

| # | Campo | Valor | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Precio | 0.01 | Aceptado |
| 2 | Precio | 999999.99 | Aceptado |
| 3 | Cantidad | 0.001 (granel) | Depende de sale_type |
| 4 | Nombre producto | 255 chars | Aceptado |
| 5 | SKU | string muy largo | Depende de validacion |
| 6 | Busqueda | string de 500 chars | No crash |

#### T17.07 — Caracteres especiales (MEDIA)

| # | Campo | Valor | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Nombre producto | "Jabon 'El Bueno' & CIA" | Se guarda correctamente |
| 2 | Nombre cliente | "Maria Jose O'Brien" | Se guarda correctamente |
| 3 | Notas | Emojis, acentos, ñ | Se guarda correctamente |

#### T17.08 — Red intermitente (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Desconectar red durante venta | Error manejado, no crash |
| 2 | Reconectar | App recupera funcionalidad |

---

## 18. Inputs Inesperados y Monkey Testing

Pruebas de robustez: que pasa cuando el usuario hace cosas que "no deberia hacer".

### Emojis en Campos de Texto

#### T18.01 — Emojis en todos los campos de texto (ALTA)

| # | Campo | Input | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Nombre cliente | "Juan 😎 Perez 🇲🇽" | Se guarda y muestra correctamente |
| 2 | Nombre producto | "Coca 🥤 Cola" | Se guarda y muestra correctamente |
| 3 | SKU producto | "🔥SKU001" | Se guarda O error de validacion claro |
| 4 | Notas turno | "Turno tranquilo 😊👍🎉" | Se guarda correctamente |
| 5 | Descripcion gasto | "Agua 💧 para la tienda" | Se guarda correctamente |
| 6 | Razon gasto | "Porque si 🤷" | Se guarda correctamente |
| 7 | Notas merma | "Se rompio 💔" | Se guarda correctamente |
| 8 | Busqueda producto | "🔍" | No crash, cero resultados |
| 9 | Busqueda cliente | "😎" | No crash, cero resultados |
| 10 | Campo usuario login | "admin👑" | Error de login (no crash) |
| 11 | Campo password | "pass🔐word" | Error de login (no crash) |
| 12 | Nombre perfil config | "Caja 1 🖥️" | Se guarda correctamente |
| 13 | Cliente en venta | "Doña Maria 👵" | Se guarda con la venta |

**Clave:** Ninguno debe causar crash, error 500, o corrupcion de datos. Se acepta o se rechaza con mensaje claro.

### Caracteres Especiales y Unicode

#### T18.02 — Caracteres especiales (ALTA)

| # | Campo | Input | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Nombre | "O'Brien & Co." | Apostrofe y ampersand guardados |
| 2 | Nombre | 'Maria "La Chida"' | Comillas dobles guardadas |
| 3 | Nombre | "Café Ñoño Güerita" | Acentos y ñ correctos |
| 4 | SKU | "PROD/001" | Slash aceptado o error claro |
| 5 | SKU | "PROD\001" | Backslash aceptado o error claro |
| 6 | Notas | "Linea 1\nLinea 2" | Salto de linea manejado |
| 7 | Busqueda | "\t\n\r" | No crash, limpia whitespace |
| 8 | Cualquier campo | "NULL" (texto) | Se guarda como texto, NO como null |
| 9 | Cualquier campo | "undefined" (texto) | Se guarda como texto |
| 10 | Cualquier campo | "true" / "false" | Se guarda como texto, no como boolean |

#### T18.03 — Inyeccion en campos (CRITICA)

| # | Campo | Input | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Nombre producto | `<script>alert('XSS')</script>` | Se guarda como texto plano, NO ejecuta |
| 2 | Busqueda | `'; DROP TABLE products; --` | Cero efecto, query parametrizado |
| 3 | Busqueda | `" OR 1=1 --` | Cero efecto |
| 4 | Nombre | `{{7*7}}` | Se guarda "{{7*7}}", no "49" |
| 5 | URL config | `javascript:alert(1)` | No ejecuta |
| 6 | Cualquier campo | `<img onerror=alert(1) src=x>` | Se guarda como texto plano |

### Numeros Invalidos

#### T18.04 — Campos numericos con inputs raros (ALTA)

| # | Campo | Input | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Precio | "abc" | No permite (input type=number) |
| 2 | Precio | "-50" | Rechazado (min: 0) o error claro |
| 3 | Precio | "0" | Rechazado o advertencia |
| 4 | Precio | "9999999999" | Aceptado o limite maximo |
| 5 | Precio | "18.999999999" | Redondea a 2 decimales |
| 6 | Precio | "1e10" (notacion cientifica) | Rechazado o convertido correctamente |
| 7 | Cantidad | "0.5" (para unidad) | Depende de sale_type (unit vs granel) |
| 8 | Cantidad | "-1" | Rechazado |
| 9 | Cantidad | "99999" | Aceptado pero verificar stock |
| 10 | Monto gasto | "0.001" | Rechazado (min: 0.01) |
| 11 | Monto gasto | "999999999" | Aceptado o limite |
| 12 | Efectivo inicial turno | "-100" | Rechazado |
| 13 | Terminal ID | "0" | Rechazado (min: 1) |
| 14 | Terminal ID | "1.5" | Redondea o rechaza (debe ser entero) |
| 15 | Cantidad inventario | "0" | Rechazado (min: 1) |

#### T18.05 — NaN e Infinity via API directa (CRITICA)

```bash
# Enviar NaN en precio
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"product_id":1,"qty":"NaN","price":18.5}],"payment_method":"cash","serie":"A"}'

# Enviar Infinity
curl -X POST http://localhost:8000/api/v1/sales/ \
  -d '{"items":[{"product_id":1,"qty":1,"price":"Infinity"}],"payment_method":"cash","serie":"A"}'
```

| # | Input | Resultado esperado |
|---|-------|-------------------|
| 1 | qty: NaN | 400 Bad Request |
| 2 | price: Infinity | 400 Bad Request |
| 3 | discount: -Infinity | 400 Bad Request |
| 4 | qty: null | 400 o 422 Validation Error |

### Strings Extremos

#### T18.06 — Longitud de strings (ALTA)

| # | Campo | Input | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Nombre producto | 1 caracter: "A" | Aceptado |
| 2 | Nombre producto | 255 caracteres | Aceptado |
| 3 | Nombre producto | 1000 caracteres | Truncado o error claro |
| 4 | Nombre producto | 10,000 caracteres | Error claro, no crash |
| 5 | SKU | "" (vacio) | Rechazado |
| 6 | SKU | "A" (1 char) | Aceptado |
| 7 | Busqueda | "" (vacio) | Muestra todos o nada |
| 8 | Busqueda | 1000 caracteres | No crash, no timeout |
| 9 | Notas | 10,000 caracteres | Aceptado o truncado |
| 10 | Email cliente | "a@b" (minimo) | Aceptado o validacion |
| 11 | Email cliente | "no-es-email" | Aceptado (opcional) o validacion |
| 12 | Telefono | "999" (3 digitos) | Aceptado |
| 13 | Telefono | "+52 999 123 4567" | Aceptado |
| 14 | Telefono | "no-es-telefono" | Aceptado (es texto libre) |

#### T18.07 — Espacios en blanco (MEDIA)

| # | Campo | Input | Resultado esperado |
|---|-------|-------|-------------------|
| 1 | Nombre | "   " (solo espacios) | Rechazado (trim → vacio) |
| 2 | Nombre | "  Juan  Perez  " | Se guarda trimmed: "Juan  Perez" |
| 3 | SKU | " PROD001 " | Se guarda trimmed o rechazado |
| 4 | Busqueda | "   coca   " | Busca "coca" (trimmed) |

### Archivos y Uploads

#### T18.08 — Subir archivos al endpoint fiscal XML (ALTA)

```bash
# Archivo PDF (no es XML)
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@documento.pdf"

# Archivo MP3
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@cancion.mp3"

# Archivo CSV
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@datos.csv"

# Archivo ejecutable
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@virus.exe"

# Archivo vacio
touch vacio.xml
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@vacio.xml"

# Archivo enorme (>10MB)
dd if=/dev/urandom of=grande.xml bs=1M count=20
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@grande.xml"

# XML malformado
echo "<cfdi><roto" > malo.xml
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@malo.xml"

# Archivo con extension falsa (.xml pero es JPG)
cp foto.jpg falso.xml
curl -X POST http://localhost:8000/api/v1/fiscal/xml/parse \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@falso.xml"
```

| # | Archivo | Resultado esperado |
|---|---------|-------------------|
| 1 | PDF | Error claro: "Solo se aceptan archivos XML" |
| 2 | MP3 | Error claro: tipo no soportado |
| 3 | CSV | Error claro: tipo no soportado |
| 4 | EXE | Error claro: tipo no soportado |
| 5 | XML vacio | Error: archivo vacio o XML invalido |
| 6 | XML >10MB | Error: archivo demasiado grande |
| 7 | XML malformado | Error: XML no se puede parsear |
| 8 | JPG renombrado a .xml | Error: contenido no es XML valido |
| 9 | Sin archivo | Error: archivo requerido |

**Clave:** Ningun archivo debe causar crash, error 500 no manejado, ni escritura al filesystem.

### Acciones Rapidas y Doble Click

#### T18.09 — Doble envio / spam de clicks (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Doble clic rapido en COBRAR | Solo 1 venta creada |
| 2 | Doble clic en Guardar cliente | Solo 1 cliente creado |
| 3 | Doble clic en Guardar producto | Solo 1 producto (o error SKU duplicado) |
| 4 | Doble clic en Aplicar inventario | Solo 1 movimiento |
| 5 | Doble clic en Abrir turno | Solo 1 turno |
| 6 | Doble clic en Registrar gasto | Solo 1 gasto |
| 7 | Doble clic en Aprobar merma | Solo 1 aprobacion |
| 8 | 10 clicks rapidos en Cargar | No crash, no requests duplicados |

#### T18.10 — Navegacion rapida (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | F1 F2 F3 F4 F5 rapido | No crash, ultima pestaña queda |
| 2 | Click rapido entre pestanas | No memory leak, no requests huerfanos |
| 3 | F12 (Cobrar) sin estar en Terminal | No efecto o navega primero |

### Datos Vacios y Nulos

#### T18.11 — Pantallas sin datos (ALTA)

| # | Pantalla | Estado | Resultado esperado |
|---|----------|--------|--------------------|
| 1 | Terminal | 0 productos en DB | Busqueda no encuentra nada, no crash |
| 2 | Clientes | 0 clientes | "Sin clientes. Haz clic en Cargar." |
| 3 | Productos | 0 productos | "Sin productos. Haz clic en Cargar." |
| 4 | Inventario | 0 productos | Tabla vacia |
| 5 | Turnos | 0 turnos historicos | Tabla vacia |
| 6 | Reportes | 0 ventas en periodo | KPIs en 0, "Sin datos." |
| 7 | Historial | 0 ventas | "Sin ventas para los filtros seleccionados." |
| 8 | Dashboard | 0 ventas hoy | Ventas: 0, Ingreso: $0.00 |
| 9 | Mermas | 0 mermas | "Sin mermas pendientes" con icono |
| 10 | Gastos | 0 gastos | $0.00 este mes, $0.00 este año |

### Formatos de Fecha

#### T18.12 — Fechas en filtros (MEDIA)

| # | Campo fecha | Input | Resultado esperado |
|---|------------|-------|-------------------|
| 1 | Fecha desde > fecha hasta | | No permite o error claro |
| 2 | Fecha futura (2030) | | Aceptada, 0 resultados |
| 3 | Fecha muy antigua (2000) | | Aceptada, 0 resultados |
| 4 | Fecha invalida via API | "2025-13-45" | Error validacion |
| 5 | Fecha con timezone | "2025-01-01T00:00:00-06:00" | Manejada correctamente |

### Navegador y Red

#### T18.13 — Comportamiento offline (ALTA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Desconectar red → intentar vender | Error manejado, no crash |
| 2 | Desconectar → cargar productos | Error manejado |
| 3 | Desconectar → login | Error de conexion claro |
| 4 | Reconectar → reintentar | Funciona normalmente |

#### T18.14 — Multiples pestanas navegador (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | Abrir 2 pestanas del POS | Ambas funcionan |
| 2 | Vender en pestana 1 | Stock se refleja en pestana 2 al recargar |
| 3 | Login en pestana 1, logout en pestana 2 | Pestana 1 pierde sesion correctamente |

#### T18.15 — Refresh de pagina (MEDIA)

| # | Accion | Resultado esperado |
|---|--------|--------------------|
| 1 | F5 en medio de edicion | No pierde config basica |
| 2 | F5 con carrito lleno | Comportamiento definido (pierde o mantiene) |
| 3 | F5 en pagina de login | Sigue en login |

### Payloads API Malformados

#### T18.16 — Requests mal formados (ALTA)

```bash
# Body vacio
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# JSON invalido
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d 'esto no es json'

# Content-Type incorrecto
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/plain" \
  -d '{"items":[]}'

# Array donde se espera objeto
curl -X POST http://localhost:8000/api/v1/sales/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[1,2,3]'

# Campos extra desconocidos
curl -X POST http://localhost:8000/api/v1/customers/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","campo_falso":"valor","hack":true}'

# IDs negativos
curl http://localhost:8000/api/v1/products/-1 \
  -H "Authorization: Bearer $TOKEN"

# IDs string donde se espera int
curl http://localhost:8000/api/v1/products/abc \
  -H "Authorization: Bearer $TOKEN"

# IDs extremos
curl http://localhost:8000/api/v1/products/99999999999 \
  -H "Authorization: Bearer $TOKEN"
```

| # | Request | Resultado esperado |
|---|---------|-------------------|
| 1 | Body vacio | 422 Validation Error |
| 2 | JSON invalido | 422 o 400 |
| 3 | Content-Type incorrecto | 422 o 415 |
| 4 | Array en vez de objeto | 422 |
| 5 | Campos extra | Ignorados (no crash) |
| 6 | ID negativo | 404 o 422 |
| 7 | ID string | 422 |
| 8 | ID enorme | 404 |

**Clave:** Ningun payload debe causar 500 Internal Server Error.

### Resumen Monkey Testing

| Categoria | Pruebas | Prioridad |
|-----------|---------|-----------|
| Emojis en campos | T18.01 (13 inputs) | ALTA |
| Caracteres especiales | T18.02 (10 inputs) | ALTA |
| Inyeccion XSS/SQL | T18.03 (6 inputs) | CRITICA |
| Numeros invalidos | T18.04 (15 inputs) | ALTA |
| NaN/Infinity API | T18.05 (4 inputs) | CRITICA |
| Strings extremos | T18.06 (14 inputs) | ALTA |
| Espacios en blanco | T18.07 (4 inputs) | MEDIA |
| Archivos upload | T18.08 (9 tests) | ALTA |
| Doble envio | T18.09 (8 tests) | ALTA |
| Navegacion rapida | T18.10 (3 tests) | MEDIA |
| Pantallas sin datos | T18.11 (10 tests) | ALTA |
| Fechas invalidas | T18.12 (5 tests) | MEDIA |
| Offline/red | T18.13 (4 tests) | ALTA |
| Multiples pestanas | T18.14 (3 tests) | MEDIA |
| Refresh pagina | T18.15 (3 tests) | MEDIA |
| Payloads malformados | T18.16 (8 tests) | ALTA |
| **TOTAL** | **119 inputs/tests** | |

---

## 19. Registro de Resultados

### Resumen por Modulo

| Modulo | Total Pruebas | CRITICA | ALTA | MEDIA | BAJA |
|--------|--------------|---------|------|-------|------|
| Instalador | 14 | 5 | 5 | 3 | 1 |
| Login | 6 | 2 | 2 | 0 | 2 |
| Terminal | 36 | 12 | 14 | 8 | 2 |
| Clientes | 14 | 3 | 7 | 4 | 0 |
| Productos | 9 | 3 | 4 | 0 | 0 |
| Inventario | 8 | 2 | 3 | 3 | 0 |
| Turnos | 13 | 3 | 6 | 3 | 1 |
| Reportes | 7 | 1 | 5 | 1 | 0 |
| Historial | 10 | 2 | 6 | 2 | 0 |
| Configuraciones | 7 | 1 | 3 | 1 | 2 |
| Dashboard | 5 | 1 | 1 | 2 | 1 |
| Mermas | 7 | 2 | 2 | 3 | 0 |
| Gastos | 6 | 1 | 2 | 3 | 0 |
| Navegacion | 5 | 2 | 1 | 1 | 1 |
| API Backend | 21 | 3 | 14 | 4 | 0 |
| Seguridad | 6 | 3 | 2 | 1 | 0 |
| Concurrencia | 8 | 3 | 3 | 2 | 0 |
| Monkey Testing | 16 | 2 | 10 | 4 | 0 |
| **TOTAL** | **198** | **49** | **90** | **45** | **10** |

**Total inputs/escenarios individuales: 301+** (muchas pruebas contienen multiples sub-verificaciones)

### Hoja de Registro

| Fecha | Tester | Modulo | Prueba | Resultado | Notas |
|-------|--------|--------|--------|-----------|-------|
| | | | | PASA/FALLA | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
