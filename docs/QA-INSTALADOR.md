# QA Manual — Instalador TITAN POS

Pruebas manuales para el flujo de instalacion tipo "doble clic".
Archivos bajo prueba: `INSTALAR.desktop`, `instalar.sh`, `setup.sh`.

---

## Requisitos del entorno de prueba

| Requisito | Detalle |
|-----------|---------|
| OS | Ubuntu 22.04+ / Linux Mint / cualquier distro con GNOME o XFCE |
| Docker | Pre-instalado para la mayoria de pruebas; desinstalar para prueba T02 |
| Usuario | Cuenta normal (no root), con sudo disponible |
| Internet | Necesario para descargar imagenes Docker la primera vez |
| Puerto 8000 | Libre (sin otro servicio escuchando) |

---

## Estado limpio (antes de cada prueba)

Para resetear a estado "primera vez", ejecutar desde el directorio del proyecto:

```bash
docker compose down -v 2>/dev/null   # baja contenedores y elimina volumen DB
rm -f .env CREDENCIALES.txt           # elimina config generada
rm -f ~/Escritorio/TITAN-POS.desktop ~/Desktop/TITAN-POS.desktop  # elimina acceso directo
```

---

## T01 — Instalacion limpia (caso feliz)

**Precondicion:** Docker instalado, `.env` NO existe, contenedores abajo.

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Abrir explorador de archivos en la carpeta del proyecto | Se ve el archivo `INSTALAR TITAN POS` con icono de instalador |
| 2 | Doble clic en `INSTALAR TITAN POS` | Se abre una terminal |
| 3 | Observar la terminal | Banner "TITAN POS — INSTALADOR" visible |
| 4 | Esperar Fase 1 | `[■□□□□□] Verificando Docker...` → `✔ Docker y Docker Compose encontrados` |
| 5 | Esperar Fase 2 | `[■■□□□□] Configurando variables...` → `✔ Archivo .env generado` + `✔ Credenciales guardadas` |
| 6 | Esperar Fase 3 | `[■■■□□□] Construyendo contenedores...` → `✔ Contenedores construidos` |
| 7 | Esperar Fase 4 | `[■■■■□□] Iniciando base de datos...` → puntos animados → `✔ Base de datos lista` |
| 8 | Esperar Fase 5 | `[■■■■■□] Iniciando servidor...` → puntos animados → `✔ Servidor listo` |
| 9 | Esperar Fase 6 | `[■■■■■■] Creando acceso directo...` → `✔ Acceso directo creado` |
| 10 | Mensaje final | `✅ ¡INSTALACION COMPLETADA!` visible |
| 11 | Navegador | Se abre automaticamente en `http://localhost:8000` |
| 12 | Terminal | Muestra `Presiona Enter para cerrar...` y espera |

**Verificaciones post-instalacion:**

```bash
# .env generado con secretos unicos (NO dice "change-me")
grep POSTGRES_PASSWORD .env    # debe ser alfanumerico ~24 chars
grep JWT_SECRET .env           # debe ser hex 64 chars
grep ADMIN_API_PASSWORD .env   # debe ser alfanumerico ~16 chars
grep '@postgres:' .env         # DATABASE_URL apunta a hostname Docker, NO a localhost

# Cada secreto es diferente
# (POSTGRES_PASSWORD != JWT_SECRET != ADMIN_API_PASSWORD)

# CREDENCIALES.txt existe y tiene los mismos valores que .env
cat CREDENCIALES.txt

# Contenedores corriendo
docker compose ps              # postgres y api en estado "Up"

# Health check responde
curl -s http://localhost:8000/health

# Acceso directo existe en el escritorio
ls -la ~/Escritorio/TITAN-POS.desktop 2>/dev/null || ls -la ~/Desktop/TITAN-POS.desktop
```

**Resultado:** PASA / FALLA

---

## T02 — Sin Docker instalado

**Precondicion:** Docker NO instalado (`sudo apt remove docker.io` o probar en VM limpia).

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Ejecutar `bash setup.sh` | Fase 1: `⚠ Docker no encontrado. Intentando instalar...` |
| 2a | Si tiene sudo + internet | `✔ Docker instalado correctamente` + advertencia de cerrar sesion |
| 2b | Si no puede instalar | `✖ No se pudo instalar Docker automaticamente` |
| 3 | (caso 2b) | Muestra instrucciones: `sudo apt install docker.io docker-compose-v2` |
| 4 | (caso 2b) | `ERROR: Docker es necesario para TITAN POS` y sale |

