# Descargas — instaladores y APKs

Esta carpeta contiene los instaladores que el **control-plane** sirve en la landing (`/`) y en la página **Descargas** (`/downloads`) para descarga pública.

## Contenido

| Archivo | Plataforma | App |
|--------|------------|-----|
| `titan-pos-setup.exe` | Windows | POS (cajeros) |
| `titan-pos.AppImage` | Linux | POS (cajeros) |
| `titan-pos_amd64.deb` | Linux (Debian/Ubuntu, PC) | POS (cajeros) |
| `titan-pos_arm64.deb` | Linux (Raspberry Pi 64-bit, Debian/Ubuntu) | POS (cajeros) |
| `titan-pos.apk` | Android | POS (cajeros) |
| `titan-owner-setup.exe` | Windows | App dueños |
| `titan-owner.AppImage` | Linux | App dueños |
| `titan-owner_amd64.deb` | Linux (Debian/Ubuntu) | App dueños |
| `titan-owner-web.zip` | Web/PWA | App dueños (opcional) |
| `titan-owner.apk` | Android | App dueños (opcional) |

Los binarios se versionan en el repo para que la landing y `/downloads` puedan ofrecerlos sin depender de artefactos externos. Al generar nuevas versiones, sustituir los archivos aquí y hacer commit.

### Raspberry Pi (64-bit)

El `.deb` para PC (`titan-pos_amd64.deb`) **no** funciona en Raspberry Pi (ARM). Para Pi 4/5 (64-bit) hace falta el paquete **arm64**:

- **Generar:** desde el repo, en una máquina con Node: `cd frontend && npm run build:linux:arm64`. Se genera `dist/titan-pos_1.x.x_arm64.deb`.
- **Publicar:** renombrar a `titan-pos_arm64.deb`, copiar a `control-plane/downloads/` y desplegar (o subir a la landing). La ruta de descarga es `/download/cajero/deb/arm64`.
- **Instalar en la Pi:** `sudo dpkg -i titan-pos_arm64.deb` (y `sudo apt -f install` si pide dependencias).

### App dueño — APK Android

- **Generar:** `cd owner-app && npm run build:android`. Luego, con Android SDK (ANDROID_HOME o `android/local.properties` con `sdk.dir`): `cd android && ./gradlew assembleDebug`.
- **Publicar:** copiar `owner-app/android/app/build/outputs/apk/debug/app-debug.apk` a `control-plane/downloads/titan-owner.apk`. La ruta de descarga es `/download/owner/apk`.
