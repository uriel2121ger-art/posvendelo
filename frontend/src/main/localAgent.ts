import { app, shell } from 'electron'
import { spawn } from 'node:child_process'
import {
  chmodSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync
} from 'node:fs'
import { createHash, createVerify } from 'node:crypto'
import { homedir } from 'node:os'
import { basename, join } from 'node:path'

type AgentConfig = {
  controlPlaneUrl?: string
  branchId?: number
  installToken?: string
  releaseManifestUrl?: string
  licenseResolveUrl?: string
  localApiUrl?: string
  backendHealthUrl?: string
  appArtifact?: string
  backendArtifact?: string
  releaseChannel?: string
  license?: AgentLicenseEnvelope | null
  bootstrap?: {
    bootstrapPublicKey?: string
    licenseResolveUrl?: string
  }
  pollIntervals?: {
    healthSeconds?: number
    manifestSeconds?: number
    licenseSeconds?: number
  }
}

type AgentLicenseEnvelope = {
  payload?: {
    license_type?: string
    effective_status?: string
    valid_until?: string | null
    support_until?: string | null
    branch_id?: number | null
    tenant_id?: number | null
    machine_id?: string | null
    grace_days?: number | null
    [key: string]: unknown
  }
  signature?: string
  public_key?: string
}

type AgentLicenseState = {
  present: boolean
  validSignature: boolean
  licenseType: string | null
  effectiveStatus: string
  validUntil: string | null
  supportUntil: string | null
  daysRemaining: number | null
  supportDaysRemaining: number | null
  message: string | null
}

type AgentReleaseArtifact = {
  version?: string
  target_ref?: string
  channel?: string
  artifact?: string
  platform?: string
  checksums_manifest_url?: string | null
  rollback_supported?: boolean
  rollout_strategy?: string | null
  rollback?: {
    version?: string
    target_ref?: string
    checksums_manifest_url?: string | null
    artifact?: string
    platform?: string
  } | null
}

type AgentReleaseManifest = {
  branch_id?: number
  branch_slug?: string
  release_channel?: string
  os_platform?: string
  artifacts?: {
    backend?: AgentReleaseArtifact | null
    app?: AgentReleaseArtifact | null
  }
}

type BackendHealthPayload = {
  success?: boolean
  data?: {
    version?: string | null
    branch_id?: string | number | null
  }
}

export type LocalAgentStatus = {
  startedAt: string
  configPath: string | null
  configLoaded: boolean
  controlPlaneUrl: string | null
  branchId: number | null
  installTokenPresent: boolean
  localApiUrl: string
  backendHealthy: boolean
  backendVersion: string | null
  currentAppVersion: string
  availableAppVersion: string | null
  availableBackendVersion: string | null
  appUpdateAvailable: boolean
  backendUpdateAvailable: boolean
  lastBackendCheckAt: string | null
  lastBackendError: string | null
  lastManifestCheckAt: string | null
  lastManifestError: string | null
  lastLicenseCheckAt: string | null
  lastLicenseError: string | null
  manifest: AgentReleaseManifest | null
  license: AgentLicenseState
  desktopUpdate: AgentDesktopUpdateState
}

type AgentDesktopUpdateState = {
  status: 'idle' | 'available' | 'downloading' | 'staged' | 'applying' | 'error'
  currentVersion: string | null
  availableVersion: string | null
  artifact: string | null
  targetRef: string | null
  downloadedPath: string | null
  downloadedFileName: string | null
  checksumVerified: boolean
  checksumSource: string | null
  preparedAt: string | null
  applyStrategy: 'installer' | 'appimage' | 'package' | 'unknown'
  rollbackExecutablePath: string | null
  rollbackAvailable: boolean
  rollbackVersion: string | null
  rollbackMessage: string | null
  message: string | null
  lastError: string | null
}

type AgentDesktopRollbackState = {
  previousVersion: string | null
  currentVersion: string | null
  backupPath: string
  targetPath: string
  appliedAt: string
}

function normalizeVersion(value: string | null | undefined): number[] {
  return String(value || '')
    .trim()
    .replace(/^v/i, '')
    .split(/[.\-+]/)
    .map((part) => Number.parseInt(part, 10))
    .filter((part) => Number.isFinite(part))
}