**Verificar:** El script NO queda colgado. Termina con mensaje claro.

**Resultado:** PASA / FALLA

---

## T03 — Re-ejecucion (idempotencia)

**Precondicion:** T01 completado exitosamente. `.env` y contenedores existen.

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Anotar passwords actuales | `grep POSTGRES_PASSWORD .env` → anotar valor |
| 2 | Ejecutar `bash setup.sh` otra vez | Fase 1: Docker OK |
| 3 | Observar Fase 2 | `✔ Archivo .env ya existe (no se modifica)` |
| 4 | | NO aparece "Credenciales guardadas" |
| 5 | Esperar finalizacion | Completa las 6 fases sin error |
| 6 | Comparar passwords | `grep POSTGRES_PASSWORD .env` → **mismo valor** que paso 1 |
| 7 | Servicios | `docker compose ps` → postgres y api corriendo |

**Clave:** Los secretos NO se regeneraron. La DB no se borro.

**Resultado:** PASA / FALLA

---

## T04 — Re-ejecucion con contenedores caidos

**Precondicion:** `.env` existe pero contenedores abajo (`docker compose down`).

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `docker compose down` | Contenedores abajo |
| 2 | `bash setup.sh` | Fase 2: `.env ya existe` (no regenera) |
| 3 | | Fases 3-5: reconstruye y levanta contenedores |
| 4 | | Fase 6: re-crea acceso directo |
| 5 | Verificar | `curl -s http://localhost:8000/health` responde OK |

**Resultado:** PASA / FALLA

---

## T05 — Falta .env.example

**Precondicion:** Renombrar `.env.example` temporalmente, `.env` NO existe.

```bash
mv .env.example .env.example.bak
rm -f .env
```

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `bash setup.sh` | Fase 1: Docker OK |
| 2 | | Fase 2: `ERROR: No se encontro .env.example — ¿la descarga esta completa?` |
| 3 | | Script termina con codigo de error |

**Restaurar despues:** `mv .env.example.bak .env.example`

**Resultado:** PASA / FALLA

---

## T06 — Puerto 8000 ocupado

**Precondicion:** Otro proceso escuchando en puerto 8000.

```bash
# Simular con netcat
python3 -m http.server 8000 &
PID=$!
```

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `bash setup.sh` | Fase 3-4 deberian funcionar (Docker usa puertos internos) |
| 2 | Fase 5 | `docker compose up -d api` puede fallar por conflicto de puerto |
| 3 | | Script muestra error o el health check falla con timeout |

**Limpiar:** `kill $PID`

**Nota:** Este escenario puede variar. Documentar el comportamiento observado.

**Resultado:** PASA / FALLA — Comportamiento observado: ___________________

---

## T07 — Acceso directo en escritorio

**Precondicion:** T01 completado. Servicios corriendo.

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Ir al escritorio | Se ve icono "TITAN POS" |
| 2 | Doble clic en "TITAN POS" | Se abre el navegador |
| 3 | | Carga `http://localhost:8000` |
| 4 | | La aplicacion responde (no error de conexion) |

**Si usa GNOME y pide "confiar en el archivo":**

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Click derecho → Propiedades → Permisos | "Permitir ejecutar como programa" marcado |
| 2 | Doble clic | NO debe pedir confirmacion (gio set trusted) |

**Resultado:** PASA / FALLA

---

## T08 — Directorio escritorio en espanol

**Precondicion:** Sistema en espanol (carpeta `~/Escritorio`).

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `bash setup.sh` | Completa sin error |
| 2 | Verificar | `ls ~/Escritorio/TITAN-POS.desktop` → existe |
| 3 | | NO se creo en `~/Desktop` |

**Resultado:** PASA / FALLA

---

## T09 — Directorio escritorio en ingles

**Precondicion:** Sistema en ingles (carpeta `~/Desktop`, NO existe `~/Escritorio`).

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `bash setup.sh` | Completa sin error |
| 2 | Verificar | `ls ~/Desktop/TITAN-POS.desktop` → existe |

