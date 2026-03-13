#Requires -RunAsAdministrator

# URL del nodo central por defecto. El usuario no tiene que escribir nada; el token se obtiene por pre-registro.
param(
  [string]$CpUrl = "https://posvendelo.com",
  [string]$InstallToken = "",
  [string]$BranchName = "",
  [string]$CloudEmail = "",
  [string]$CloudPassword = "",
  [string]$TenantName = "",
  [switch]$ExistingCloud,
  [string]$InstallDir = "$env:LOCALAPPDATA\POSVENDELO",
  [string]$PublisherCertPath = "",
  [int]$ApiPort = 0,
  [int]$DbPort = 0
)

$ErrorActionPreference = "Stop"
$statePath = Join-Path $env:ProgramData "POSVENDELO\install-state.json"

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

function Collect-HardwareInfo {
  $boardSerial = (Get-CimInstance Win32_BaseBoard).SerialNumber
  $boardName = (Get-CimInstance Win32_BaseBoard).Product
  $cpuModel = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
  $macPrimary = (Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -First 1).MacAddress
  $diskSerial = (Get-CimInstance Win32_DiskDrive | Where-Object MediaType -like '*fixed*' | Select-Object -First 1).SerialNumber

  # Clean up placeholder/invalid values
  $invalidValues = @('', 'Default string', 'Default', 'To Be Filled By O.E.M.', 'Not Specified', 'None', 'N/A', '0')
  if ($boardSerial -in $invalidValues) { $boardSerial = $null }
  if ($boardName -in $invalidValues) { $boardName = $null }

  return @{
    board_serial = $boardSerial
    board_name   = $boardName
    cpu_model    = $cpuModel
    mac_primary  = $macPrimary
    disk_serial  = $diskSerial
  }
}

