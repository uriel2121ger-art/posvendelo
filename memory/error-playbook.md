# Error Playbook — POSVENDELO

Errores y bugs encontrados en auditorías, con causa raíz, solución y lección. Consultar antes de investigar un error nuevo.

Formato por entrada: ID, Síntoma, Causa raíz, Solución, Resultado, Lección.

---

## ERR-001 — Respuesta JSON con float para montos en resumen de turno remoto

- **Síntoma:** El endpoint remoto de estado de turno (`/turn-status` o equivalente) devolvía `0.0` (float) para `cash_sales`, `card_sales`, `transfer_sales`, `total_sales` cuando no había resumen, en lugar de string decimal.
- **Causa raíz:** En `backend/modules/remote/routes.py` se usaba `0.0` como fallback cuando `summary` era falsy. El contrato del proyecto exige que los montos en JSON sean `money()` (string) o Decimal en lógica; nunca float en respuestas API.
- **Solución:** Sustituir `0.0` por `money(Decimal("0"))` en las cuatro claves del payload de respuesta (cash_sales, card_sales, transfer_sales, total_sales). El módulo ya importaba `Decimal` y `money`.
- **Resultado:** Las respuestas de resumen de turno remoto devuelven siempre string decimal para montos (p. ej. `"0.00"`), consistente con el resto de la API.
- **Lección:** En respuestas API, montos deben ser `money(Decimal(...))` o `"0.00"`; no usar `0.0` (float). Regla: dinero en JSON como string; en aritmética usar `dec()`.

---

## ERR-002 — Emoji en UI (modal “Operación exitosa” movimiento de caja)

- **Síntoma:** En el modal de éxito de entrada/retiro de efectivo (movimiento de caja) se mostraba el carácter Unicode ✅ (`&#9989;`). La convención del proyecto es no usar emojis en la UI.
- **Causa raíz:** En `frontend/src/renderer/src/App.tsx` (CashMovementModal) se usaba `<div className="text-5xl mb-4">&#9989;</div>` para el ícono de éxito.
- **Solución:** Importar `Check` de `lucide-react` y reemplazar el div con el emoji por `<Check className="h-14 w-14 text-emerald-400" strokeWidth={2.5} aria-hidden />` dentro de un contenedor flex centrado, manteniendo el mismo mensaje “Operación exitosa”.
- **Resultado:** El modal muestra un ícono de check de Lucide en lugar del emoji; se cumple la convención “sin emojis en UI”.
- **Lección:** No usar emojis ni caracteres Unicode decorativos en la UI; usar íconos de la librería del proyecto (Lucide React).

---

---

## ERR-003 — Instalación nueva: evitar ejecutar 48 migraciones (pre-producción)

- **Síntoma:** En una DB vacía, el entrypoint aplica `schema.sql` (esquema completo) y luego `migrate.py` ejecuta los 48 archivos de migración uno a uno; es redundante y más lento.
- **Causa raíz:** No se marcaban como aplicadas las versiones 1..N en `schema_version` tras aplicar `schema.sql`, por lo que `migrate.py` consideraba todas pendientes.
- **Solución:** En `backend/entrypoint.sh`, justo después de aplicar `schema.sql` en una DB recién detectada como vacía, ejecutar un script que obtiene el máximo número de migración existente en `migrations/*.sql` e inserta en `schema_version` las versiones 1..N con `ON CONFLICT (version) DO NOTHING`. Así `migrate.py` no tiene nada pendiente en instalación nueva.
- **Resultado:** Instalación nueva = una sola aplicación de `schema.sql` + inserción de versiones 1..N; `migrate.py` termina en segundos sin ejecutar 48 archivos. Las migraciones futuras (049, 050, …) se aplican solo cuando se añadan.
- **Lección:** Antes de producción se puede consolidar el “todo de una vez” para DB nueva usando el schema completo y marcando las migraciones actuales como aplicadas; no hace falta borrar ni archivar los archivos de migración.

---

---

## ERR-004 — Licencia del nodo: "missing", "sin-licencia", "Archivo titan-agent.json no encontrado"