function isVersionGreater(next: string | null | undefined, current: string | null | undefined): boolean {
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

function parseJsonFile<T>(path: string): T | null {
  try {
    return JSON.parse(readFileSync(path, 'utf8')) as T
  } catch {
    return null
  }
}

function daysRemaining(value: string | null | undefined): number | null {
  if (!value) return null
  const ms = new Date(value).getTime() - Date.now()
  if (!Number.isFinite(ms)) return null
  return Math.floor(ms / 86_400_000)
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) =>
      a.localeCompare(b)
    )
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function verifyLicenseSignature(license: AgentLicenseEnvelope, fallbackKey?: string | null): boolean {
  const payload = license.payload
  const signature = license.signature
  const publicKey = license.public_key || fallbackKey
  if (!payload || !signature || !publicKey) return false
  try {
    const verifier = createVerify('RSA-SHA256')
    verifier.update(stableStringify(payload))
    verifier.end()
    return verifier.verify(publicKey, Buffer.from(signature, 'base64'))
  } catch {
    return false
  }
}

function buildLicenseMessage(state: AgentLicenseState): string | null {
  if (!state.present) return 'Licencia no configurada'
  if (!state.validSignature) return 'Firma de licencia inválida'
  if (state.effectiveStatus === 'grace') return 'Licencia mensual en gracia'
  if (state.effectiveStatus === 'expired' && state.licenseType === 'trial')
    return 'Trial vencido'
  if (state.effectiveStatus === 'expired') return 'Licencia vencida'
  if (state.effectiveStatus === 'support_expired') return 'Soporte vencido'
  if (state.daysRemaining !== null) return `${state.daysRemaining} día(s) restantes`
  return 'Licencia operativa'
}

function deriveLicenseState(config: AgentConfig | null): AgentLicenseState {
  const license = config?.license ?? null
  if (!license?.payload) {
    return {
      present: false,
      validSignature: false,
      licenseType: null,
      effectiveStatus: 'missing',
      validUntil: null,
      supportUntil: null,
      daysRemaining: null,
      supportDaysRemaining: null,
      message: 'Licencia no configurada'
    }
  }
  const validSignature = verifyLicenseSignature(license, config?.bootstrap?.bootstrapPublicKey ?? null)
  const state: AgentLicenseState = {
    present: true,
    validSignature,
    licenseType: typeof license.payload.license_type === 'string' ? license.payload.license_type : null,
    effectiveStatus:
      typeof license.payload.effective_status === 'string'
        ? license.payload.effective_status
        : 'active',
    validUntil: typeof license.payload.valid_until === 'string' ? license.payload.valid_until : null,
    supportUntil:
      typeof license.payload.support_until === 'string' ? license.payload.support_until : null,
    daysRemaining: daysRemaining(
      typeof license.payload.valid_until === 'string' ? license.payload.valid_until : null
    ),
    supportDaysRemaining: daysRemaining(
      typeof license.payload.support_until === 'string' ? license.payload.support_until : null
    ),
    message: null
  }
  state.message = buildLicenseMessage(state)
  return state
}

function normalizeUrl(value: string | undefined): string | null {
  if (!value?.trim()) return null
  try {
    const parsed = new URL(value.trim())
    return parsed.toString().replace(/\/$/, '')
  } catch {
    return null
  }
}

