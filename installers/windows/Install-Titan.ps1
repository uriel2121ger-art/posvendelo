#Requires -RunAsAdministrator

param(
  [Parameter(Mandatory = $true)][string]$CpUrl,
  [string]$InstallToken = "",
  [string]$BranchName = "",
  [string]$CloudEmail = "",
  [string]$CloudPassword = "",
  [string]$TenantName = "",
  [switch]$ExistingCloud,
  [string]$InstallDir = "$env:LOCALAPPDATA\TitanPOS",
  [string]$PublisherCertPath = "",
  [int]$ApiPort = 0,
  [int]$DbPort = 0
)

$ErrorActionPreference = "Stop"
$statePath = Join-Path $env:ProgramData "TitanPOS\install-state.json"

function Write-Step([string]$Message) {
  Write-Host "[POSVENDELO] $Message" -ForegroundColor Cyan
}

function Ensure-Docker {
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    return
  }

  Write-Step "Docker Desktop no encontrado. Intentando instalar con winget..."
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget no esta disponible. Instala Docker Desktop manualmente y vuelve a ejecutar."
  }

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $statePath) | Out-Null
  @{
    CpUrl = $CpUrl
    InstallToken = $InstallToken
    BranchName = $BranchName
    InstallDir = $InstallDir
    PublisherCertPath = $PublisherCertPath
    ApiPort = $ApiPort
    DbPort = $DbPort
  } | ConvertTo-Json | Set-Content -Encoding UTF8 $statePath

  winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
  throw "Docker Desktop fue instalado. Abre Docker Desktop y luego ejecuta Continue-Install.ps1 con -StateFile `"$statePath`"."
}

function Wait-DockerReady {
  Write-Step "Verificando que Docker Desktop este listo..."
  for ($i = 0; $i -lt 45; $i++) {
    try {
      docker version | Out-Null
      return
    } catch {
      Start-Sleep -Seconds 2
    }
  }

  throw "Docker Desktop no responde todavia. Abre Docker Desktop, espera a que termine de iniciar y luego ejecuta Continue-Install.ps1."
}

function Import-PublisherCert {
  if (-not $PublisherCertPath) {
    return
  }
  if (-not (Test-Path $PublisherCertPath)) {
    throw "No se encontro el certificado del publicador: $PublisherCertPath"
  }

  Write-Step "Importando certificado del publicador autofirmado..."
  Import-Certificate -FilePath $PublisherCertPath -CertStoreLocation "Cert:\LocalMachine\Root" | Out-Null
  Import-Certificate -FilePath $PublisherCertPath -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher" | Out-Null
}

function New-RandomHex([int]$Length) {
  $byteLength = [Math]::Ceiling($Length / 2)
  $bytes = New-Object byte[] $byteLength
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return ([BitConverter]::ToString($bytes)).Replace("-", "").Substring(0, $Length).ToLower()
}

function Ensure-CloudInstallToken {
  if ($InstallToken) {
    return
  }

  if (-not $CloudEmail) {
    $script:CloudEmail = Read-Host "Correo cloud"
  }
  if (-not $CloudPassword) {
    $secure = Read-Host "Contraseña cloud" -AsSecureString
    $script:CloudPassword = [System.Net.NetworkCredential]::new("", $secure).Password
  }
  if (-not $BranchName) {
    $script:BranchName = Read-Host "Nombre de la sucursal"
  }
  if (-not $ExistingCloud.IsPresent -and -not $TenantName) {
    $script:TenantName = Read-Host "Empresa o negocio"
  }

  if ($ExistingCloud.IsPresent) {
    $authBody = @{
      email = $CloudEmail
      password = $CloudPassword
    } | ConvertTo-Json
    $login = Invoke-RestMethod -Method Post -Uri "$($CpUrl.TrimEnd('/'))/api/v1/cloud/login" -ContentType "application/json" -Body $authBody
    $sessionToken = $login.data.session_token
    if (-not $sessionToken) {
      throw "No se pudo obtener sesión cloud"
    }
    $branchBody = @{ branch_name = $(if ($BranchName) { $BranchName } else { "Sucursal Principal" }) } | ConvertTo-Json
    $branch = Invoke-RestMethod -Method Post -Uri "$($CpUrl.TrimEnd('/'))/api/v1/cloud/register-branch" -ContentType "application/json" -Headers @{ Authorization = "Bearer $sessionToken" } -Body $branchBody
    $script:InstallToken = $branch.data.install_token
  } else {
    $registerBody = @{
      email = $CloudEmail
      password = $CloudPassword
      business_name = $TenantName
      branch_name = $(if ($BranchName) { $BranchName } else { "Sucursal Principal" })
    } | ConvertTo-Json
    $register = Invoke-RestMethod -Method Post -Uri "$($CpUrl.TrimEnd('/'))/api/v1/cloud/register" -ContentType "application/json" -Body $registerBody
    $script:InstallToken = $register.data.install_token
  }

  if (-not $InstallToken) {
    throw "No se pudo obtener install token desde el onboarding cloud"
  }
}

function Get-FreeTcpPort([int]$PreferredPort) {
  for ($port = $PreferredPort; $port -lt ($PreferredPort + 200); $port++) {
    $listener = $null
    try {
      $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
      $listener.Start()
      return $port
    } catch {
      continue
    } finally {
      if ($listener) {
        $listener.Stop()
      }
    }
  }

  throw "No se encontro un puerto libre a partir de $PreferredPort"
}

function Invoke-TitanCompose {
  param(
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$EnvFilePath
  )

  $varsToClear = @(
    "POSTGRES_PASSWORD",
    "ADMIN_API_USER",
    "ADMIN_API_PASSWORD",
    "JWT_SECRET",
    "CORS_ALLOWED_ORIGINS",
    "CONTROL_PLANE_URL",
    "TITAN_LICENSE_KEY",
    "TITAN_BRANCH_ID",
    "TITAN_VERSION",
    "CF_TUNNEL_TOKEN",
    "BACKEND_IMAGE",
    "LOCAL_API_PORT",
    "LOCAL_POSTGRES_PORT",
    "TITAN_LICENSE_ENFORCEMENT"
  )

  $backup = @{}
  foreach ($name in $varsToClear) {
    $backup[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, $null, "Process")
  }

  Push-Location $WorkingDirectory
  try {
    & docker compose --env-file $EnvFilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose fallo con codigo $LASTEXITCODE"
    }
  } finally {
    Pop-Location
    foreach ($name in $varsToClear) {
      [Environment]::SetEnvironmentVariable($name, $backup[$name], "Process")
    }
  }
}

function Send-InstallReport([string]$Status, [string]$ErrorMessage) {
  $payload = @{
    install_token = $InstallToken
    status = $Status
    error = $(if ($ErrorMessage) { $ErrorMessage } else { $null })
    app_version = "1.0.0"
    pos_version = "2.0.0"
  } | ConvertTo-Json

  try {
    Invoke-RestMethod -Method Post -Uri "$($CpUrl.TrimEnd('/'))/api/v1/branches/install-report" -ContentType "application/json" -Body $payload | Out-Null
  } catch {
    Write-Warning "No se pudo reportar estado de instalacion al control-plane."
  }
}

try {
  if (-not $InstallToken) {
    $activateCloud = Read-Host "¿Activar Nube PosVendelo ahora para generar install token? [s/N]"
    if ($activateCloud -match '^[sS]$') {
      $hasAccount = Read-Host "¿Ya tienes cuenta cloud? [s/N]"
      if ($hasAccount -match '^[sS]$') {
        $ExistingCloud = $true
      }
      Ensure-CloudInstallToken
    }
  }

  if (-not $InstallToken) {
    throw "Se requiere install token o activar onboarding cloud."
  }

  Ensure-Docker
  Import-PublisherCert
  Wait-DockerReady

  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "backups") | Out-Null

  $bootstrap = Invoke-RestMethod -Method Get -Uri "$($CpUrl.TrimEnd('/'))/api/v1/branches/bootstrap-config" -Headers @{"Authorization" = "Bearer $InstallToken"}
  $bootstrapData = $bootstrap.data

  if ($ApiPort -le 0) {
    $ApiPort = Get-FreeTcpPort 8000
  }
  if ($DbPort -le 0) {
    $DbPort = Get-FreeTcpPort 5434
  }

  $envPath = Join-Path $InstallDir ".env"
  $composePath = Join-Path $InstallDir "docker-compose.yml"
  $agentPath = Join-Path $InstallDir "titan-agent.json"
  $registerPath = Join-Path $env:TEMP "titan-register.json"

  @"
POSTGRES_PASSWORD=$(New-RandomHex 32)
ADMIN_API_USER=admin
ADMIN_API_PASSWORD=$(New-RandomHex 24)
JWT_SECRET=$(New-RandomHex 64)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080
CONTROL_PLANE_URL=$($bootstrapData.cp_url)
TITAN_LICENSE_KEY=$($bootstrapData.tenant_slug)
TITAN_BRANCH_ID=$($bootstrapData.branch_id)
TITAN_VERSION=2.0.0
CF_TUNNEL_TOKEN=$($bootstrapData.cf_tunnel_token)
BACKEND_IMAGE=$($bootstrapData.backend_image)
LOCAL_API_PORT=$ApiPort
LOCAL_POSTGRES_PORT=$DbPort
TITAN_LICENSE_ENFORCEMENT=true
"@ | Set-Content -Encoding UTF8 $envPath

  $adminUser = "admin"
  $adminPasswordLine = Get-Content $envPath | Where-Object { $_ -like "ADMIN_API_PASSWORD=*" } | Select-Object -First 1
  $adminPassword = if ($adminPasswordLine) { ($adminPasswordLine -split "=", 2)[1] } else { "" }

  @{
    controlPlaneUrl = $bootstrapData.cp_url
    branchId = $bootstrapData.branch_id
    installToken = $InstallToken
    releaseManifestUrl = $bootstrapData.release_manifest_url
    licenseResolveUrl = $bootstrapData.license_resolve_url
    localApiUrl = "http://127.0.0.1:$ApiPort"
    backendHealthUrl = "http://127.0.0.1:$ApiPort/health"
    appArtifact = "electron-windows"
    backendArtifact = "backend"
    releaseChannel = $(if ($bootstrapData.release_channel) { $bootstrapData.release_channel } else { "stable" })
    pollIntervals = @{
      healthSeconds = 15
      manifestSeconds = 300
      licenseSeconds = 300
    }
    license = $bootstrapData.license
    bootstrap = @{
      installDir = $InstallDir
      composeTemplateUrl = $bootstrapData.compose_template_url
      registerUrl = $bootstrapData.register_url
      installReportUrl = $bootstrapData.install_report_url
      bootstrapPublicKey = $bootstrapData.bootstrap_public_key
      licenseResolveUrl = $bootstrapData.license_resolve_url
      companionUrl = $bootstrapData.companion_url
      companionEntryUrl = $bootstrapData.companion_entry_url
      ownerSessionUrl = $bootstrapData.owner_session_url
      ownerApiBaseUrl = $bootstrapData.owner_api_base_url
      quickLinks = $bootstrapData.quick_links
    }
  } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $agentPath

  @"
POSVENDELO - RESUMEN DE INSTALACION

Directorio: $InstallDir
Branch ID: $($bootstrapData.branch_id)
Control Plane: $($bootstrapData.cp_url)
API local: http://127.0.0.1:$ApiPort
Health local: http://127.0.0.1:$ApiPort/health
Postgres local: 127.0.0.1:$DbPort
Manifest: $($bootstrapData.release_manifest_url)
Companion: $($bootstrapData.companion_url)
Companion Portfolio: $($bootstrapData.companion_entry_url)
Owner API: $($bootstrapData.owner_api_base_url)

Credenciales iniciales de acceso a caja:
- Usuario: $adminUser
- Contraseña: $adminPassword

Archivos clave:
- .env
- docker-compose.yml
- titan-agent.json

Si necesitas continuar instalacion despues de Docker Desktop:
powershell -ExecutionPolicy Bypass -File .\installers\windows\Continue-Install.ps1 -StateFile "$statePath"
"@ | Set-Content -Encoding UTF8 (Join-Path $InstallDir "INSTALL_SUMMARY.txt")

  if ($PublisherCertPath) {
@"

Certificado autofirmado importado:
$PublisherCertPath
"@ | Add-Content -Encoding UTF8 (Join-Path $InstallDir "INSTALL_SUMMARY.txt")
  }

  Invoke-WebRequest -Uri "$($CpUrl.TrimEnd('/'))/api/v1/branches/compose-template" -Headers @{"Authorization" = "Bearer $InstallToken"} -OutFile $composePath

  $registerPayload = @{
    install_token = $InstallToken
    machine_id = $env:COMPUTERNAME
    os_platform = "windows"
    branch_name = $(if ($BranchName) { $BranchName } else { $null })
    app_version = "1.0.0"
    pos_version = "2.0.0"
  } | ConvertTo-Json

  $registerPayload | Set-Content -Encoding UTF8 $registerPath
  try {
    Invoke-RestMethod -Method Post -Uri "$($CpUrl.TrimEnd('/'))/api/v1/branches/register" -ContentType "application/json" -InFile $registerPath | Out-Null
  } finally {
    if (Test-Path $registerPath) {
      Remove-Item -Force $registerPath
    }
  }

  Invoke-TitanCompose -WorkingDirectory $InstallDir -EnvFilePath $envPath -Arguments @("pull")
  Invoke-TitanCompose -WorkingDirectory $InstallDir -EnvFilePath $envPath -Arguments @("up", "-d")

  Write-Step "Esperando health local..."
  for ($i = 0; $i -lt 60; $i++) {
    try {
      Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$ApiPort/health" | Out-Null
      Send-InstallReport "success" $null
      if (Test-Path $statePath) {
        Remove-Item -Force $statePath
      }
      Write-Step "Instalacion completada en $InstallDir"
      exit 0
    } catch {
      Start-Sleep -Seconds 2
    }
  }

  throw "El backend local no respondio a tiempo."
} catch {
  if ($CpUrl -and $InstallToken) {
    Send-InstallReport "error" $_.Exception.Message
  }
  throw
}
