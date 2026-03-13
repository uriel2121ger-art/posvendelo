# Flujo de actualización para el cliente

Cómo llegan los fixes (por ejemplo: montar `posvendelo-agent.json` en el backend, nuevo postinst) al cliente y qué tiene que hacer.

---

## 1. Qué publicamos nosotros

| Qué | Dónde | Cuándo |
|-----|-------|--------|
| **Nuevo .deb** (con postinst corregido) | Build desde `frontend` → subir a control-plane/downloads (homelab 192.168.10.90 o posvendelo.com) | Tras hacer los cambios en el repo y construir |
| **Nueva imagen backend** | GHCR `ghcr.io/uriel2121ger-art/posvendelo:latest` | Push a master dispara deploy; o release manual |
| **Metadata de release** | Control-plane: publicar versión para `electron-linux` / `electron-deb` con `target_ref` que apunte al nuevo .deb | Para que la app desktop detecte “hay actualización” |

El fix del postinst (volumen + copia de `posvendelo-agent.json`) **solo llega al nodo cuando el cliente instala una versión nueva del .deb**. La app actualizada sola no cambia el compose del backend; hace falta instalar el paquete.

---

## 2. Cómo llega la actualización al cliente

### Opción A — Manual (recomendado para probar)

1. El cliente entra a la **página de descargas** (por ejemplo `https://posvendelo.com/downloads` o la URL del homelab).
2. Descarga el **nuevo .deb** (ej. `posvendelo_1.0.1_amd64.deb`).
3. En el equipo del nodo ejecuta:
   ```bash
   sudo dpkg -i posvendelo_1.0.1_amd64.deb
   ```
4. El **postinst** del paquete:
   - Regenera `docker-compose.yml` en `/opt/posvendelo` (con el volumen de `posvendelo-agent.json` y `POSVENDELO_AGENT_CONFIG_PATH`).
   - Si existe `~/.config/posvendelo/posvendelo-agent.json`, lo copia a `/opt/posvendelo/posvendelo-agent.json`.
   - Hace `docker compose pull` y `docker compose up -d`.
5. El backend reinicia con el nuevo compose y ya ve el archivo de agente (y la licencia del nodo puede mostrarse bien).

**Resumen:** el cliente descarga el .deb nuevo e instala con `dpkg -i`; no tiene que editar nada a mano.

El **registro para monitoreo** (vincular la sucursal con una cuenta para verla desde la app del dueño) puede hacerse desde el wizard inicial (paso 2) o más tarde desde **Configuración** → Nube PosVendelo → "Registro para monitoreo".

### Opción B — Desde la app (sin comandos ni terminal)

Para usuarios que no usan terminal ni comandos: abrir la app PosVendelo → **Configuración** → sección **Actualizaciones**. Activar **"Buscar actualizaciones automáticamente"** y pulsar **"Comprobar ahora"**. Si hay actualización, pulsar **"Descargar actualización"** y luego **"Instalar ahora"**; en Linux se abre el instalador del sistema (Centro de software, etc.) y el usuario solo confirma. No hace falta escribir comandos.

### Opción C — Auto-update (app desktop)

1. La app desktop tiene **posvendelo-agent.json** con `controlPlaneUrl` (y opcionalmente `install_token` o `branchId`).
2. El agente local hace **poll** al control-plane (`GET .../releases/manifest`) cada X minutos (ej. 300 s).
3. Si el control-plane devuelve una versión de **app** mayor que la actual, la app puede mostrar **“Actualización disponible”**.
4. El usuario acepta → la app **descarga** el artefacto (AppImage o .deb) según plataforma y lo deja en estado **staged**.
5. El usuario aplica el update:
   - **Linux (.deb):** normalmente hay que **abrir/ejecutar el .deb descargado** (o correr `sudo dpkg -i ...`). Al instalarse el paquete, se ejecuta el postinst y se aplican los cambios de compose + copia del agente.
   - **Linux (AppImage):** la app puede reemplazar el binario y reiniciar; el **backend** en ese caso no se toca por el AppImage (sigue en Docker). Para que el backend tenga el fix del compose, en instalaciones que usan .deb hace falta instalar el .deb nuevo; en instalaciones solo-AppImage el backend se actualiza por Watchtower o por script manual.

Para que el **fix del postinst** (compose + archivo de agente) llegue, el cliente debe **instalar el .deb nuevo** en el nodo, ya sea descargándolo a mano (Opción A) o desde Configuración → Actualizaciones (Opción B) o el flujo en segundo plano (Opción C).

---

## 2.1 ¿Funciona en todos los instaladores y OS? ¿Hace falta ser administrador?

