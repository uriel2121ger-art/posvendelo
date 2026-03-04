# Avisos de `apt update` — qué significan y qué hacer

## Mensajes que ves

### 1. `Ign: ... Translation-es` / `Translation-en` / `Translation-es_MX`
**Normal.** Apt está omitiendo paquetes de idioma (traducciones). No es un error. Si quieres menos ruido, puedes crear `/etc/apt/apt.conf.d/99no-translations` con:
```
Acquire::Languages "none";
```
(opcional; luego `sudo apt update` mostrará menos líneas)

---

### 2. `Notice: Omitiendo el uso del fichero configurado «.../binary-i386/Packages» ... no admite la arquitectura «i386»`
**Normal en equipos de 64 bits.** Tu sistema es amd64; los repos de Docker, Chrome y antigravity no publican paquetes i386. Apt solo informa que no usa esos índices. No hace falta hacer nada.

---

### 3. `Notice: Missing Signed-By in the sources.list(5) entry for 'https://netdevops.fury.site/apt'`
**Aviso de seguridad.** Apt recomienda que el repo tenga una clave GPG en `Signed-By`. Ese repo está configurado con `Trusted: yes` (sin clave), por eso sale el Notice. Las actualizaciones funcionan igual.

**Opciones:**

- **Dejarlo así**  
  El aviso es informativo. No afecta a la instalación ni a las actualizaciones.

- **Quitar el aviso (si tienes la clave del repo)**  
  Si quien administra netdevops.fury.site te pasa el fichero de la clave (p. ej. `netdevops.gpg`):

  1. Copiar la clave al sistema:
     ```bash
     sudo cp /ruta/a/netdevops.gpg /etc/apt/keyrings/netdevops.gpg
     ```
  2. Editar el fichero del repo:
     ```bash
     sudo nano /etc/apt/sources.list.d/netdevops.sources
     ```
  3. Poner la línea `Signed-By` (y quitar la línea vacía `Signed-By:` si existe):
     ```
     Signed-By: /etc/apt/keyrings/netdevops.gpg
     ```
  4. Guardar y ejecutar:
     ```bash
     sudo apt update
     ```

Si el repo no publica clave GPG, el Notice seguirá saliendo y es seguro ignorarlo mientras uses `Trusted: yes` a conciencia (repo de confianza).

---

## Resumen

| Mensaje              | ¿Problema? | Acción recomendada   |
|----------------------|------------|----------------------|
| Ign Translation-*    | No         | Ninguna (o `Acquire::Languages "none"`) |
| Omitiendo i386       | No         | Ninguna              |
| Missing Signed-By    | Aviso      | Ninguna o añadir clave si la tienes     |
