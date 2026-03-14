import { app, dialog } from 'electron'
import { execSync, spawn } from 'child_process'
import { existsSync, mkdtempSync, writeFileSync } from 'fs'
import { join } from 'path'
import http from 'http'

const INSTALL_DIR =
  process.platform === 'win32'
    ? join(process.env.PROGRAMDATA || 'C:\\ProgramData', 'POSVENDELO')
    : '/opt/posvendelo'

const COMPOSE_FILE = join(INSTALL_DIR, 'docker-compose.yml')
const HEALTH_URL = 'http://127.0.0.1:8000/health'

// ---------------------------------------------------------------------------
// Public entry point — call before creating the main window
// ---------------------------------------------------------------------------
export async function ensureBackend(): Promise<boolean> {
  // Fast path: backend already running (deb postinst already ran, dev mode, etc.)
  // Use 15 retries (30s) because on first install postgres healthcheck alone
  // can take up to 50s (interval=10s × retries=5) before the API container starts.
  if (await checkHealth(15)) return true

  // Compose file present → containers are installed but maybe stopped
  if (existsSync(COMPOSE_FILE)) {
    await tryStartExisting()
    if (await checkHealth(30)) return true

    const { response } = await dialog.showMessageBox({
      type: 'warning',
      title: 'POSVENDELO — Backend no responde',
      message:
        'El servidor está instalado pero no responde.\n\n' +
        '¿Deseas intentar reiniciarlo ahora?',
      buttons: ['Reiniciar servidor', 'Continuar de todas formas', 'Salir'],
      defaultId: 0,
      cancelId: 2
    })
    if (response === 2) return false
    if (response === 0) {
      await tryStartExisting()
      if (await checkHealth(30)) return true
    }
    // response === 1 → let the app load (user may be debugging)
    return true
  }

  // First-time setup
  const { response: confirmResponse } = await dialog.showMessageBox({
    type: 'info',
    title: 'POSVENDELO — Primera instalación',
    message:
      'Se necesita configurar el servidor del punto de venta.\n\n' +
      'Esto incluye instalar Docker y descargar el backend.\n' +
      'Se solicitará tu contraseña de administrador.',
    buttons: ['Configurar ahora', 'Cancelar'],
    defaultId: 0,
    cancelId: 1
  })

  if (confirmResponse === 1) return false

  const success = await runSetup()
  if (!success) {
    dialog.showErrorBox(
      'Error de instalación',
      'No se pudo configurar el servidor.\n\n' +
        'Verifica que tengas conexión a internet y permisos de administrador.\n' +
        'También puedes instalar manualmente ejecutando el instalador incluido.'
    )
    return false
  }

  // Be patient — first Docker pull + DB migrations can take a while
  if (await checkHealth(60)) return true

  dialog.showErrorBox(
    'Instalación completada',
    'El servidor se instaló pero aún no responde.\n\n' +
      'Espera un momento y vuelve a abrir POSVENDELO.'
  )
  return false
}

// ---------------------------------------------------------------------------
// Health check with retry (each attempt waits 2 s before the next)
// ---------------------------------------------------------------------------
function checkHealth(retries: number = 3): Promise<boolean> {
  return new Promise((resolve) => {
    let attempts = 0

    const attempt = (): void => {
      const req = http.get(HEALTH_URL, { timeout: 3000 }, (res) => {
        res.resume() // drain to avoid memory leaks
        if (res.statusCode === 200) resolve(true)
        else retry()
      })
      req.on('error', retry)
      req.on('timeout', () => {
        req.destroy()
        retry()
      })
    }

    const retry = (): void => {
      attempts++
      if (attempts < retries) setTimeout(attempt, 2000)
      else resolve(false)
    }

    attempt()
  })
}

// ---------------------------------------------------------------------------
// Try to start existing stopped containers (no elevation needed if user is in
// docker group; falls back to pkexec on Linux)
// ---------------------------------------------------------------------------
async function tryStartExisting(): Promise<void> {
  try {
    if (process.platform === 'win32') {
      // All args are literal constants — no user input, no injection risk
      execSync(`cd /d "${INSTALL_DIR}" && docker compose up -d`, {
        timeout: 60000,
        stdio: 'ignore'
      })
    } else {
      try {
        // Best case: user is already in the docker group
        execSync(`docker compose -f "${COMPOSE_FILE}" up -d`, {
          timeout: 60000,
          stdio: 'ignore'
        })
      } catch {
        // Fallback: ask for elevation via polkit (spawn with array to avoid shell injection)
        const { spawnSync } = require('node:child_process') as typeof import('node:child_process')
        const result = spawnSync('pkexec', ['docker', 'compose', '-f', COMPOSE_FILE, 'up', '-d'], {
          timeout: 60000,
          stdio: 'ignore'
        })
        if (result.status !== 0) throw new Error('pkexec docker compose failed')
      }
    }
  } catch {
    // Swallowed — the caller checks health independently
  }
}

