# Descargas — instaladores y APKs

Esta carpeta contiene los instaladores que el **control-plane** sirve en la landing (`/`) y en la página **Descargas** (`/downloads`) para descarga pública.

## Contenido

| Archivo | Plataforma | App |
|--------|------------|-----|
| `titan-pos-setup.exe` | Windows | POS (cajeros) |
| `titan-pos.AppImage` | Linux | POS (cajeros) |
| `titan-pos_amd64.deb` | Linux (Debian/Ubuntu) | POS (cajeros) |
| `titan-pos.apk` | Android | POS (cajeros) |
| `titan-owner-setup.exe` | Windows | App dueños |
| `titan-owner.AppImage` | Linux | App dueños |
| `titan-owner_amd64.deb` | Linux (Debian/Ubuntu) | App dueños |
| `titan-owner-web.zip` | Web/PWA | App dueños (opcional) |
| `titan-owner.apk` | Android | App dueños (opcional) |

Los binarios se versionan en el repo para que la landing y `/downloads` puedan ofrecerlos sin depender de artefactos externos. Al generar nuevas versiones, sustituir los archivos aquí y hacer commit.