function Invoke-PreRegister {
  Write-Step "Recolectando información de hardware..."
  $hwInfo = Collect-HardwareInfo

  $branchNameValue = if ($BranchName) { $BranchName } else { "Sucursal Principal" }
  $payload = @{
    hw_info     = $hwInfo
    os_platform = "windows"
    branch_name = $branchNameValue
  } | ConvertTo-Json -Depth 4

  Write-Step "Registrando equipo en el servidor central..."
  try {
    $response = Invoke-RestMethod -Method Post `
      -Uri "$($CpUrl.TrimEnd('/'))/api/v1/branches/pre-register" `
      -ContentType "application/json" `
      -Body $payload
  } catch {
    throw "No se pudo conectar al servidor central. Verifique su conexión a internet e intente de nuevo."
  }

  $data = $response.data
  if ($data.is_new -eq $true) {
    Write-Step "Equipo registrado por primera vez."
  } else {
    Write-Step "Equipo reconocido. Período de prueba continúa."
  }

  $script:InstallToken = $data.install_token
  if (-not $InstallToken) {
    throw "No se obtuvo token de instalación del servidor."
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

function Invoke-PosvendoloCompose {
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
    "POSVENDELO_LICENSE_KEY",
    "POSVENDELO_BRANCH_ID",
    "POSVENDELO_VERSION",
    "CF_TUNNEL_TOKEN",
    "BACKEND_IMAGE",
    "LOCAL_API_PORT",
    "LOCAL_POSTGRES_PORT",
    "POSVENDELO_LICENSE_ENFORCEMENT"
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
    if ($CloudEmail -or $CloudPassword -or $TenantName) {
      Ensure-CloudInstallToken
    } else {
      # Pre-register with hardware fingerprint (plug-and-play, no account needed)
      Invoke-PreRegister
    }
  }

  if (-not $InstallToken) {
    throw "No se pudo obtener un token de instalación."
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
  $agentPath = Join-Path $InstallDir "posvendelo-agent.json"  # nombre de archivo interno del agente
  $registerPath = Join-Path $env:TEMP "posvendelo-register.json"

  @"
POSTGRES_PASSWORD=$(New-RandomHex 32)
ADMIN_API_USER=
ADMIN_API_PASSWORD=
JWT_SECRET=$(New-RandomHex 64)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080
CONTROL_PLANE_URL=$($bootstrapData.cp_url)
POSVENDELO_LICENSE_KEY=$($bootstrapData.tenant_slug)
POSVENDELO_BRANCH_ID=$($bootstrapData.branch_id)
POSVENDELO_VERSION=2.0.0
CF_TUNNEL_TOKEN=$($bootstrapData.cf_tunnel_token)
BACKEND_IMAGE=$($bootstrapData.backend_image)
LOCAL_API_PORT=$ApiPort
LOCAL_POSTGRES_PORT=$DbPort
POSVENDELO_LICENSE_ENFORCEMENT=true
"@ | Set-Content -Encoding UTF8 $envPath

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

Primer acceso:
Configura tu usuario al abrir el POS por primera vez.
El asistente de configuracion te pedira crear un usuario administrador.

Período de prueba: 120 días desde el primer registro
Activar Nube: Desde la app, Configuración > Nube PosVendelo

Archivos clave:
- .env
- docker-compose.yml
- posvendelo-agent.json

Como abrir el punto de venta (POS):
  - Doble clic en el icono "POSVENDELO - Punto de venta" del escritorio (abre la app o la pagina de descargas).
  - Si ya instalo la app: ejecute "POSVENDELO" o "posvendelo" desde el menu Inicio.
  - Si aun no tiene la app: descargue el instalador .exe desde la web e instalelo.
  - Si la app no inicia: ejecutela desde Ejecutar (Win+R) o desde una consola para ver mensajes de error.

Si necesitas continuar instalacion despues de Docker Desktop:
powershell -ExecutionPolicy Bypass -File .\installers\windows\Continue-Install.ps1 -StateFile "$statePath"
"@ | Set-Content -Encoding UTF8 (Join-Path $InstallDir "INSTALL_SUMMARY.txt")

  $downloadPage = $CpUrl.TrimEnd('/')
  $abrirPosScript = @"
# Abre el POS si esta instalado; si no, abre la pagina de descargas
`$exe = `$null
try { `$exe = Get-Command posvendelo -ErrorAction SilentlyContinue } catch {}
if (`$exe) { Start-Process `$exe.Source; exit }
`$paths = @(
  "`$env:LOCALAPPDATA\Programs\POSVENDELO\posvendelo.exe",
  "`$env:ProgramFiles\POSVENDELO\posvendelo.exe"
)
foreach (`$p in `$paths) {
  if (Test-Path `$p) { Start-Process `$p; exit }
}
Start-Process "$downloadPage"
"@
  $abrirPosPath = Join-Path $InstallDir "Abrir-POS.ps1"
  $abrirPosScript | Set-Content -Encoding UTF8 -Path $abrirPosPath

  $desktopPath = [Environment]::GetFolderPath("Desktop")
  if ($desktopPath) {
    try {
      $wsh = New-Object -ComObject WScript.Shell
      $shortcut = $wsh.CreateShortcut((Join-Path $desktopPath "POSVENDELO - Punto de venta.lnk"))
      $shortcut.TargetPath = "powershell.exe"
      $shortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$abrirPosPath`""
      $shortcut.WorkingDirectory = $InstallDir
      $shortcut.Description = "Abrir punto de venta POSVENDELO"
      $shortcut.Save()
      [System.Runtime.Interopservices.Marshal]::ReleaseComObject($wsh) | Out-Null
    } catch {
      Write-Warning "No se pudo crear el acceso directo en el escritorio: $_"
    }
  }

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

  Invoke-PosvendoloCompose -WorkingDirectory $InstallDir -EnvFilePath $envPath -Arguments @("pull")
  Invoke-PosvendoloCompose -WorkingDirectory $InstallDir -EnvFilePath $envPath -Arguments @("up", "-d")

  Write-Step "Esperando health local..."
  for ($i = 0; $i -lt 60; $i++) {
    try {
      Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$ApiPort/health" | Out-Null
      Send-InstallReport "success" $null
      if (Test-Path $statePath) {
        Remove-Item -Force $statePath
      }
      Write-Step "Instalacion completada en $InstallDir"
      Write-Host ""
      Write-Host "Para abrir el punto de venta (POS): busque 'POSVENDELO' en el menu Inicio o ejecute posvendelo." -ForegroundColor Green
      Write-Host "Si aun no instalo la app, descargue el .exe desde la web." -ForegroundColor Green
      Write-Host ""
      $posExe = $null
      if (Get-Command posvendelo -ErrorAction SilentlyContinue) { $posExe = "posvendelo" }
      if (-not $posExe -and (Test-Path "$env:LOCALAPPDATA\Programs\POSVENDELO\posvendelo.exe")) { $posExe = "$env:LOCALAPPDATA\Programs\POSVENDELO\posvendelo.exe" }
      if (-not $posExe -and (Test-Path "$env:ProgramFiles\POSVENDELO\posvendelo.exe")) { $posExe = "$env:ProgramFiles\POSVENDELO\posvendelo.exe" }
      if ($posExe) {
        Write-Step "Iniciando la aplicacion POS..."
        Start-Process -FilePath $posExe -ErrorAction SilentlyContinue
      } else {
        Write-Step "Abriendo el POS en el navegador para configuracion inicial..."
        Start-Process "http://127.0.0.1:$ApiPort" -ErrorAction SilentlyContinue
      }
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