// ---------------------------------------------------------------------------
// Run the setup script elevated
// ---------------------------------------------------------------------------
function runSetup(): Promise<boolean> {
  return new Promise((resolve) => {
    const scriptPath = getBundledScriptPath()

    if (scriptPath) {
      runElevated(scriptPath, resolve)
      return
    }

    // No bundled script → generate an inline one
    const script = generateSetupScript()
    // Use mkdtemp with 0o700 to prevent TOCTOU attacks in /tmp
    const { tmpdir } = require('node:os') as typeof import('node:os')
    const tmpDir = mkdtempSync(join(tmpdir(), 'posvendelo-'))
    const tmpScript =
      process.platform === 'win32'
        ? join(tmpDir, 'posvendelo-setup.ps1')
        : join(tmpDir, 'setup.sh')

    writeFileSync(tmpScript, script, { mode: 0o700 })
    runElevated(tmpScript, resolve)
  })
}

// ---------------------------------------------------------------------------
// Locate a setup script bundled inside the package (AppImage resources dir or
// installed alongside the deb)
// ---------------------------------------------------------------------------
function getBundledScriptPath(): string | null {
  const resourcesPath: string =
    (process as NodeJS.Process & { resourcesPath?: string }).resourcesPath ?? ''

  const candidates =
    process.platform === 'win32'
      ? [
          join(resourcesPath, 'posvendelo-setup.ps1'),
          join(app.getAppPath(), '..', 'installers', 'windows', 'Install-Posvendelo.ps1')
        ]
      : [
          join(resourcesPath, 'posvendelo-setup.sh'),
          join(app.getAppPath(), '..', 'installers', 'linux', 'postinst.sh')
        ]

  return candidates.find((p) => existsSync(p)) ?? null
}

// ---------------------------------------------------------------------------
// Inline setup scripts (mirrors postinst.sh / Install-Posvendelo.ps1 but without
// control-plane calls — pure offline-first first-run setup)
// ---------------------------------------------------------------------------
function generateSetupScript(): string {
  return process.platform === 'win32' ? generateWindowsScript() : generateLinuxScript()
}

