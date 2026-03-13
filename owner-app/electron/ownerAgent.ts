import { app } from 'electron'
import { net } from 'electron'
import { spawn } from 'node:child_process'
import {
  chmodSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { createHash } from 'node:crypto'
import { homedir } from 'node:os'
import { basename, join } from 'node:path'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type OwnerAgentConfig = {
  controlPlaneUrl?: string
  installToken?: string
  releaseChannel?: string
  pollIntervalSeconds?: number
  installDir?: string
}

export type UpdateStatus = {
  status: 'idle' | 'checking' | 'available' | 'downloading' | 'staged' | 'applying' | 'error'
  currentVersion: string
  availableVersion: string | null
  checksumVerified: boolean
  message: string | null
  lastError: string | null
}

type ManifestArtifact = {
  version?: string
  target_ref?: string
  checksums_manifest_url?: string
}

type ReleaseManifest = {
  data?: {
    artifacts?: {
      owner_app?: ManifestArtifact
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function configPath(): string {
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA ?? join(homedir(), 'AppData', 'Local')
    return join(localAppData, 'POSVENDELO', 'posvendelo-agent.json')
  }
  return join(homedir(), '.config', 'posvendelo', 'posvendelo-agent.json')
}

function stagingDir(): string {
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA ?? join(homedir(), 'AppData', 'Local')
    return join(localAppData, 'POSVENDELO', 'owner-updates')
  }
  return join(homedir(), '.config', 'posvendelo', 'owner-updates')
}

function readConfig(): OwnerAgentConfig {
  try {
    const raw = readFileSync(configPath(), 'utf8')
    return JSON.parse(raw) as OwnerAgentConfig
  } catch {
    return {}
  }
}

function normalizeVersion(value: string | null | undefined): number[] {
  return String(value ?? '')
    .trim()
    .replace(/^v/i, '')
    .split(/[.\-+]/)
    .map((p) => Number.parseInt(p, 10))
    .filter((p) => Number.isFinite(p))
}

function isVersionGreater(
  next: string | null | undefined,
  current: string | null | undefined,
): boolean {
  const left = normalizeVersion(next)
  const right = normalizeVersion(current)
  const max = Math.max(left.length, right.length)
  for (let i = 0; i < max; i++) {
    const a = left[i] ?? 0
    const b = right[i] ?? 0
    if (a === b) continue
    return a > b
  }
  return false
}

function parseChecksumManifest(content: string, filename: string): string | null {
  const variants = new Set<string>([filename, `./${filename}`])
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(/^([A-Fa-f0-9]{64})\s+\*?(.+)$/)
    if (!match) continue
    const candidate = match[2].trim()
    if (variants.has(candidate) || basename(candidate) === filename) {
      return match[1].toLowerCase()
    }
  }
  return null
}

function shellQuote(s: string): string {
  return `'${s.replace(/'/g, "'\\''")}'`
}

async function netFetchText(url: string): Promise<string> {
  const response = await net.fetch(url)
  if (!response.ok) throw new Error(`HTTP ${response.status} al obtener ${url}`)
  return response.text()
}

async function netFetchBuffer(url: string): Promise<Buffer> {
  const response = await net.fetch(url)
  if (!response.ok) throw new Error(`HTTP ${response.status} al descargar ${url}`)
  return Buffer.from(await response.arrayBuffer())
}

// ---------------------------------------------------------------------------
// OwnerUpdateAgent
// ---------------------------------------------------------------------------

export class OwnerUpdateAgent {
  private config: OwnerAgentConfig
  private status: UpdateStatus
  private stagedPath: string | null = null
  private pollTimer: NodeJS.Timeout | null = null

  constructor(appVersion: string) {
    this.config = readConfig()
    this.status = {
      status: 'idle',
      currentVersion: appVersion,
      availableVersion: null,
      checksumVerified: false,
      message: null,
      lastError: null,
    }
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  start(): void {
    const intervalSeconds = Math.max(60, this.config.pollIntervalSeconds ?? 300)
    // Initial check after 10 s to not block startup
    setTimeout(() => {
      void this.checkForUpdate()
    }, 10_000)

    this.pollTimer = setInterval(() => {
      void this.checkForUpdate()
    }, intervalSeconds * 1000)
  }

  stop(): void {
    if (this.pollTimer !== null) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  }

  getStatus(): UpdateStatus {
    return { ...this.status }
  }

  async checkForUpdate(): Promise<UpdateStatus> {
    const manifestUrl = this.buildManifestUrl()
    if (!manifestUrl) {
      this.status = {
        ...this.status,
        status: 'idle',
        message: 'Control-plane no configurado',
        lastError: null,
      }
      return this.getStatus()
    }

    this.status = { ...this.status, status: 'checking', message: 'Verificando actualizaciones...', lastError: null }

    try {
      const text = await netFetchText(manifestUrl)
      const manifest = JSON.parse(text) as ReleaseManifest
      const artifact = manifest?.data?.artifacts?.owner_app

      if (!artifact?.version || !artifact?.target_ref) {
        this.status = { ...this.status, status: 'idle', message: 'Sin artefacto owner_app en manifest', lastError: null }
        return this.getStatus()
      }

      if (isVersionGreater(artifact.version, this.status.currentVersion)) {
        this.status = {
          ...this.status,
          status: 'available',
          availableVersion: artifact.version,
          message: `Actualización disponible: ${artifact.version}`,
          lastError: null,
        }
      } else {
        this.status = {
          ...this.status,
          status: 'idle',
          availableVersion: artifact.version,
          message: 'La aplicación está al día',
          lastError: null,
        }
      }
    } catch (error) {
      this.status = {
        ...this.status,
        status: 'error',
        message: 'Error al verificar actualizaciones',
        lastError: error instanceof Error ? error.message : String(error),
      }
    }

    return this.getStatus()
  }

  async downloadUpdate(): Promise<UpdateStatus> {
    if (this.status.status !== 'available') {
      this.status = { ...this.status, status: 'error', message: 'No hay actualización disponible para descargar', lastError: null }
      return this.getStatus()
    }

    const manifestUrl = this.buildManifestUrl()
    if (!manifestUrl) {
      this.status = { ...this.status, status: 'error', message: 'Control-plane no configurado', lastError: null }
      return this.getStatus()
    }

    this.status = { ...this.status, status: 'downloading', message: 'Descargando actualización...', lastError: null }

    try {
      const text = await netFetchText(manifestUrl)
      const manifest = JSON.parse(text) as ReleaseManifest
      const artifact = manifest?.data?.artifacts?.owner_app

      if (!artifact?.target_ref || !artifact?.version) {
        throw new Error('Artefacto owner_app no disponible en manifest')
      }

      this.assertTrustedUrl(artifact.target_ref)

      const dir = stagingDir()
      mkdirSync(dir, { recursive: true, mode: 0o700 })

      const filename = basename(new URL(artifact.target_ref).pathname)
      const destination = join(dir, filename)

      const buffer = await netFetchBuffer(artifact.target_ref)
      writeFileSync(destination, buffer)

      if (destination.toLowerCase().endsWith('.appimage')) {
        chmodSync(destination, 0o755)
      }

      // Verify SHA256 — required for security
      let checksumVerified = false
      if (artifact.checksums_manifest_url) {
        this.assertTrustedUrl(artifact.checksums_manifest_url)
        const sumsText = await netFetchText(artifact.checksums_manifest_url)
        const expected = parseChecksumManifest(sumsText, filename)
        if (expected) {
          const actual = createHash('sha256').update(buffer).digest('hex').toLowerCase()
          if (actual !== expected) {
            rmSync(destination, { force: true })
            throw new Error(`SHA256 no coincide para ${filename}`)
          }
          checksumVerified = true
        } else {
          rmSync(destination, { force: true })
          throw new Error(`No se encontró checksum para ${filename} en SHA256SUMS`)
        }
      } else {
        rmSync(destination, { force: true })
        throw new Error('Manifest no incluye checksums_manifest_url — descarga rechazada por seguridad')
      }

      this.stagedPath = destination

      this.status = {
        ...this.status,
        status: 'staged',
        availableVersion: artifact.version,
        checksumVerified,
        message: `Descargado y verificado: ${filename}`,
        lastError: null,
      }
    } catch (error) {
      this.status = {
        ...this.status,
        status: 'error',
        message: 'Error al descargar actualización',
        lastError: error instanceof Error ? error.message : String(error),
      }
    }

    return this.getStatus()
  }

  async applyUpdate(): Promise<void> {
    if (this.status.status !== 'staged' || !this.stagedPath) {
      this.status = { ...this.status, status: 'error', message: 'No hay actualización descargada para aplicar', lastError: null }
      return
    }

    const stagedPath = this.stagedPath
    this.status = { ...this.status, status: 'applying', message: 'Aplicando actualización...', lastError: null }

    try {
      if (process.platform === 'linux' && stagedPath.toLowerCase().endsWith('.appimage')) {
        await this.applyAppImage(stagedPath)
      } else if (process.platform === 'win32' && stagedPath.toLowerCase().endsWith('.exe')) {
        this.applyWindowsInstaller(stagedPath)
      } else {
        throw new Error(`Estrategia de instalación no soportada para: ${basename(stagedPath)}`)
      }
    } catch (error) {
      this.status = {
        ...this.status,
        status: 'error',
        message: 'Error al aplicar la actualización',
        lastError: error instanceof Error ? error.message : String(error),
      }
    }
  }

  discardUpdate(): void {
    if (this.stagedPath && existsSync(this.stagedPath)) {
      try {
        rmSync(this.stagedPath, { force: true })
      } catch {
        // ignore
      }
    }
    this.stagedPath = null
    this.status = {
      ...this.status,
      status: this.status.availableVersion ? 'available' : 'idle',
      message: 'Descarga descartada',
      lastError: null,
    }
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  private buildManifestUrl(): string | null {
    const cp = this.config.controlPlaneUrl?.trim()
    if (!cp) return null
    const base = cp.replace(/\/$/, '')
    const token = this.config.installToken
    if (token) {
      return `${base}/api/v1/releases/manifest?install_token=${encodeURIComponent(token)}`
    }
    return `${base}/api/v1/releases/manifest`
  }

  private assertTrustedUrl(url: string): void {
    const TRUSTED = new Set([
      'github.com',
      'objects.githubusercontent.com',
      'ghcr.io',
      'pkg-containers.githubusercontent.com',
    ])
    let hostname: string
    try {
      hostname = new URL(url).hostname.toLowerCase()
    } catch {
      throw new Error(`URL de descarga inválida: ${url}`)
    }
    if (TRUSTED.has(hostname)) return
    const cp = this.config.controlPlaneUrl?.trim()
    if (cp) {
      try {
        const cpHost = new URL(cp).hostname.toLowerCase()
        if (hostname === cpHost) return
      } catch { /* ignore */ }
    }
    throw new Error(`Dominio no confiable para descarga: ${hostname}`)
  }

  private async applyAppImage(stagedPath: string): Promise<void> {
    const currentExe = app.getPath('exe')
    const dir = stagingDir()
    const scriptPath = join(dir, 'apply-owner-update.sh')
    const pid = process.pid

    const script = `#!/usr/bin/env bash
set -euo pipefail
STAGED=${shellQuote(stagedPath)}
TARGET=${shellQuote(currentExe)}
PID_TO_WAIT=${pid}

for _ in $(seq 1 120); do
  if ! kill -0 "$PID_TO_WAIT" 2>/dev/null; then
    break
  fi
  sleep 1
done

mv "$STAGED" "$TARGET"
chmod +x "$TARGET"
nohup "$TARGET" >/dev/null 2>&1 &
`
    writeFileSync(scriptPath, script, 'utf8')
    chmodSync(scriptPath, 0o755)

    this.status = {
      ...this.status,
      status: 'applying',
      message: 'Aplicando actualización AppImage y reiniciando...',
      lastError: null,
    }
    this.stagedPath = null

    spawn('/bin/bash', [scriptPath], { detached: true, stdio: 'ignore' }).unref()
    app.quit()
  }

  private applyWindowsInstaller(stagedPath: string): void {
    this.status = {
      ...this.status,
      status: 'applying',
      message: 'Iniciando instalador silencioso de Windows...',
      lastError: null,
    }
    this.stagedPath = null

    spawn(stagedPath, ['/S', '/NORESTART'], {
      detached: true,
      stdio: 'ignore',
    }).unref()

    app.quit()
  }
}
