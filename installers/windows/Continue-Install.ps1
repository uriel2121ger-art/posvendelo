param(
  [Parameter(Mandatory = $true)][string]$StateFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $StateFile)) {
  throw "No se encontro el archivo de estado: $StateFile"
}

$state = Get-Content $StateFile -Raw | ConvertFrom-Json
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installScript = Join-Path $scriptDir "Install-Posvendelo.ps1"

powershell -ExecutionPolicy Bypass -File $installScript `
  -CpUrl $state.CpUrl `
  -InstallToken $state.InstallToken `
  -BranchName $state.BranchName `
  -InstallDir $state.InstallDir `
  -PublisherCertPath $state.PublisherCertPath `
  -ApiPort $state.ApiPort `
  -DbPort $state.DbPort
