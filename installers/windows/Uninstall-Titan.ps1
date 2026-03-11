param(
  [string]$InstallDir = "$env:LOCALAPPDATA\TitanPOS"
)

$ErrorActionPreference = "Stop"

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
