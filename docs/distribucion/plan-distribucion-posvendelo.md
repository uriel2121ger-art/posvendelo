# Plan: Sistema de Distribucion POSVENDELO
Fecha: Marzo 2026

---

## Estado actual (implementado)

```
GitHub Actions (CI)
  └── Build & Release automatico
        ├── Docker multi-arch → GHCR (ghcr.io/uriel2121ger-art/posvendelo:latest)
        ├── Electron (.deb, .AppImage, .exe) → GitHub Releases
        ├── Owner app (.deb, .AppImage, .exe) → GitHub Releases
        └── APKs firmados (cajero + owner) → GitHub Releases

Control-plane (posvendelo.com)
  └── /api/v1/releases/manifest?os=linux
        ├── backend: apunta a GHCR tag
        ├── app: URL directa a GitHub Release
        └── owner_app: URL directa a GitHub Release

Landing page (posvendelo.com/)
  └── Botones de descarga → /download/{plataforma}/{formato}
        └── Redirect 302 a GitHub Release URL
```

### Flujo de auto-update (6 plataformas)

| Plataforma | Mecanismo |
|---|---|
| Docker backend | Watchtower (GHCR poll cada 30 min) |
| Linux .deb (amd64/arm64) | localAgent.ts → manifest → download + dpkg -i |
| Linux AppImage | localAgent.ts → manifest → download + reemplazo |
| Windows .exe | localAgent.ts → manifest → download + NSIS installer |
| Android cajero APK | Capacitor update check → Browser.open(url) |
| Android owner APK | Capacitor update check → Browser.open(url) |

### Flujo de release

```
git push (fix:/feat:) → GitHub Actions → auto-release vX.Y.Z
  → CI sube artefactos a GitHub Release
  → CI registra artefactos en control-plane (/api/v1/releases/upload)
  → Control-plane actualiza manifest
  → Nodos consultan manifest y se auto-actualizan
```

---

## Stack por plataforma

| Plataforma | Tecnologia |
|---|---|
| Windows | Electron + React + NSIS |
| Linux (.deb / .AppImage) | Electron + React |
| Raspberry Pi (ARM64) | Electron + React |
| Android (.apk) | Capacitor + React |

---

## Mejora futura: Cloudflare R2

### Por que considerar R2

- GitHub Releases tiene limite de 2 GB por archivo y rate limits en descargas
- CF Tunnel Free tiene limite de 100 MB por request (ya mitigado con URLs directas a GH)
- R2 tiene egress 100% gratuito e ilimitado
- Arquitectura CDN profesional: como VS Code, Slack, Notion

### Que cambiaria

```
Actual:  CI → GitHub Release → control-plane registra URL
Futuro:  CI → R2 bucket → control-plane registra URL de R2
```

Solo cambia el destino del upload en CI y las URLs en el manifest. El flujo del cliente no cambia.

### Estructura propuesta en R2

```
posvendelo-releases/               <- bucket
  cajero/
    {version}/
      posvendelo-{version}-setup.exe
      posvendelo-{version}.AppImage
      posvendelo_{version}_amd64.deb
      posvendelo-{version}.apk
      latest.yml                   <- electron-updater
  owner/
    {version}/
      posvendelo-owner-{version}-setup.exe
      posvendelo-owner-{version}.AppImage
      posvendelo-owner_{version}_amd64.deb
      posvendelo-owner-{version}.apk
      latest.yml
```

### Free tier R2

| Concepto | Limite gratis/mes |
|---|---|
| Storage | 10 GB |
| Uploads (Class A) | 1,000,000 ops |
| Downloads (Class B) | 10,000,000 ops |
| Egress | **Ilimitado** |

### Cuando migrar a R2

No es urgente. GitHub Releases funciona bien para el volumen actual. Considerar R2 cuando:
- Se superen los rate limits de GitHub Releases
- Se necesite un custom domain (downloads.posvendelo.com)
- Se quiera delta updates con electron-updater (requiere latest.yml servido desde URL propia)

---

## Stub instalador Windows (pendiente)

Un `.exe` de ~2 MB distribuible por WhatsApp/email/USB. Al ejecutarse consulta el manifest, descarga el instalador real y lo lanza.

```
Cliente descarga PosvendeloSetup.exe (2 MB, stub permanente)
  -> Consulta posvendelo.com/api/v1/releases/manifest?os=windows
  -> Descarga posvendelo-X.X.X-setup.exe
  -> Lanza el instalador NSIS
```

Implementar cuando haya demanda de distribucion fisica.
