#Requires -RunAsAdministrator

param(
  [string]$Subject = "CN=TITAN POS Publisher",
  [string]$FriendlyName = "TITAN POS Self-Signed Code Signing",
  [string]$OutputDir = "$PSScriptRoot\..\..\artifacts\codesign",
  [Parameter(Mandatory = $true)][string]$PfxPassword
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$securePassword = ConvertTo-SecureString $PfxPassword -AsPlainText -Force
$cert = New-SelfSignedCertificate `
  -Type CodeSigningCert `
  -Subject $Subject `
  -FriendlyName $FriendlyName `
  -KeyAlgorithm RSA `
  -KeyLength 4096 `
  -HashAlgorithm SHA256 `
  -CertStoreLocation "Cert:\CurrentUser\My" `
  -NotAfter (Get-Date).AddYears(3)

$pfxPath = Join-Path $OutputDir "titan-selfsigned-codesign.pfx"
$cerPath = Join-Path $OutputDir "titan-selfsigned-codesign.cer"

Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null
Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null

Write-Host ""
Write-Host "Certificado generado correctamente." -ForegroundColor Green
Write-Host "Thumbprint: $($cert.Thumbprint)"
Write-Host "PFX: $pfxPath"
Write-Host "CER: $cerPath"
Write-Host ""
Write-Host "Siguientes pasos sugeridos:" -ForegroundColor Cyan
Write-Host "1. Importa el .cer en Trusted Root y Trusted Publishers en las maquinas piloto."
Write-Host "2. Usa el .pfx para firmar builds de Windows en tu proceso de release."
Write-Host "3. Guarda el .pfx y su password fuera del repositorio."