- **Síntoma:** En Ajustes → Licencia del nodo se ve: Plan sin-licencia, Estado missing, Válida/Soporte hasta sin límite, y mensaje "Archivo titan-agent.json no encontrado".
- **Causa raíz:**  
  1. El backend no encuentra el archivo de configuración del agente (donde puede ir la licencia). Por defecto busca `POSVENDELO_AGENT_CONFIG_PATH` o `/runtime/posvendelo-agent.json`. Si no existe, devuelve `effective_status: "missing"` y un mensaje de archivo no encontrado.  
  2. Si el mensaje dice **"titan-agent.json"** (y no "posvendelo-agent.json"), el backend que responde es una **imagen o código antiguo** (titan-pos); en el repo actual el mensaje es "Archivo posvendelo-agent.json no encontrado" (`backend/modules/shared/license_state.py`).
  3. En Docker el backend suele no tener montado `posvendelo-agent.json`; ese archivo lo genera el instalador en el host (Linux: `~/.config/posvendelo/`, Windows: `%LOCALAPPDATA%\POSVENDELO\`). El contenedor no tiene acceso a esa ruta salvo que se monte.
- **Solución:**  
  1. **Actualizar el backend** a la imagen/código actual (posvendelo) para que el mensaje sea el correcto y el comportamiento sea el esperado.  
  2. **Tener el archivo donde el backend lo busque:** o bien montar en el contenedor la ruta del host donde está `posvendelo-agent.json` (ej. volumen a `~/.config/posvendelo/posvendelo-agent.json`) y definir `POSVENDELO_AGENT_CONFIG_PATH` a esa ruta dentro del contenedor, o bien inyectar la licencia vía `POSVENDELO_LICENSE_BLOB` (JSON en env).  
  3. Si no se usa licencia (modo desarrollo/trial): es esperado "missing" y "sin límite"; no bloquea si `POSVENDELO_LICENSE_ENFORCEMENT` no está en true.
- **Resultado:** Mensaje coherente con posvendelo-agent.json; licencia visible en Ajustes si el archivo o el BLOB está configurado; si se ve "titan-agent.json", tras actualizar el backend debería verse "posvendelo-agent.json".
- **Lección:** El estado de licencia lo resuelve el backend desde `license_state.py` (archivo o env); el nombre del archivo en los mensajes debe ser posvendelo-agent.json. Evitar desplegar backend con código/imagen titan-pos si ya se renombró a posvendelo.

**Complemento (instalador nuevo):** El postinst del .deb generaba `posvendelo-agent.json` en `~/.config/posvendelo/` pero el docker-compose del nodo **no** montaba ese archivo en el contenedor del backend, por eso el backend siempre devolvía "no encontrado". Corrección: en `installers/linux/postinst.sh` se añadió (1) volumen `./posvendelo-agent.json:/runtime/posvendelo-agent.json:ro` y `POSVENDELO_AGENT_CONFIG_PATH` en el servicio api, y (2) copia de `~/.config/posvendelo/posvendelo-agent.json` a `$INSTALL_DIR/posvendelo-agent.json` para que el volumen tenga archivo. Con eso, instalaciones nuevas con el .deb dejan el backend viendo el archivo; si aún no hay licencia en el JSON, el estado seguirá "missing" hasta hacer pre-registro/activación.

---

## ERR-005 — Release workflow: Android APK falla con "invalid source release: 21"

- **Síntoma:** En GitHub Actions, el workflow "POSVENDELO — Release Artifacts" (tag v1.0.3) falla en los jobs "Frontend Android — APK cajero" y "Owner App Android — APK" con: `Execution failed for task ':capacitor-android:compileReleaseJavaWithJavac'` → `error: invalid source release: 21`.
- **Causa raíz:** Los proyectos Android (frontend y owner-app) tienen en `capacitor.build.gradle` (o equivalente) `sourceCompatibility`/`targetCompatibility` en Java 21, pero el workflow de release usaba `actions/setup-java` con `java-version: "17"`. El JDK 17 no soporta compilar con source/target 21.
- **Solución:** En `.github/workflows/release.yml`, en los jobs `build-frontend-android` y `build-owner-android`, cambiar `Setup Java 17` por `Setup Java 21` y `java-version: "21"`.
- **Resultado:** Los builds de APK en CI usan JDK 21 y compilan correctamente; el release completo puede completar (salvo otros fallos como upload al control-plane).
- **Lección:** La versión de Java en el workflow debe coincidir con la que exigen los proyectos Android (capacitor.build.gradle); si el proyecto usa VERSION_21, el job debe usar Java 21.

---

*Última actualización: 2026-03-13. Entradas derivadas de auditoría backend, frontend y correcciones aplicadas.*