function generateLinuxScript(): string {
  // Shell variables inside the compose heredoc must be written literally (bash << 'DCEOF' prevents
  // their expansion at the bash level). Here we escape them so TypeScript does not interpolate them.
  return `#!/bin/bash
set -e

INSTALL_DIR="/opt/posvendelo"
COMPOSE_FILE="\$INSTALL_DIR/docker-compose.yml"
ENV_FILE="\$INSTALL_DIR/.env"
SERVICE_FILE="/etc/systemd/system/posvendelo.service"

log() { echo "[POSVENDELO] \$*"; }

# Upgrade path: compose already present -> just start containers
if [ -f "\$COMPOSE_FILE" ]; then
  log "Compose existente — iniciando contenedores..."
  cd "\$INSTALL_DIR" && docker compose up -d
  exit 0
fi

log "Instalando sistema completo..."

# Install Docker
if ! command -v docker &>/dev/null; then
  log "Instalando Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
else
  log "Docker ya instalado."
fi
systemctl start docker 2>/dev/null || true

# Add real user to docker group
REAL_USER="\${SUDO_USER:-\$USER}"
if [ -n "\$REAL_USER" ] && [ "\$REAL_USER" != "root" ]; then
  usermod -aG docker "\$REAL_USER" 2>/dev/null || true
  log "Usuario '\$REAL_USER' agregado al grupo docker."
fi

mkdir -p "\$INSTALL_DIR/backups"

# Generate .env (never overwrite existing secrets)
if [ ! -f "\$ENV_FILE" ]; then
  JWT_SECRET=\$(openssl rand -hex 32)
  DB_PASSWORD=\$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
  cat > "\$ENV_FILE" << ENVEOF
POSTGRES_PASSWORD=\$DB_PASSWORD
DATABASE_URL=postgresql+asyncpg://posvendelo_user:\$DB_PASSWORD@postgres:5432/posvendelo
JWT_SECRET=\$JWT_SECRET
ADMIN_API_USER=
ADMIN_API_PASSWORD=
CONTROL_PLANE_URL=https://posvendelo.com
BACKEND_IMAGE=ghcr.io/uriel2121ger-art/posvendelo:latest
DEBUG=false
ENVEOF
  chmod 600 "\$ENV_FILE"
  log ".env generado con credenciales seguras."
else
  log ".env existente conservado."
fi

# Write docker-compose.yml (single-quoted heredoc so bash does NOT expand \${...})
cat > "\$COMPOSE_FILE" << 'DCEOF'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: posvendelo
      POSTGRES_USER: posvendelo_user
      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U posvendelo_user -d posvendelo"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    image: ghcr.io/uriel2121ger-art/posvendelo:latest
    env_file:
      - .env
    environment:
      DATABASE_URL: \${DATABASE_URL}
      JWT_SECRET: \${JWT_SECRET}
      ADMIN_API_USER: \${ADMIN_API_USER:-}
      ADMIN_API_PASSWORD: \${ADMIN_API_PASSWORD:-}
      CORS_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
      CORS_ALLOWED_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
      CONTROL_PLANE_URL: \${CONTROL_PLANE_URL:-https://posvendelo.com}
      POSVENDELO_AGENT_CONFIG_PATH: /runtime/posvendelo-agent.json
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./posvendelo-agent.json:/runtime/posvendelo-agent.json
      - /var/run/cups/cups.sock:/var/run/cups/cups.sock
      - /sys/class/dmi/id:/sys/class/dmi/id:ro
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
DCEOF

# Systemd service for auto-start on boot
cat > "\$SERVICE_FILE" << SVCEOF
[Unit]
Description=POSVENDELO POS Backend
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=\$INSTALL_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable posvendelo.service
log "Servicio systemd registrado."

# Copy agent config for Docker bind mount (auto-registration needs it)
AGENT_SRC="\$HOME/.config/posvendelo/posvendelo-agent.json"
if [ -f "\$AGENT_SRC" ]; then
  cp "\$AGENT_SRC" "\$INSTALL_DIR/posvendelo-agent.json"
  chmod 644 "\$INSTALL_DIR/posvendelo-agent.json"
elif [ -n "\$REAL_USER" ] && [ "\$REAL_USER" != "root" ]; then
  REAL_AGENT_SRC="\$(getent passwd "\$REAL_USER" | cut -d: -f6)/.config/posvendelo/posvendelo-agent.json"
  if [ -f "\$REAL_AGENT_SRC" ]; then
    cp "\$REAL_AGENT_SRC" "\$INSTALL_DIR/posvendelo-agent.json"
    chmod 644 "\$INSTALL_DIR/posvendelo-agent.json"
  fi
fi

# Pull image and start
log "Descargando backend (puede tardar varios minutos en la primera instalacion)..."
cd "\$INSTALL_DIR"
docker compose pull 2>&1 | tail -5 || {
  log "ADVERTENCIA: No se pudo descargar la imagen. El servicio iniciara cuando haya internet."
  exit 0
}
docker compose up -d
log "Contenedores iniciados."

# Wait for health (up to 60 s)
log "Esperando que el servidor este listo..."
for i in \$(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    log "Servidor listo."
    break
  fi
  sleep 2
done
`
}