El flujo de **Configuración → Actualizaciones** (comprobar, descargar, instalar) funciona en **todos** los instaladores y sistemas operativos soportados (Linux .deb, Linux AppImage, Windows .exe). El usuario **no tiene que abrir terminal ni escribir comandos**.

En el momento de **instalar** la actualización descargada, el sistema puede pedir permisos:

| Plataforma | Comportamiento al pulsar "Instalar ahora" | ¿Requiere admin/sudo? |
|------------|------------------------------------------|------------------------|
| **Linux (.deb)** | Se abre el instalador del sistema (Centro de software, GDebi, etc.) con el .deb descargado. | Sí: el instalador pedirá la **contraseña del usuario** (sudo) para instalar el paquete. Es un cuadro de diálogo, no terminal. |
| **Linux (AppImage)** | La app reemplaza el ejecutable actual por la nueva AppImage y se reinicia. | Solo si la AppImage está en una carpeta del sistema (ej. /opt). Si está en la carpeta del usuario (Descargas, home), **no** hace falta sudo. |
| **Windows (.exe NSIS)** | Se ejecuta el instalador en modo silencioso o se abre con el sistema; puede aparecer UAC. | Sí: instalar en Program Files suele pedir **permisos de administrador** (UAC). El usuario hace clic en "Sí" en el aviso, sin usar CMD ni PowerShell. |

**Resumen:** No hace falta saber usar terminal ni comandos. Sí puede hacer falta **introducir la contraseña (Linux)** o **aceptar el aviso de administrador (Windows)** cuando el sistema lo pida para completar la instalación.

---

## 3. Qué tiene que hacer el cliente (resumen)

| Objetivo | Acción del cliente |
|----------|--------------------|
| Tener el **fix del backend** (que vea `posvendelo-agent.json` y licencia del nodo) | Instalar el **nuevo .deb** en el nodo: desde **Configuración → Actualizaciones** usar "Comprobar ahora" y "Descargar" / "Instalar ahora", o descargar el .deb desde la página de descargas e instalar (sin comandos si usan la app). |
| Tener la **app desktop** nueva (con mejoras de UI, etc.) | Si usa .deb: con el mismo `dpkg -i` del .deb nuevo ya queda la app actualizada. Si usa solo AppImage: descargar el nuevo AppImage y sustituir / ejecutar. |
| Que el **backend** use la imagen más reciente (mensaje “posvendelo-agent.json” en vez de “titan-agent.json”) | El postinst ya hace `docker compose pull` y `up -d`; con el .deb nuevo el nodo usa la imagen actual. Si no instalan .deb, pueden hacer a mano: `cd /opt/posvendelo && docker compose pull && docker compose up -d`. |

En la práctica: **“Descargar el .deb nuevo desde la página de descargas e instalarlo con `sudo dpkg -i` en el equipo del nodo.”** Con eso el cliente obtiene el fix del compose, la copia del agente y la actualización de la app y del backend.

---

## 4. Regenerar todo (backend + instaladores + control-plane)

Para que se construya **backend**, **frontend** (instaladores) y se **suban al control-plane**, hay que disparar el workflow de release, no solo push a master:

- **Opción A:** Crear y subir un tag: `git tag v1.0.1 && git push origin v1.0.1`. El workflow `Release Artifacts` construye backend, frontend Linux, frontend Windows (y Android si aplica) y sube los artefactos al control-plane.
- **Opción B:** En GitHub → Actions → "POSVENDELO — Release Artifacts" → "Run workflow" (elegir rama/tag si lo permite).

Solo el **push a master** construye y sube la **imagen del backend** a GHCR; no genera ni sube los instaladores. Ver [DEPLOY_VS_RELEASE.md](DEPLOY_VS_RELEASE.md).

---

## 5. Orden recomendado al publicar un fix así

1. **Nosotros:** merge a master (o release) → se construye backend y se sube a GHCR.
2. **Nosotros:** construir nuevo .deb desde `frontend` (ej. `npm run build:linux`).
3. **Nosotros:** subir el .deb (y si aplica AppImage/setup.exe) al control-plane/downloads (homelab o servidor que sirva posvendelo.com).
4. **Nosotros (opcional):** publicar en el control-plane la release (versión, artifact `electron-deb`/`electron-linux`, `target_ref` a la URL del .deb) para que la app muestre “Actualización disponible”.
5. **Cliente:** descarga el .deb nuevo e instala con `sudo dpkg -i` en el nodo (o sigue el flujo de auto-update y luego ejecuta el .deb descargado).

Referencia: [DEPLOY_VS_RELEASE.md](DEPLOY_VS_RELEASE.md), [ROLLOUT_UPDATES_Y_ROLLBACK.md](../operacion/ROLLOUT_UPDATES_Y_ROLLBACK.md), [HOMELAB.md](../operacion/HOMELAB.md).
