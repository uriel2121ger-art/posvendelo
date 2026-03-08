#Requires -RunAsAdministrator

param(
  [Parameter(Mandatory = $true)][string]$CertPath,
  [ValidateSet("CurrentUser", "LocalMachine")][string]$Scope = "LocalMachine"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $CertPath)) {
  throw "No se encontro el certificado: $CertPath"
}

$rootStore = "Cert:\$Scope\Root"
$publisherStore = "Cert:\$Scope\TrustedPublisher"

Import-Certificate -FilePath $CertPath -CertStoreLocation $rootStore | Out-Null
Import-Certificate -FilePath $CertPath -CertStoreLocation $publisherStore | Out-Null

Write-Host ""
Write-Host "Certificado importado correctamente." -ForegroundColor Green
Write-Host "Root store: $rootStore"
Write-Host "Trusted publisher: $publisherStore"