function buildManifestUrl(config: AgentConfig): string | null {
  const explicit = normalizeUrl(config.releaseManifestUrl)
  if (explicit) return explicit

  const cp = normalizeUrl(config.controlPlaneUrl)
  if (!cp) return null
  if (config.installToken) {
    return `${cp}/api/v1/releases/manifest?install_token=${encodeURIComponent(config.installToken)}`
  }
  if (config.branchId) {
    return `${cp}/api/v1/releases/manifest?branch_id=${config.branchId}`
  }
  return null
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

function inferApplyStrategy(path: string | null): AgentDesktopUpdateState['applyStrategy'] {
  const lower = (path || '').toLowerCase()
  if (lower.endsWith('.appimage')) return 'appimage'
  if (lower.endsWith('.exe') || lower.endsWith('.msi') || lower.endsWith('.deb') || lower.endsWith('.rpm'))
    return 'installer'
  if (lower.endsWith('.zip') || lower.endsWith('.tar.gz') || lower.endsWith('.tgz')) return 'package'
  return 'unknown'
}

export class LocalNodeAgent {
  private configPath: string | null = null
  private config: AgentConfig | null = null
  private healthTimer: NodeJS.Timeout | null = null
  private manifestTimer: NodeJS.Timeout | null = null
  private licenseTimer: NodeJS.Timeout | null = null
  private startedAt = new Date().toISOString()
  private backendHealthy = false
  private lastBackendCheckAt: string | null = null
  private lastBackendError: string | null = null
  private lastManifestCheckAt: string | null = null
  private lastManifestError: string | null = null
  private lastLicenseCheckAt: string | null = null
  private lastLicenseError: string | null = null
  private manifest: AgentReleaseManifest | null = null
  private backendVersion: string | null = null
  private desktopUpdateState: AgentDesktopUpdateState = {
    status: 'idle',
    currentVersion: null,
    availableVersion: null,
    artifact: null,
    targetRef: null,
    downloadedPath: null,
    downloadedFileName: null,
    checksumVerified: false,
    checksumSource: null,
    preparedAt: null,
    applyStrategy: 'unknown',
    rollbackExecutablePath: null,
    rollbackAvailable: false,
    rollbackVersion: null,
    rollbackMessage: null,
    message: null,
    lastError: null
  }

  start(): void {
    this.reloadConfig()
    this.loadDesktopUpdateState()
    void this.refreshNow()

    const healthSeconds = this.config?.pollIntervals?.healthSeconds ?? 15
    const manifestSeconds = this.config?.pollIntervals?.manifestSeconds ?? 300
    const licenseSeconds = this.config?.pollIntervals?.licenseSeconds ?? 300

    this.healthTimer = setInterval(
      () => {
        void this.refreshBackendHealth()
      },
      Math.max(5, healthSeconds) * 1000
    )

    this.manifestTimer = setInterval(
      () => {
        void this.refreshManifest()
      },
      Math.max(30, manifestSeconds) * 1000
    )

    this.licenseTimer = setInterval(
      () => {
        void this.refreshLicense()
      },
      Math.max(30, licenseSeconds) * 1000
    )
  }

  stop(): void {
    if (this.healthTimer) clearInterval(this.healthTimer)
    if (this.manifestTimer) clearInterval(this.manifestTimer)
    if (this.licenseTimer) clearInterval(this.licenseTimer)
    this.healthTimer = null
    this.manifestTimer = null
    this.licenseTimer = null
  }

  reloadConfig(): void {
    for (const candidate of this.configCandidates()) {
      if (!existsSync(candidate)) continue
      const next = parseJsonFile<AgentConfig>(candidate)
      if (!next) continue
      const externalLicensePath = join(candidate.replace(/titan-agent\.json$/i, ''), 'titan-license.json')
      if (existsSync(externalLicensePath)) {
        const externalLicense = parseJsonFile<AgentLicenseEnvelope>(externalLicensePath)
        if (externalLicense?.payload) {
          next.license = externalLicense
        }
      }
      this.config = next
      this.configPath = candidate
      return
    }
    this.config = null
    this.configPath = null
  }

  async prepareAppUpdate(): Promise<LocalAgentStatus> {
    this.reloadConfig()
    await this.refreshManifest()
    const release = this.manifest?.artifacts?.app ?? null
    const currentVersion = app.getVersion()
    if (!release?.target_ref || !release.version) {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'error',
        currentVersion,
        availableVersion: release?.version ?? null,
        artifact: release?.artifact ?? this.config?.appArtifact ?? null,
        targetRef: release?.target_ref ?? null,
        message: 'No hay artefacto de app publicado para este nodo.',
        lastError: 'app artifact missing'
      }
      this.saveDesktopUpdateState()
      return this.getStatus()
    }
    if (!isVersionGreater(release.version, currentVersion)) {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'idle',
        currentVersion,
        availableVersion: release.version,
        artifact: release.artifact ?? this.config?.appArtifact ?? null,
        targetRef: release.target_ref,
        message: 'La app ya está en la versión más reciente.',
        lastError: null
      }
      this.saveDesktopUpdateState()
      return this.getStatus()
    }

    const updatesDir = this.desktopUpdatesDir()
    mkdirSync(updatesDir, { recursive: true })
    const filename = basename(new URL(release.target_ref).pathname) || `titan-pos-${release.version}`
    const destination = join(updatesDir, filename)
    const rollbackExecutablePath = app.isPackaged ? app.getPath('exe') : process.execPath

    this.desktopUpdateState = {
      ...this.desktopUpdateState,
      status: 'downloading',
      currentVersion,
      availableVersion: release.version,
      artifact: release.artifact ?? this.config?.appArtifact ?? null,
      targetRef: release.target_ref,
      downloadedPath: destination,
      downloadedFileName: filename,
      checksumVerified: false,
      checksumSource: null,
      preparedAt: null,
      applyStrategy: inferApplyStrategy(destination),
      rollbackExecutablePath,
      message: 'Descargando actualización de app...',
      lastError: null
    }
    this.saveDesktopUpdateState()

    try {
      const response = await fetch(release.target_ref, { signal: AbortSignal.timeout(120_000) })
      if (!response.ok) {
        throw new Error(`No se pudo descargar update app (${response.status})`)
      }
      const buffer = Buffer.from(await response.arrayBuffer())
      writeFileSync(destination, buffer)
      if (destination.toLowerCase().endsWith('.appimage')) {
        chmodSync(destination, 0o755)
      }

      let checksumVerified = false
      let checksumSource: string | null = null
      const expectedSha = await this.fetchExpectedSha256(
        release.target_ref,
        release.checksums_manifest_url ?? null
      ).catch(() => null)
      if (expectedSha) {
        const actualSha = this.computeSha256(destination)
        if (actualSha !== expectedSha) {
          throw new Error('SHA256 del update app no coincide con el manifest publicado')
        }
        checksumVerified = true
        checksumSource = release.checksums_manifest_url ?? this.buildChecksumUrl(release.target_ref)
      }

      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'staged',
        checksumVerified,
        checksumSource,
        preparedAt: new Date().toISOString(),
        applyStrategy: inferApplyStrategy(destination),
        message: 'Actualización descargada. Lista para aplicar.',
        lastError: null
      }
      this.saveDesktopUpdateState()
    } catch (error) {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'error',
        message: 'No se pudo preparar la actualización de app.',
        lastError: error instanceof Error ? error.message : String(error)
      }
      this.saveDesktopUpdateState()
    }

    return this.getStatus()
  }

  async applyStagedAppUpdate(): Promise<LocalAgentStatus> {
    this.loadDesktopUpdateState()
    const stagedPath = this.desktopUpdateState.downloadedPath
    if (!stagedPath || !existsSync(stagedPath)) {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'error',
        message: 'No hay actualización descargada para aplicar.',
        lastError: 'staged update missing'
      }
      this.saveDesktopUpdateState()
      return this.getStatus()
    }
    this.desktopUpdateState = {
      ...this.desktopUpdateState,
      status: 'applying',
      message: 'Abriendo instalador/artefacto del update.',
      lastError: null
    }
    this.saveDesktopUpdateState()
    if (process.platform === 'linux' && this.desktopUpdateState.applyStrategy === 'appimage' && app.isPackaged) {
      try {
        const currentExe = app.getPath('exe')
        const rollbackPath = join(
          this.desktopUpdatesDir(),
          `rollback-${(this.desktopUpdateState.currentVersion || 'current').replace(/[^a-z0-9._-]/gi, '_')}.AppImage`
        )
        const scriptPath = join(this.desktopUpdatesDir(), 'apply-appimage-update.sh')
        const rollbackMetadataPath = this.desktopRollbackStatePath()
        const script = `#!/usr/bin/env bash
set -euo pipefail
TARGET=${this.shellQuote(currentExe)}
STAGED=${this.shellQuote(stagedPath)}
BACKUP=${this.shellQuote(rollbackPath)}
META=${this.shellQuote(rollbackMetadataPath)}
PID_TO_WAIT=${process.pid}

for _ in $(seq 1 120); do
  if ! kill -0 "$PID_TO_WAIT" 2>/dev/null; then
    break
  fi
  sleep 1
done

cp "$TARGET" "$BACKUP"
mv "$STAGED" "$TARGET"
chmod +x "$TARGET"
cat > "$META" <<'EOF'
${JSON.stringify(
  {
    previousVersion: this.desktopUpdateState.currentVersion,
    currentVersion: this.desktopUpdateState.availableVersion,
    backupPath: rollbackPath,
    targetPath: currentExe,
    appliedAt: new Date().toISOString()
  },
  null,
  2
)}
EOF
nohup "$TARGET" >/dev/null 2>&1 &
`
        writeFileSync(scriptPath, script, 'utf8')
        chmodSync(scriptPath, 0o755)
        this.desktopUpdateState = {
          ...this.desktopUpdateState,
          rollbackExecutablePath: rollbackPath,
          rollbackAvailable: true,
          rollbackVersion: this.desktopUpdateState.currentVersion,
          rollbackMessage: 'Rollback local disponible mientras exista el backup AppImage.',
          message: 'Aplicando update AppImage y reiniciando app...'
        }
        this.saveDesktopUpdateState()
        spawn('/bin/bash', [scriptPath], {
          detached: true,
          stdio: 'ignore'
        }).unref()
        app.quit()
        return this.getStatus()
      } catch (error) {
        this.desktopUpdateState = {
          ...this.desktopUpdateState,
          status: 'error',
          message: 'No se pudo aplicar el update AppImage.',
          lastError: error instanceof Error ? error.message : String(error)
        }
        this.saveDesktopUpdateState()
        return this.getStatus()
      }
    }
    const openError = await shell.openPath(stagedPath)
    if (openError) {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'error',
        message: 'No se pudo abrir el update descargado.',
        lastError: openError
      }
      this.saveDesktopUpdateState()
    } else {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        rollbackMessage:
          'Update abierto con instalador externo. Si falla, repinnea una versión previa desde control-plane.',
        rollbackAvailable: false
      }
      this.saveDesktopUpdateState()
    }
    return this.getStatus()
  }

  async discardAppUpdate(): Promise<LocalAgentStatus> {
    this.loadDesktopUpdateState()
    const stagedPath = this.desktopUpdateState.downloadedPath
    if (stagedPath && existsSync(stagedPath)) {
      rmSync(stagedPath, { force: true })
    }
    this.desktopUpdateState = {
      status: 'idle',
      currentVersion: app.getVersion(),
      availableVersion: this.manifest?.artifacts?.app?.version ?? null,
      artifact: this.manifest?.artifacts?.app?.artifact ?? this.config?.appArtifact ?? null,
      targetRef: this.manifest?.artifacts?.app?.target_ref ?? null,
      downloadedPath: null,
      downloadedFileName: null,
      checksumVerified: false,
      checksumSource: null,
      preparedAt: null,
      applyStrategy: 'unknown',
      rollbackExecutablePath: null,
      rollbackAvailable: this.desktopUpdateState.rollbackAvailable,
      rollbackVersion: this.desktopUpdateState.rollbackVersion,
      rollbackMessage: this.desktopUpdateState.rollbackMessage,
      message: 'Actualización descartada.',
      lastError: null
    }
    this.saveDesktopUpdateState()
    return this.getStatus()
  }

  async rollbackLastAppUpdate(): Promise<LocalAgentStatus> {
    this.loadDesktopUpdateState()
    const rollback = parseJsonFile<AgentDesktopRollbackState>(this.desktopRollbackStatePath())
    if (!rollback?.backupPath || !rollback.targetPath || !existsSync(rollback.backupPath)) {
      this.desktopUpdateState = {
        ...this.desktopUpdateState,
        status: 'error',
        rollbackAvailable: false,
        rollbackMessage: null,
        message: 'No hay rollback local disponible.',
        lastError: 'rollback metadata missing'
      }
      this.saveDesktopUpdateState()
      return this.getStatus()
    }
    if (process.platform === 'linux' && rollback.targetPath.toLowerCase().endsWith('.appimage')) {
      try {
        const scriptPath = join(this.desktopUpdatesDir(), 'rollback-appimage-update.sh')
        const metadataPath = this.desktopRollbackStatePath()
        const script = `#!/usr/bin/env bash
set -euo pipefail
TARGET=${this.shellQuote(rollback.targetPath)}
BACKUP=${this.shellQuote(rollback.backupPath)}
META=${this.shellQuote(metadataPath)}
PID_TO_WAIT=${process.pid}

for _ in $(seq 1 120); do
  if ! kill -0 "$PID_TO_WAIT" 2>/dev/null; then
    break
  fi
  sleep 1
done

mv "$BACKUP" "$TARGET"
chmod +x "$TARGET"
rm -f "$META"
nohup "$TARGET" >/dev/null 2>&1 &
`
        writeFileSync(scriptPath, script, 'utf8')
        chmodSync(scriptPath, 0o755)
        this.desktopUpdateState = {
          ...this.desktopUpdateState,
          status: 'applying',
          message: 'Ejecutando rollback AppImage y reiniciando app...',
          lastError: null
        }
        this.saveDesktopUpdateState()
        spawn('/bin/bash', [scriptPath], {
          detached: true,
          stdio: 'ignore'
        }).unref()
        app.quit()
        return this.getStatus()
      } catch (error) {
        this.desktopUpdateState = {
          ...this.desktopUpdateState,
          status: 'error',
          message: 'No se pudo ejecutar el rollback local.',
          lastError: error instanceof Error ? error.message : String(error)
        }
        this.saveDesktopUpdateState()
        return this.getStatus()
      }
    }

    const remoteRollback = this.manifest?.artifacts?.app?.rollback ?? null
    if (remoteRollback?.target_ref && remoteRollback.version) {
      try {
        const updatesDir = this.desktopUpdatesDir()
        mkdirSync(updatesDir, { recursive: true })
        const filename =
          basename(new URL(remoteRollback.target_ref).pathname) ||
          `titan-pos-rollback-${remoteRollback.version}`
        const destination = join(updatesDir, `rollback-${filename}`)
        const response = await fetch(remoteRollback.target_ref, {
          signal: AbortSignal.timeout(120_000)
        })
        if (!response.ok) {
          throw new Error(`No se pudo descargar rollback remoto (${response.status})`)
        }
        const buffer = Buffer.from(await response.arrayBuffer())
        writeFileSync(destination, buffer)
        if (destination.toLowerCase().endsWith('.appimage')) {
          chmodSync(destination, 0o755)
        }
        const expectedSha = await this.fetchExpectedSha256(
          remoteRollback.target_ref,
          remoteRollback.checksums_manifest_url ?? null
        ).catch(() => null)
        if (expectedSha) {
          const actualSha = this.computeSha256(destination)
          if (actualSha !== expectedSha) {
            throw new Error('SHA256 del rollback remoto no coincide con el manifest publicado')
          }
        }
        const openError = await shell.openPath(destination)
        if (openError) {
          throw new Error(openError)
        }
        this.desktopUpdateState = {
          ...this.desktopUpdateState,
          status: 'applying',
          rollbackAvailable: false,
          rollbackVersion: remoteRollback.version,
          rollbackMessage: 'Rollback remoto abierto con instalador/artefacto previo.',
          message: 'Abriendo rollback remoto...',
          lastError: null
        }
        this.saveDesktopUpdateState()
        return this.getStatus()
      } catch (error) {
        this.desktopUpdateState = {
          ...this.desktopUpdateState,
          status: 'error',
          message: 'No se pudo ejecutar el rollback remoto.',
          lastError: error instanceof Error ? error.message : String(error)
        }
        this.saveDesktopUpdateState()
        return this.getStatus()
      }
    }

    this.desktopUpdateState = {
      ...this.desktopUpdateState,
      status: 'error',
      message: 'Este tipo de update no soporta rollback local automático.',
      lastError: 'rollback unsupported for apply strategy'
    }
    this.saveDesktopUpdateState()
    return this.getStatus()
  }

  getStatus(): LocalAgentStatus {
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    const localApiUrl = normalizeUrl(this.config?.localApiUrl) ?? 'http://127.0.0.1:8000'
    const currentAppVersion = app.getVersion()
    const availableAppVersion = this.manifest?.artifacts?.app?.version ?? null
    const availableBackendVersion = this.manifest?.artifacts?.backend?.version ?? null
    const license = deriveLicenseState(this.config)
    const appUpdateAvailable = isVersionGreater(availableAppVersion, currentAppVersion)
    const desktopUpdate = this.deriveDesktopUpdateState(currentAppVersion, availableAppVersion, appUpdateAvailable)
    return {
      startedAt: this.startedAt,
      configPath: this.configPath,
      configLoaded: Boolean(this.config),
      controlPlaneUrl,
      branchId: this.config?.branchId ?? null,
      installTokenPresent: Boolean(this.config?.installToken),
      localApiUrl,
      backendHealthy: this.backendHealthy,
      backendVersion: this.backendVersion,
      currentAppVersion,
      availableAppVersion,
      availableBackendVersion,
      appUpdateAvailable,
      backendUpdateAvailable: isVersionGreater(availableBackendVersion, this.backendVersion),
      lastBackendCheckAt: this.lastBackendCheckAt,
      lastBackendError: this.lastBackendError,
      lastManifestCheckAt: this.lastManifestCheckAt,
      lastManifestError: this.lastManifestError,
      lastLicenseCheckAt: this.lastLicenseCheckAt,
      lastLicenseError: this.lastLicenseError,
      manifest: this.manifest,
      license,
      desktopUpdate
    }
  }

  async refreshNow(): Promise<LocalAgentStatus> {
    this.reloadConfig()
    await Promise.all([this.refreshBackendHealth(), this.refreshManifest(), this.refreshLicense()])
    return this.getStatus()
  }

  private configCandidates(): string[] {
    const custom = process.env.TITAN_AGENT_CONFIG_PATH?.trim()
    const userData = join(app.getPath('userData'), 'titan-agent.json')
    const home = join(homedir(), '.titanpos', 'titan-agent.json')
    const localAppData = process.env.LOCALAPPDATA
      ? join(process.env.LOCALAPPDATA, 'TitanPOS', 'titan-agent.json')
      : null
    return [custom, userData, home, localAppData].filter((value): value is string => Boolean(value))
  }

  private async refreshBackendHealth(): Promise<void> {
    const localApiUrl = normalizeUrl(this.config?.localApiUrl) ?? 'http://127.0.0.1:8000'
    const healthUrl = normalizeUrl(this.config?.backendHealthUrl) ?? `${localApiUrl}/health`
    this.lastBackendCheckAt = new Date().toISOString()
    try {
      const response = await fetch(healthUrl, { signal: AbortSignal.timeout(5000) })
      this.backendHealthy = response.ok
      if (!response.ok) {
        this.lastBackendError = `HTTP ${response.status}`
        return
      }
      const body = (await response.json()) as BackendHealthPayload
      this.backendVersion = body.data?.version?.trim() || null
      this.lastBackendError = null
    } catch (error) {
      this.backendHealthy = false
      this.backendVersion = null
      this.lastBackendError = error instanceof Error ? error.message : String(error)
    }
  }

  private async refreshManifest(): Promise<void> {
    const manifestUrl = this.config ? buildManifestUrl(this.config) : null
    if (!manifestUrl) return

    this.lastManifestCheckAt = new Date().toISOString()
    try {
      const response = await fetch(manifestUrl, { signal: AbortSignal.timeout(7000) })
      if (!response.ok) {
        this.lastManifestError = `HTTP ${response.status}`
        return
      }
      const body = (await response.json()) as { success?: boolean; data?: AgentReleaseManifest }
      this.manifest = body.data ?? null
      this.lastManifestError = body.success === false ? 'manifest rejected' : null
      this.saveDesktopUpdateState()
    } catch (error) {
      this.lastManifestError = error instanceof Error ? error.message : String(error)
    }
  }

  private async refreshLicense(): Promise<void> {
    const installToken = this.config?.installToken
    const explicitResolveUrl = normalizeUrl(this.config?.licenseResolveUrl || this.config?.bootstrap?.licenseResolveUrl)
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    const resolveUrl =
      explicitResolveUrl ||
      (controlPlaneUrl && installToken
        ? `${controlPlaneUrl}/api/v1/licenses/resolve?install_token=${encodeURIComponent(installToken)}`
        : null)
    if (!resolveUrl || !installToken || !this.configPath || !this.config) return

    this.lastLicenseCheckAt = new Date().toISOString()
    try {
      const machineId =
        this.config.license?.payload?.machine_id ||
        process.env.COMPUTERNAME ||
        process.env.HOSTNAME ||
        null
      const params = new URLSearchParams()
      params.set('install_token', installToken)
      if (machineId) params.set('machine_id', machineId)
      params.set('os_platform', process.platform)
      params.set('app_version', app.getVersion())
      const targetUrl = resolveUrl.includes('?')
        ? `${resolveUrl}&${params.toString().split('&').slice(1).join('&')}`
        : `${resolveUrl}?${params.toString()}`
      const response = await fetch(targetUrl, { signal: AbortSignal.timeout(7000) })
      if (!response.ok) {
        this.lastLicenseError = `HTTP ${response.status}`
        return
      }
      const body = (await response.json()) as {
        success?: boolean
        data?: { license?: AgentLicenseEnvelope }
      }
      if (body.data?.license) {
        this.config.license = body.data.license
        if (!this.config.bootstrap) this.config.bootstrap = {}
        if (body.data.license.public_key) {
          this.config.bootstrap.bootstrapPublicKey = body.data.license.public_key
        }
        writeFileSync(this.configPath, JSON.stringify(this.config, null, 2), 'utf8')
      }
      this.lastLicenseError = body.success === false ? 'license rejected' : null
    } catch (error) {
      this.lastLicenseError = error instanceof Error ? error.message : String(error)
    }
  }

  private desktopUpdatesDir(): string {
    return join(app.getPath('userData'), 'updates')
  }

  private desktopUpdateStatePath(): string {
    return join(this.desktopUpdatesDir(), 'desktop-update.json')
  }

  private loadDesktopUpdateState(): void {
    const saved = parseJsonFile<AgentDesktopUpdateState>(this.desktopUpdateStatePath())
    if (!saved) return
    this.desktopUpdateState = saved
  }

  private saveDesktopUpdateState(): void {
    mkdirSync(this.desktopUpdatesDir(), { recursive: true })
    writeFileSync(this.desktopUpdateStatePath(), JSON.stringify(this.desktopUpdateState, null, 2), 'utf8')
  }

  private desktopRollbackStatePath(): string {
    return join(this.desktopUpdatesDir(), 'desktop-rollback.json')
  }

  private deriveDesktopUpdateState(
    currentVersion: string,
    availableVersion: string | null,
    appUpdateAvailable: boolean
  ): AgentDesktopUpdateState {
    const current = this.desktopUpdateState
    if (current.status === 'staged' || current.status === 'downloading' || current.status === 'applying') {
      return {
        ...current,
        currentVersion,
        availableVersion,
        rollbackAvailable: current.rollbackAvailable || this.hasRollbackMetadata()
      }
    }
    if (current.status === 'error') {
      return {
        ...current,
        currentVersion,
        availableVersion,
        rollbackAvailable: current.rollbackAvailable || this.hasRollbackMetadata()
      }
    }
    if (appUpdateAvailable) {
      return {
        ...current,
        status: 'available',
        currentVersion,
        availableVersion,
        artifact: this.manifest?.artifacts?.app?.artifact ?? this.config?.appArtifact ?? null,
        targetRef: this.manifest?.artifacts?.app?.target_ref ?? null,
        rollbackAvailable: current.rollbackAvailable || this.hasRollbackMetadata(),
        message: 'Hay una actualización de app disponible.',
        lastError: current.lastError
      }
    }
    return {
      ...current,
      status: 'idle',
      currentVersion,
      availableVersion,
      artifact: this.manifest?.artifacts?.app?.artifact ?? this.config?.appArtifact ?? null,
      targetRef: this.manifest?.artifacts?.app?.target_ref ?? null,
      rollbackAvailable: current.rollbackAvailable || this.hasRollbackMetadata(),
      message: current.status === 'idle' ? current.message : null
    }
  }

  private hasRollbackMetadata(): boolean {
    const rollback = parseJsonFile<AgentDesktopRollbackState>(this.desktopRollbackStatePath())
    return Boolean(rollback?.backupPath && existsSync(rollback.backupPath))
  }

  private buildChecksumUrl(targetRef: string): string | null {
    try {
      const url = new URL(targetRef)
      const segments = url.pathname.split('/')
      segments[segments.length - 1] = 'SHA256SUMS.txt'
      url.pathname = segments.join('/')
      return url.toString()
    } catch {
      return null
    }
  }

  private async fetchExpectedSha256(
    targetRef: string,
    explicitChecksumUrl: string | null
  ): Promise<string | null> {
    const checksumUrl = explicitChecksumUrl || this.buildChecksumUrl(targetRef)
    if (!checksumUrl) return null
    const response = await fetch(checksumUrl, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) return null
    const content = await response.text()
    return parseChecksumManifest(content, basename(new URL(targetRef).pathname))
  }

  private computeSha256(path: string): string {
    const hash = createHash('sha256')
    hash.update(readFileSync(path))
    return hash.digest('hex')
  }

  private shellQuote(value: string): string {
    return `'${value.replace(/'/g, `'\"'\"'`)}'`
  }
}