**Resultado:** PASA / FALLA

---

## T10 — Ruta del proyecto con espacios

**Precondicion:** El proyecto esta en una ruta con espacios (ej: `/home/user/PUNTO DE VENTA/`).

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Doble clic en `INSTALAR TITAN POS` | Se abre terminal |
| 2 | | Script NO falla por espacios en la ruta |
| 3 | | Todas las fases completan correctamente |
| 4 | Verificar | `.env` se creo en la ruta correcta (con espacios) |

**Resultado:** PASA / FALLA

---

## T11 — Ruta del proyecto movida (USB)

**Precondicion:** Copiar toda la carpeta a otra ubicacion (simular USB).

```bash
cp -r "/home/user/PUNTO DE VENTA" /tmp/titan-usb-test
```

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | Ir a `/tmp/titan-usb-test` en explorador de archivos | Se ve `INSTALAR TITAN POS` |
| 2 | Doble clic | Terminal se abre |
| 3 | | El script trabaja sobre `/tmp/titan-usb-test`, NO sobre la ubicacion original |
| 4 | Verificar | `ls /tmp/titan-usb-test/.env` → existe ahi |

**Limpiar:** `rm -rf /tmp/titan-usb-test`

**Resultado:** PASA / FALLA

---

## T12 — Seguridad de secretos

**Precondicion:** T01 completado.

| # | Verificacion | Comando | Esperado |
|---|-------------|---------|----------|
| 1 | CREDENCIALES.txt no esta en git | `git status --short CREDENCIALES.txt` | No aparece (esta en .gitignore) |
| 2 | .env no esta en git | `git status --short .env` | No aparece (esta en .gitignore) |
| 3 | Secretos son aleatorios | Comparar POSTGRES_PASSWORD entre 2 instalaciones distintas | Valores diferentes |
| 4 | No contienen chars problematicos | `grep -E '[/+=]' .env \| grep -v DATABASE_URL \| grep -v CORS` | Sin resultados (passwords no tienen `/+=`) |
| 5 | DATABASE_URL apunta a Docker | `grep DATABASE_URL .env` | Contiene `@postgres:5432` (NO `@localhost`) |
| 6 | JWT_SECRET es hex 64 chars | `grep JWT_SECRET .env \| cut -d= -f2 \| wc -c` | 65 (64 + newline) |

**Resultado:** PASA / FALLA

---

## T13 — make setup

**Precondicion:** Estado limpio.

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `make setup` | Ejecuta `bash setup.sh` |
| 2 | | Comportamiento identico a T01 |

**Resultado:** PASA / FALLA

---

## T14 — Ejecucion desde terminal (sin .desktop)

**Precondicion:** Estado limpio.

| Paso | Accion | Resultado esperado |
|------|--------|--------------------|
| 1 | `cd` al directorio del proyecto | |
| 2 | `bash setup.sh` | Identico a T01 |
| 3 | Alternativa: `./setup.sh` | Identico a T01 (tiene shebang + chmod +x) |

**Resultado:** PASA / FALLA

---

## Matriz de cobertura

| Escenario | Prueba | Prioridad |
|-----------|--------|-----------|
| Instalacion desde cero | T01 | CRITICA |
| Docker no instalado | T02 | ALTA |
| Re-ejecucion sin romper nada | T03 | CRITICA |
| Contenedores caidos | T04 | ALTA |
| Archivo faltante | T05 | MEDIA |
| Puerto ocupado | T06 | MEDIA |
| Acceso directo funciona | T07 | CRITICA |
| Escritorio espanol | T08 | ALTA |
| Escritorio ingles | T09 | ALTA |
| Ruta con espacios | T10 | CRITICA |
| Proyecto copiado/USB | T11 | ALTA |
| Secretos seguros | T12 | CRITICA |
| make setup | T13 | BAJA |
| Ejecucion desde terminal | T14 | BAJA |

---

## Registro de resultados

| Fecha | Tester | OS/Distro | T01 | T02 | T03 | T04 | T05 | T06 | T07 | T08 | T09 | T10 | T11 | T12 | T13 | T14 | Notas |
|-------|--------|-----------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-------|
| | | | | | | | | | | | | | | | | |
| | | | | | | | | | | | | | | | | |
| | | | | | | | | | | | | | | | | |