function generateWindowsScript(): string {
  // All PowerShell $ variables must be escaped with \$ so TypeScript does not interpolate them.
  // The backtick inside PowerShell here-strings (\`\${...}) is the PS escape for literal ${...}
  // which docker-compose reads as env-var references.
  return [
    '#Requires -RunAsAdministrator',
    '$ErrorActionPreference = "Stop"',
    '$INSTALL_DIR = "$env:ProgramData\\POSVENDELO"',
    '$COMPOSE_FILE = "$INSTALL_DIR\\docker-compose.yml"',
    '$ENV_FILE = "$INSTALL_DIR\\.env"',
    '',
    'function Write-Step([string]$Message) {',
    '  Write-Host "[POSVENDELO] $Message" -ForegroundColor Cyan',
    '}',
    '',
    'function New-RandomHex([int]$Length) {',
    '  $bytes = New-Object byte[] ([Math]::Ceiling($Length / 2))',
    '  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)',
    '  return ([BitConverter]::ToString($bytes)).Replace("-", "").Substring(0, $Length).ToLower()',
    '}',
    '',
    '# Upgrade path',
    'if (Test-Path $COMPOSE_FILE) {',
    '  Write-Step "Compose existente — iniciando contenedores..."',
    '  Set-Location $INSTALL_DIR',
    '  docker compose up -d',
    '  exit 0',
    '}',
    '',
    'Write-Step "Instalando sistema completo..."',
    '',
    '# Install Docker',
    'if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {',
    '  if (Get-Command winget -ErrorAction SilentlyContinue) {',
    '    Write-Step "Instalando Docker Desktop via winget..."',
    '    winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements',
    '  } else {',
    '    Write-Step "Descargando Docker Desktop..."',
    '    $installer = "$env:TEMP\\DockerDesktopInstaller.exe"',
    '    Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -OutFile $installer',
    '    Start-Process -Wait -FilePath $installer -ArgumentList "install","--quiet","--accept-license"',
    '    Remove-Item $installer -Force',
    '  }',
    '  Start-Sleep 30',
    '}',
    '',
    'Write-Step "Verificando que Docker este listo..."',
    'for ($i = 0; $i -lt 45; $i++) {',
    '  try { docker version | Out-Null; break } catch { Start-Sleep 2 }',
    '}',
    '',
    'New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\\backups" | Out-Null',
    '',
    'if (-not (Test-Path $ENV_FILE)) {',
    '  $jwt = New-RandomHex 64',
    '  $dbpass = New-RandomHex 32',
    '  @"',
    'POSTGRES_PASSWORD=$dbpass',
    'DATABASE_URL=postgresql+asyncpg://posvendelo_user:$dbpass@postgres:5432/posvendelo',
    'JWT_SECRET=$jwt',
    'ADMIN_API_USER=',
    'ADMIN_API_PASSWORD=',
    'DEBUG=false',
    '"@ | Set-Content -Encoding UTF8 $ENV_FILE',
    '  Write-Step ".env generado."',
    '} else {',
    '  Write-Step ".env existente conservado."',
    '}',
    '',
    // The docker-compose content — PS backtick-dollar escapes ${...} for docker-compose
    '@"',
    'services:',
    '  postgres:',
    '    image: postgres:15-alpine',
    '    environment:',
    '      POSTGRES_DB: posvendelo',
    '      POSTGRES_USER: posvendelo_user',
    '      POSTGRES_PASSWORD: `${POSTGRES_PASSWORD}',
    '    volumes:',
    '      - pgdata:/var/lib/postgresql/data',
    '    healthcheck:',
    '      test: ["CMD-SHELL", "pg_isready -U posvendelo_user -d posvendelo"]',
    '      interval: 10s',
    '      timeout: 5s',
    '      retries: 5',
    '    restart: unless-stopped',
    '',
    '  api:',
    '    image: ghcr.io/uriel2121ger-art/posvendelo:latest',
    '    env_file:',
    '      - .env',
    '    environment:',
    '      DATABASE_URL: `${DATABASE_URL}',
    '      JWT_SECRET: `${JWT_SECRET}',
    '      ADMIN_API_USER: `${ADMIN_API_USER:-}',
    '      ADMIN_API_PASSWORD: `${ADMIN_API_PASSWORD:-}',
    '      CORS_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"',
    '      CORS_ALLOWED_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"',
    '    ports:',
    '      - "127.0.0.1:8000:8000"',
    '    depends_on:',
    '      postgres:',
    '        condition: service_healthy',
    '    restart: unless-stopped',
    '',
    'volumes:',
    '  pgdata:',
    '"@ | Set-Content -Encoding UTF8 $COMPOSE_FILE',
    '',
    'Set-Location $INSTALL_DIR',
    'Write-Step "Descargando backend..."',
    'docker compose pull',
    'docker compose up -d',
    '',
    'Write-Step "Esperando que el servidor este listo..."',
    'for ($i = 0; $i -lt 30; $i++) {',
    '  try {',
    '    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health" | Out-Null',
    '    Write-Step "Servidor listo."',
    '    exit 0',
    '  } catch { Start-Sleep 2 }',
    '}',
    'Write-Step "El servidor tardo mas de lo esperado. Abre POSVENDELO en unos minutos."',
  ].join('\n')
}

// ---------------------------------------------------------------------------
// Run a script elevated (pkexec on Linux, UAC via PowerShell on Windows)
// All paths are derived from app constants or tmp — no user-controlled input
// ---------------------------------------------------------------------------
function runElevated(scriptPath: string, callback: (success: boolean) => void): void {
  if (process.platform === 'win32') {
    // spawn uses argument array — shell injection is not possible here
    const child = spawn(
      'powershell',
      [
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        `Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \\"${scriptPath}\\"' -Verb RunAs -Wait`
      ],
      { stdio: 'ignore' }
    )
    child.on('close', (code) => callback(code === 0))
    child.on('error', () => callback(false))
  } else {
    // pkexec provides a graphical polkit prompt (GNOME / KDE / XFCE)
    // spawn with array avoids shell injection
    const child = spawn('pkexec', ['bash', scriptPath], { stdio: 'ignore' })
    child.on('close', (code) => callback(code === 0))
    child.on('error', () => {
      // Fallback: open a terminal with sudo (headless / minimal desktops)
      const child2 = spawn(
        'x-terminal-emulator',
        ['-e', `sudo bash "${scriptPath}"; read -p "Presiona Enter para continuar..."`],
        { stdio: 'ignore' }
      )
      child2.on('close', (code2) => callback(code2 === 0))
      child2.on('error', () => callback(false))
    })
  }
}
