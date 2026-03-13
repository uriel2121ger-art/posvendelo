# Autofirma Windows Controlada

## Objetivo

Usar un certificado autofirmado propio para firmar builds de Windows en entornos piloto o despliegues controlados, aceptando que no equivale a confianza comercial pública.

## Cuándo usarlo

- pilotos con clientes acompañados
- entornos internos
- distribución controlada por soporte
- validación previa a comprar un certificado comercial

## Cuándo no basta

- distribución pública masiva
- clientes que descargarán e instalarán solos
- escenarios donde SmartScreen y reputación del editor importan desde el día uno

## Flujo recomendado

1. Generar el certificado autofirmado en Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Create-SelfSigned-CodeSigningCert.ps1 -PfxPassword "CAMBIA_ESTA_PASSWORD"
```

1. Guardar fuera del repositorio:

- `posvendelo-selfsigned-codesign.pfx`
- `posvendelo-selfsigned-codesign.cer`

1. Para maquinas piloto, importar confianza:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Trust-PosvendeloPublisher.ps1 -CertPath ".\artifacts\codesign\posvendelo-selfsigned-codesign.cer"
```

1. Para instalacion guiada con confianza previa, usar:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\Install-Posvendelo.ps1 `
  -CpUrl https://control-plane.example.com `
  -InstallToken TOKEN `
  -PublisherCertPath ".\artifacts\codesign\posvendelo-selfsigned-codesign.cer"
```

1. Para CI Windows:

- cargar `WIN_CSC_LINK`
- cargar `WIN_CSC_KEY_PASSWORD`

## Notas importantes

- La autofirma sirve para firmar, pero no da reputación pública automática.
- El archivo `.cer` debe llegar a las maquinas que confiarán en ese publicador.
- El `.pfx` y su password deben guardarse como secreto operativo.
- El workflow de release ya está preparado para usar `WIN_CSC_LINK` y `WIN_CSC_KEY_PASSWORD`.

## Archivos relevantes

- `installers/windows/Create-SelfSigned-CodeSigningCert.ps1`
- `installers/windows/Trust-PosvendeloPublisher.ps1`
- `installers/windows/Install-Posvendelo.ps1`
- `.github/workflows/release.yml`
