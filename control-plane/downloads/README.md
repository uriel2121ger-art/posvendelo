# Descargas — instaladores y APKs

Esta carpeta contiene los instaladores que el **control-plane** sirve en la landing (`/`) y en la página **Descargas** (`/downloads`) para descarga pública.

## Contenido

| Archivo | Plataforma | App |
|--------|------------|-----|
| `posvendelo-setup.exe` | Windows | POS (cajeros) |
| `posvendelo.AppImage` | Linux | POS (cajeros) |
| `posvendelo_amd64.deb` | Linux (Debian/Ubuntu, PC) | POS (cajeros) |
| `posvendelo_arm64.deb` | Linux (Raspberry Pi 64-bit, Debian/Ubuntu) | POS (cajeros) |
| `posvendelo.apk` | Android | POS (cajeros) |
| `posvendelo-owner-setup.exe` | Windows | App dueños |
| `posvendelo-owner.AppImage` | Linux | App dueños |
| `posvendelo-owner_amd64.deb` | Linux (Debian/Ubuntu) | App dueños |
| `posvendelo-owner-web.zip` | Web/PWA | App dueños (opcional) |
| `posvendelo-owner.apk` | Android | App dueños (opcional) |

Los binarios **no** se suben a Git (están en `.gitignore` por tamaño). Para distribuir por la página (posvendelo.com):

1. **Generar** los instaladores/APKs desde el repo (ver secciones abajo).
2. **Copiar** los artefactos a esta carpeta con los nombres exactos de la tabla.
3. **Desplegar:** subir esta carpeta `downloads/` al servidor donde corre el control-plane (homelab). El control-plane sirve los archivos desde `CP_DOWNLOADS_DIR` o, por defecto, `control-plane/downloads/`.

### Raspberry Pi (64-bit)

El `.deb` para PC (`posvendelo_amd64.deb`) **no** funciona en Raspberry Pi (ARM). Para Pi 4/5 (64-bit) hace falta el paquete **arm64**:

- **Generar:** desde el repo, en una máquina con Node: `cd frontend && npm run build:linux:arm64`. Se genera `dist/posvendelo_1.x.x_arm64.deb`.
- **Publicar:** renombrar a `posvendelo_arm64.deb`, copiar a `control-plane/downloads/` y desplegar (o subir a la landing). La ruta de descarga es `/download/cajero/deb/arm64`.
- **Instalar en la Pi:** `sudo dpkg -i posvendelo_arm64.deb` (y `sudo apt -f install` si pide dependencias).

### App dueño — APK Android

- **Generar:** `cd owner-app && npm run build:android`. Luego, con Android SDK (ANDROID_HOME o `android/local.properties` con `sdk.dir`): `cd android && ./gradlew assembleDebug`.
- **Publicar:** copiar `owner-app/android/app/build/outputs/apk/debug/app-debug.apk` a `control-plane/downloads/posvendelo-owner.apk`. La ruta de descarga es `/download/owner/apk`.
