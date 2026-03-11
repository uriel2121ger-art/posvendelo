param(
  [string]$InstallDir = "$env:LOCALAPPDATA\TitanPOS"
)

$ErrorActionPreference = "Stop"

# Quitar acceso directo del escritorio creado por el instalador
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "POSVENDELO - Punto de venta.lnk"
if (Test-Path $shortcutPath) {
  Remove-Item -Force $shortcutPath
  Write-Host "[POSVENDELO] Acceso directo del escritorio eliminado."
}

if (-not (Test-Path $InstallDir)) {
  Write-Host "[POSVENDELO] No existe $InstallDir"
  exit 0
}

Push-Location $InstallDir
try {
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose down -v
  }
} finally {
  Pop-Location
}

Remove-Item -Recurse -Force $InstallDir
Write-Host "[POSVENDELO] Instalacion eliminada: $InstallDir"
