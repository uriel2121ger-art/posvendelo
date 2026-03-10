import { app, shell } from 'electron'
import { spawn } from 'node:child_process'
import { chmodSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createHash, createVerify } from 'node:crypto'
import { homedir } from 'node:os'
import { basename, dirname, join } from 'node:path'

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
    ownerSessionUrl?: string
    ownerApiBaseUrl?: string
    companionUrl?: string
    companionEntryUrl?: string
    quickLinks?: {
      owner_portfolio?: string
      owner_devices?: string
      owner_remote?: string
    }
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
  ownerSessionReady: boolean
  ownerAccessMode: 'owner-session' | 'install-token' | 'unavailable'
  companionUrl: string | null
  companionEntryUrl: string | null
  ownerSessionUrl: string | null
  ownerApiBaseUrl: string | null
  quickLinks: {
    ownerPortfolio: string | null
    ownerDevices: string | null
    ownerRemote: string | null
  }
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
  backendUpdate: AgentBackendUpdateState
}

export type OwnerPortfolioStatus = {
  controlPlaneUrl: string | null
  tenantName: string | null
  tenantSlug: string | null
  branchesTotal: number
  online: number
  offline: number
  salesTodayTotal: number
  alertsTotal: number
  branches: Array<Record<string, unknown>>
  alerts: Array<Record<string, unknown>>
  lastError: string | null
}

export type OwnerEventsStatus = {
  controlPlaneUrl: string | null
  events: Array<Record<string, unknown>>
  lastError: string | null
}

export type OwnerBranchTimelineStatus = {
  controlPlaneUrl: string | null
  branch: Record<string, unknown> | null
  timeline: Array<Record<string, unknown>>
  lastError: string | null
}

export type OwnerCommercialStatus = {
  controlPlaneUrl: string | null
  license: Record<string, unknown> | null
  health: Record<string, unknown> | null
  events: Array<Record<string, unknown>>
  lastError: string | null
}

export type OwnerHealthSummaryStatus = {
  controlPlaneUrl: string | null
  summary: Record<string, unknown> | null
  lastError: string | null
}

export type OwnerAuditStatus = {
  controlPlaneUrl: string | null
  audit: Array<Record<string, unknown>>
  lastError: string | null
}

export type BranchLinkCodeStatus = {
  controlPlaneUrl: string | null
  branchId: number | null
  branchName: string | null
  code: string | null
  expiresAt: string | null
  lastError: string | null
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

type AgentBackendUpdateState = {
  status: 'idle' | 'available' | 'applying' | 'error'
  currentVersion: string | null
  availableVersion: string | null
  artifact: string | null
  targetRef: string | null
  rollbackAvailable: boolean
  rollbackVersion: string | null
  rollbackMessage: string | null
  message: string | null
  lastError: string | null
}

type AgentBackendRollbackState = {
  previousImage: string
  previousVersion: string | null
  currentImage: string
  currentVersion: string | null
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

function isVersionGreater(
  next: string | null | undefined,
  current: string | null | undefined
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

function verifyLicenseSignature(
  license: AgentLicenseEnvelope,
  fallbackKey?: string | null
): boolean {
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
  if (state.effectiveStatus === 'expired' && state.licenseType === 'trial') return 'Trial vencido'
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
  const validSignature = verifyLicenseSignature(
    license,
    config?.bootstrap?.bootstrapPublicKey ?? null
  )
  const state: AgentLicenseState = {
    present: true,
    validSignature,
    licenseType:
      typeof license.payload.license_type === 'string' ? license.payload.license_type : null,
    effectiveStatus:
      typeof license.payload.effective_status === 'string'
        ? license.payload.effective_status
        : 'active',
    validUntil:
      typeof license.payload.valid_until === 'string' ? license.payload.valid_until : null,
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
  if (explicit) {
    try {
      const sanitized = new URL(explicit)
      sanitized.searchParams.delete('install_token')
      return sanitized.toString()
    } catch {
      return explicit
    }
  }

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

function buildControlPlaneHeaders(installToken: string | null): HeadersInit | undefined {
  if (!installToken) return undefined
  return {
    'X-Install-Token': installToken
  }
}

function buildOwnerSessionHeaders(ownerToken: string | null): HeadersInit | undefined {
  if (!ownerToken) return undefined
  return {
    'X-Owner-Token': ownerToken
  }
}

function decodeOwnerSessionExpiry(ownerToken: string | null): number | null {
  if (!ownerToken) return null
  const [payload] = ownerToken.split('.', 1)
  if (!payload) return null
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padding = '='.repeat((4 - (normalized.length % 4)) % 4)
    const decoded = JSON.parse(
      Buffer.from(`${normalized}${padding}`, 'base64').toString('utf8')
    ) as {
      exp?: number
    }
    return typeof decoded.exp === 'number' ? decoded.exp : null
  } catch {
    return null
  }
}

function stripInstallTokenFromUrl(rawUrl: string | null): string | null {
  if (!rawUrl) return null
  try {
    const parsed = new URL(rawUrl)
    parsed.searchParams.delete('install_token')
    return parsed.toString()
  } catch {
    return rawUrl
  }
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
  if (
    lower.endsWith('.exe') ||
    lower.endsWith('.msi') ||
    lower.endsWith('.deb') ||
    lower.endsWith('.rpm')
  )
    return 'installer'
  if (lower.endsWith('.zip') || lower.endsWith('.tar.gz') || lower.endsWith('.tgz'))
    return 'package'
  return 'unknown'
}

export class LocalNodeAgent {
  private configPath: string | null = null
  private config: AgentConfig | null = null
  private ownerSessionToken: string | null = null
  private ownerSessionExpiresAt: number | null = null
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
  private backendUpdateState: AgentBackendUpdateState = {
    status: 'idle',
    currentVersion: null,
    availableVersion: null,
    artifact: null,
    targetRef: null,
    rollbackAvailable: false,
    rollbackVersion: null,
    rollbackMessage: null,
    message: null,
    lastError: null
  }

  start(): void {
    this.reloadConfig()
    this.loadDesktopUpdateState()
    this.loadBackendUpdateState()
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
    const previousConfigPath = this.configPath
    const previousInstallToken = this.config?.installToken?.trim() || null
    for (const candidate of this.configCandidates()) {
      if (!existsSync(candidate)) continue
      const next = parseJsonFile<AgentConfig>(candidate)
      if (!next) continue
      const externalLicensePath = join(
        candidate.replace(/titan-agent\.json$/i, ''),
        'titan-license.json'
      )
      if (existsSync(externalLicensePath)) {
        const externalLicense = parseJsonFile<AgentLicenseEnvelope>(externalLicensePath)
        if (externalLicense?.payload) {
          next.license = externalLicense
        }
      }
      const nextInstallToken = next.installToken?.trim() || null
      if (previousConfigPath !== candidate || previousInstallToken !== nextInstallToken) {
        this.invalidateOwnerSession()
      }
      this.config = next
      this.configPath = candidate
      return
    }
    if (this.config || this.configPath) {
      this.invalidateOwnerSession()
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
    const filename =
      basename(new URL(release.target_ref).pathname) || `titan-pos-${release.version}`
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
    if (
      process.platform === 'linux' &&
      this.desktopUpdateState.applyStrategy === 'appimage' &&
      app.isPackaged
    ) {
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

  async applyBackendUpdate(): Promise<LocalAgentStatus> {
    this.reloadConfig()
    await this.refreshManifest()
    const release = this.manifest?.artifacts?.backend ?? null
    if (!release?.target_ref || !release.version) {
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'error',
        currentVersion: this.backendVersion,
        availableVersion: release?.version ?? null,
        artifact: release?.artifact ?? this.config?.backendArtifact ?? null,
        targetRef: release?.target_ref ?? null,
        message: 'No hay artefacto de backend publicado para este nodo.',
        lastError: 'backend artifact missing'
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }
    if (!isVersionGreater(release.version, this.backendVersion)) {
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'idle',
        currentVersion: this.backendVersion,
        availableVersion: release.version,
        artifact: release.artifact ?? this.config?.backendArtifact ?? null,
        targetRef: release.target_ref,
        rollbackAvailable:
          this.backendUpdateState.rollbackAvailable || this.hasBackendRollbackMetadata(),
        message: 'El servidor local ya está en la versión más reciente.',
        lastError: null
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }

    const installDir = this.installationDir()
    const envPath = installDir ? join(installDir, '.env') : null
    const composePath = installDir ? join(installDir, 'docker-compose.yml') : null
    if (
      !installDir ||
      !envPath ||
      !composePath ||
      !existsSync(envPath) ||
      !existsSync(composePath)
    ) {
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'error',
        currentVersion: this.backendVersion,
        availableVersion: release.version,
        artifact: release.artifact ?? this.config?.backendArtifact ?? null,
        targetRef: release.target_ref,
        message: 'No se encontró la instalación local del backend para aplicar la actualización.',
        lastError: 'install dir missing'
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }

    const envVars = this.readEnvFile(envPath)
    const previousImage = envVars.BACKEND_IMAGE || ''
    const previousVersion = this.backendVersion
    if (!previousImage) {
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'error',
        currentVersion: this.backendVersion,
        availableVersion: release.version,
        artifact: release.artifact ?? this.config?.backendArtifact ?? null,
        targetRef: release.target_ref,
        message: 'No se pudo determinar BACKEND_IMAGE actual del nodo.',
        lastError: 'BACKEND_IMAGE missing'
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }

    this.backendUpdateState = {
      ...this.backendUpdateState,
      status: 'applying',
      currentVersion: this.backendVersion,
      availableVersion: release.version,
      artifact: release.artifact ?? this.config?.backendArtifact ?? null,
      targetRef: release.target_ref,
      rollbackAvailable:
        this.backendUpdateState.rollbackAvailable || this.hasBackendRollbackMetadata(),
      message: 'Aplicando actualización del servidor local...',
      lastError: null
    }
    this.saveBackendUpdateState()

    try {
      this.writeEnvFile(envPath, { ...envVars, BACKEND_IMAGE: release.target_ref })
      await this.runDockerCompose(installDir, envPath, ['pull', 'api'])
      await this.runDockerCompose(installDir, envPath, ['up', '-d', 'api'])
      writeFileSync(
        this.backendRollbackStatePath(),
        JSON.stringify(
          {
            previousImage,
            previousVersion,
            currentImage: release.target_ref,
            currentVersion: release.version,
            appliedAt: new Date().toISOString()
          } satisfies AgentBackendRollbackState,
          null,
          2
        ),
        'utf8'
      )
      await this.refreshBackendHealth()
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'idle',
        currentVersion: this.backendVersion,
        availableVersion: release.version,
        rollbackAvailable: true,
        rollbackVersion: previousVersion,
        rollbackMessage: `Imagen previa lista para reversión: ${previousImage}`,
        message: 'Servidor local actualizado correctamente.',
        lastError: null
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    } catch (error) {
      this.writeEnvFile(envPath, { ...envVars, BACKEND_IMAGE: previousImage })
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'error',
        message: 'No se pudo actualizar el servidor local.',
        lastError: error instanceof Error ? error.message : String(error)
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }
  }

  async rollbackLastBackendUpdate(): Promise<LocalAgentStatus> {
    const rollback = parseJsonFile<AgentBackendRollbackState>(this.backendRollbackStatePath())
    const installDir = this.installationDir()
    const envPath = installDir ? join(installDir, '.env') : null
    const composePath = installDir ? join(installDir, 'docker-compose.yml') : null
    if (
      !rollback?.previousImage ||
      !installDir ||
      !envPath ||
      !composePath ||
      !existsSync(envPath) ||
      !existsSync(composePath)
    ) {
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'error',
        rollbackAvailable: false,
        rollbackMessage: null,
        message: 'No hay reversión del backend disponible en este nodo.',
        lastError: 'backend rollback unavailable'
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }

    const envVars = this.readEnvFile(envPath)
    this.backendUpdateState = {
      ...this.backendUpdateState,
      status: 'applying',
      rollbackAvailable: true,
      rollbackVersion: rollback.previousVersion,
      rollbackMessage: `Revirtiendo a ${rollback.previousVersion ?? rollback.previousImage}`,
      message: 'Revirtiendo servidor local...',
      lastError: null
    }
    this.saveBackendUpdateState()

    try {
      this.writeEnvFile(envPath, { ...envVars, BACKEND_IMAGE: rollback.previousImage })
      await this.runDockerCompose(installDir, envPath, ['pull', 'api'])
      await this.runDockerCompose(installDir, envPath, ['up', '-d', 'api'])
      rmSync(this.backendRollbackStatePath(), { force: true })
      await this.refreshBackendHealth()
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'idle',
        currentVersion: this.backendVersion,
        rollbackAvailable: false,
        rollbackVersion: null,
        rollbackMessage: null,
        message: 'Servidor local revertido correctamente.',
        lastError: null
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    } catch (error) {
      this.backendUpdateState = {
        ...this.backendUpdateState,
        status: 'error',
        rollbackAvailable: true,
        rollbackVersion: rollback.previousVersion,
        rollbackMessage: `Imagen previa registrada: ${rollback.previousImage}`,
        message: 'No se pudo revertir el servidor local.',
        lastError: error instanceof Error ? error.message : String(error)
      }
      this.saveBackendUpdateState()
      return this.getStatus()
    }
  }

  getStatus(): LocalAgentStatus {
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    const localApiUrl = normalizeUrl(this.config?.localApiUrl) ?? 'http://127.0.0.1:8000'
    const companionUrl = normalizeUrl(this.config?.bootstrap?.companionUrl)
    const companionEntryUrl = normalizeUrl(this.config?.bootstrap?.companionEntryUrl)
    const ownerSessionUrl = normalizeUrl(this.config?.bootstrap?.ownerSessionUrl)
    const ownerApiBaseUrl = normalizeUrl(this.config?.bootstrap?.ownerApiBaseUrl)
    const currentAppVersion = app.getVersion()
    const availableAppVersion = this.manifest?.artifacts?.app?.version ?? null
    const availableBackendVersion = this.manifest?.artifacts?.backend?.version ?? null
    const license = deriveLicenseState(this.config)
    const appUpdateAvailable = isVersionGreater(availableAppVersion, currentAppVersion)
    const desktopUpdate = this.deriveDesktopUpdateState(
      currentAppVersion,
      availableAppVersion,
      appUpdateAvailable
    )
    const backendUpdate = this.deriveBackendUpdateState(
      this.backendVersion,
      availableBackendVersion
    )
    return {
      startedAt: this.startedAt,
      configPath: this.configPath,
      configLoaded: Boolean(this.config),
      controlPlaneUrl,
      branchId: this.config?.branchId ?? null,
      installTokenPresent: Boolean(this.config?.installToken),
      ownerSessionReady: Boolean(this.ownerSessionToken),
      ownerAccessMode: this.ownerSessionToken
        ? 'owner-session'
        : this.config?.installToken
          ? 'install-token'
          : 'unavailable',
      companionUrl,
      companionEntryUrl,
      ownerSessionUrl,
      ownerApiBaseUrl,
      quickLinks: {
        ownerPortfolio: normalizeUrl(this.config?.bootstrap?.quickLinks?.owner_portfolio),
        ownerDevices: normalizeUrl(this.config?.bootstrap?.quickLinks?.owner_devices),
        ownerRemote: normalizeUrl(this.config?.bootstrap?.quickLinks?.owner_remote)
      },
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
      desktopUpdate,
      backendUpdate
    }
  }

  async refreshNow(): Promise<LocalAgentStatus> {
    this.reloadConfig()
    await Promise.all([this.refreshBackendHealth(), this.refreshManifest(), this.refreshLicense()])
    return this.getStatus()
  }

  private invalidateOwnerSession(): void {
    this.ownerSessionToken = null
    this.ownerSessionExpiresAt = null
  }

  private async ensureOwnerSession(): Promise<{ controlPlaneUrl: string; ownerToken: string }> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    const installToken = this.config?.installToken?.trim() || null
    if (!controlPlaneUrl || !installToken) {
      throw new Error('El nodo no tiene control-plane o install token configurado.')
    }

    const nowSeconds = Math.floor(Date.now() / 1000)
    if (
      this.ownerSessionToken &&
      this.ownerSessionExpiresAt &&
      this.ownerSessionExpiresAt > nowSeconds + 30
    ) {
      return { controlPlaneUrl, ownerToken: this.ownerSessionToken }
    }

    const response = await fetch(`${controlPlaneUrl}/api/v1/owner/session`, {
      method: 'POST',
      headers: buildControlPlaneHeaders(installToken),
      signal: AbortSignal.timeout(7000)
    })
    if (!response.ok) {
      throw new Error(`Owner session HTTP ${response.status}`)
    }
    const body = (await response.json()) as { data?: { session_token?: string } }
    const ownerToken = body.data?.session_token?.trim() || ''
    if (!ownerToken) {
      throw new Error('Owner session sin token')
    }
    this.ownerSessionToken = ownerToken
    this.ownerSessionExpiresAt = decodeOwnerSessionExpiry(ownerToken)
    return { controlPlaneUrl, ownerToken }
  }

  private async ownerFetch(path: string, retry = true): Promise<Response> {
    const { controlPlaneUrl, ownerToken } = await this.ensureOwnerSession()
    const response = await fetch(`${controlPlaneUrl}${path}`, {
      headers: buildOwnerSessionHeaders(ownerToken),
      signal: AbortSignal.timeout(7000)
    })
    if ((response.status === 401 || response.status === 403) && retry) {
      this.invalidateOwnerSession()
      return this.ownerFetch(path, false)
    }
    return response
  }

  async getOwnerPortfolio(): Promise<OwnerPortfolioStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    if (!controlPlaneUrl || !this.config?.installToken?.trim()) {
      return {
        controlPlaneUrl,
        tenantName: null,
        tenantSlug: null,
        branchesTotal: 0,
        online: 0,
        offline: 0,
        salesTodayTotal: 0,
        alertsTotal: 0,
        branches: [],
        alerts: [],
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }

    try {
      const [portfolioRes, alertsRes] = await Promise.all([
        this.ownerFetch('/api/v1/owner/portfolio'),
        this.ownerFetch('/api/v1/owner/alerts')
      ])
      if (!portfolioRes.ok) {
        throw new Error(`Owner portfolio HTTP ${portfolioRes.status}`)
      }
      if (!alertsRes.ok) {
        throw new Error(`Owner alerts HTTP ${alertsRes.status}`)
      }
      const portfolioBody = (await portfolioRes.json()) as {
        success?: boolean
        data?: Record<string, unknown>
      }
      const alertsBody = (await alertsRes.json()) as {
        success?: boolean
        data?: Array<Record<string, unknown>>
      }
      const data = portfolioBody.data ?? {}
      return {
        controlPlaneUrl,
        tenantName: typeof data.tenant_name === 'string' ? data.tenant_name : null,
        tenantSlug: typeof data.tenant_slug === 'string' ? data.tenant_slug : null,
        branchesTotal: Number(data.branches_total ?? 0) || 0,
        online: Number(data.online ?? 0) || 0,
        offline: Number(data.offline ?? 0) || 0,
        salesTodayTotal: Number(data.sales_today_total ?? 0) || 0,
        alertsTotal: Number(data.alerts_total ?? 0) || 0,
        branches: Array.isArray(data.branches)
          ? (data.branches as Array<Record<string, unknown>>)
          : [],
        alerts: Array.isArray(alertsBody.data) ? alertsBody.data : [],
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        tenantName: null,
        tenantSlug: null,
        branchesTotal: 0,
        online: 0,
        offline: 0,
        salesTodayTotal: 0,
        alertsTotal: 0,
        branches: [],
        alerts: [],
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
  }

  async getOwnerEvents(): Promise<OwnerEventsStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    if (!controlPlaneUrl || !this.config?.installToken?.trim()) {
      return {
        controlPlaneUrl,
        events: [],
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }
    try {
      const response = await this.ownerFetch('/api/v1/owner/events')
      if (!response.ok) {
        throw new Error(`Owner events HTTP ${response.status}`)
      }
      const body = (await response.json()) as { data?: Array<Record<string, unknown>> }
      return {
        controlPlaneUrl,
        events: Array.isArray(body.data) ? body.data : [],
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        events: [],
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
  }

  async getOwnerBranchTimeline(branchId: number): Promise<OwnerBranchTimelineStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    if (!controlPlaneUrl || !this.config?.installToken?.trim()) {
      return {
        controlPlaneUrl,
        branch: null,
        timeline: [],
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }
    try {
      const response = await this.ownerFetch(`/api/v1/owner/branches/${branchId}/timeline`)
      if (!response.ok) {
        throw new Error(`Owner timeline HTTP ${response.status}`)
      }
      const body = (await response.json()) as {
        data?: { branch?: Record<string, unknown>; timeline?: Array<Record<string, unknown>> }
      }
      return {
        controlPlaneUrl,
        branch: body.data?.branch ?? null,
        timeline: Array.isArray(body.data?.timeline) ? body.data!.timeline : [],
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        branch: null,
        timeline: [],
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
  }

  async getOwnerCommercial(): Promise<OwnerCommercialStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    if (!controlPlaneUrl || !this.config?.installToken?.trim()) {
      return {
        controlPlaneUrl,
        license: null,
        health: null,
        events: [],
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }
    try {
      const response = await this.ownerFetch('/api/v1/owner/commercial')
      if (!response.ok) {
        throw new Error(`Owner commercial HTTP ${response.status}`)
      }
      const body = (await response.json()) as {
        data?: {
          license?: Record<string, unknown>
          health?: Record<string, unknown>
          events?: Array<Record<string, unknown>>
        }
      }
      return {
        controlPlaneUrl,
        license: body.data?.license ?? null,
        health: body.data?.health ?? null,
        events: Array.isArray(body.data?.events) ? body.data!.events : [],
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        license: null,
        health: null,
        events: [],
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
  }

  async getOwnerHealthSummary(): Promise<OwnerHealthSummaryStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    if (!controlPlaneUrl || !this.config?.installToken?.trim()) {
      return {
        controlPlaneUrl,
        summary: null,
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }
    try {
      const response = await this.ownerFetch('/api/v1/owner/health-summary')
      if (!response.ok) {
        throw new Error(`Owner health-summary HTTP ${response.status}`)
      }
      const body = (await response.json()) as { data?: Record<string, unknown> }
      return {
        controlPlaneUrl,
        summary: body.data ?? null,
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        summary: null,
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
  }

  async getOwnerAudit(): Promise<OwnerAuditStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    if (!controlPlaneUrl || !this.config?.installToken?.trim()) {
      return {
        controlPlaneUrl,
        audit: [],
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }
    try {
      const response = await this.ownerFetch('/api/v1/owner/audit')
      if (!response.ok) {
        throw new Error(`Owner audit HTTP ${response.status}`)
      }
      const body = (await response.json()) as { data?: Array<Record<string, unknown>> }
      return {
        controlPlaneUrl,
        audit: Array.isArray(body.data) ? body.data : [],
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        audit: [],
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
  }

  async generateLinkCode(ttlMinutes = 15): Promise<BranchLinkCodeStatus> {
    this.reloadConfig()
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    const installToken = this.config?.installToken?.trim() || null
    const branchId = this.config?.branchId ?? null
    if (!controlPlaneUrl || !installToken) {
      return {
        controlPlaneUrl,
        branchId,
        branchName: null,
        code: null,
        expiresAt: null,
        lastError: 'El nodo no tiene control-plane o install token configurado.'
      }
    }
    try {
      const response = await fetch(`${controlPlaneUrl}/api/v1/branches/generate-link-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(buildControlPlaneHeaders(installToken) ?? {})
        },
        body: JSON.stringify({ ttl_minutes: ttlMinutes, purpose: 'branch_link' }),
        signal: AbortSignal.timeout(7000)
      })
      if (!response.ok) {
        throw new Error(`Generate link code HTTP ${response.status}`)
      }
      const body = (await response.json()) as {
        data?: { branch_id?: number; branch_name?: string; code?: string; expires_at?: string }
      }
      return {
        controlPlaneUrl,
        branchId: Number(body.data?.branch_id ?? branchId ?? 0) || branchId,
        branchName: body.data?.branch_name ?? null,
        code: body.data?.code ?? null,
        expiresAt: body.data?.expires_at ?? null,
        lastError: null
      }
    } catch (error) {
      return {
        controlPlaneUrl,
        branchId,
        branchName: null,
        code: null,
        expiresAt: null,
        lastError: error instanceof Error ? error.message : String(error)
      }
    }
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
      const response = await fetch(manifestUrl, {
        headers: buildControlPlaneHeaders(this.config?.installToken ?? null),
        signal: AbortSignal.timeout(7000)
      })
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
    const explicitResolveUrl = stripInstallTokenFromUrl(
      normalizeUrl(this.config?.licenseResolveUrl || this.config?.bootstrap?.licenseResolveUrl)
    )
    const controlPlaneUrl = normalizeUrl(this.config?.controlPlaneUrl)
    const resolveUrl =
      explicitResolveUrl ||
      (controlPlaneUrl && installToken ? `${controlPlaneUrl}/api/v1/licenses/resolve` : null)
    if (!resolveUrl || !installToken || !this.configPath || !this.config) return

    this.lastLicenseCheckAt = new Date().toISOString()
    try {
      const machineId =
        this.config.license?.payload?.machine_id ||
        process.env.COMPUTERNAME ||
        process.env.HOSTNAME ||
        null
      const params = new URLSearchParams()
      if (machineId) params.set('machine_id', machineId)
      params.set('os_platform', process.platform)
      params.set('app_version', app.getVersion())
      const targetUrl = resolveUrl.includes('?')
        ? `${resolveUrl}&${params.toString()}`
        : `${resolveUrl}?${params.toString()}`
      const response = await fetch(targetUrl, {
        headers: buildControlPlaneHeaders(installToken),
        signal: AbortSignal.timeout(7000)
      })
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
    writeFileSync(
      this.desktopUpdateStatePath(),
      JSON.stringify(this.desktopUpdateState, null, 2),
      'utf8'
    )
  }

  private desktopRollbackStatePath(): string {
    return join(this.desktopUpdatesDir(), 'desktop-rollback.json')
  }

  private backendUpdateStatePath(): string {
    return join(this.desktopUpdatesDir(), 'backend-update.json')
  }

  private backendRollbackStatePath(): string {
    return join(this.desktopUpdatesDir(), 'backend-rollback.json')
  }

  private loadBackendUpdateState(): void {
    const saved = parseJsonFile<AgentBackendUpdateState>(this.backendUpdateStatePath())
    if (!saved) return
    this.backendUpdateState = saved
  }

  private saveBackendUpdateState(): void {
    mkdirSync(this.desktopUpdatesDir(), { recursive: true })
    writeFileSync(
      this.backendUpdateStatePath(),
      JSON.stringify(this.backendUpdateState, null, 2),
      'utf8'
    )
  }

  private deriveDesktopUpdateState(
    currentVersion: string,
    availableVersion: string | null,
    appUpdateAvailable: boolean
  ): AgentDesktopUpdateState {
    const current = this.desktopUpdateState
    if (
      current.status === 'staged' ||
      current.status === 'downloading' ||
      current.status === 'applying'
    ) {
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

  private hasBackendRollbackMetadata(): boolean {
    const rollback = parseJsonFile<AgentBackendRollbackState>(this.backendRollbackStatePath())
    return Boolean(rollback?.previousImage)
  }

  private deriveBackendUpdateState(
    currentVersion: string | null,
    availableVersion: string | null
  ): AgentBackendUpdateState {
    const current = this.backendUpdateState
    const updateAvailable = isVersionGreater(availableVersion, currentVersion)
    if (current.status === 'applying') {
      return {
        ...current,
        currentVersion,
        availableVersion,
        rollbackAvailable: current.rollbackAvailable || this.hasBackendRollbackMetadata()
      }
    }
    if (current.status === 'error') {
      return {
        ...current,
        currentVersion,
        availableVersion,
        rollbackAvailable: current.rollbackAvailable || this.hasBackendRollbackMetadata()
      }
    }
    if (updateAvailable) {
      return {
        ...current,
        status: 'available',
        currentVersion,
        availableVersion,
        artifact:
          this.manifest?.artifacts?.backend?.artifact ?? this.config?.backendArtifact ?? null,
        targetRef: this.manifest?.artifacts?.backend?.target_ref ?? null,
        rollbackAvailable: current.rollbackAvailable || this.hasBackendRollbackMetadata(),
        message: 'Hay una actualización del servidor local disponible.',
        lastError: current.lastError
      }
    }
    return {
      ...current,
      status: 'idle',
      currentVersion,
      availableVersion,
      artifact: this.manifest?.artifacts?.backend?.artifact ?? this.config?.backendArtifact ?? null,
      targetRef: this.manifest?.artifacts?.backend?.target_ref ?? null,
      rollbackAvailable: current.rollbackAvailable || this.hasBackendRollbackMetadata()
    }
  }

  private installationDir(): string | null {
    if (!this.configPath) return null
    return dirname(this.configPath)
  }

  private readEnvFile(path: string): Record<string, string> {
    const data = existsSync(path) ? readFileSync(path, 'utf8') : ''
    const env: Record<string, string> = {}
    for (const rawLine of data.split(/\r?\n/)) {
      const line = rawLine.trim()
      if (!line || line.startsWith('#')) continue
      const eqIndex = line.indexOf('=')
      if (eqIndex < 0) continue
      env[line.slice(0, eqIndex).trim()] = line.slice(eqIndex + 1).trim()
    }
    return env
  }

  private writeEnvFile(path: string, envVars: Record<string, string>): void {
    const serialized = Object.entries(envVars)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => `${key}=${value}`)
      .join('\n')
    writeFileSync(path, `${serialized}\n`, 'utf8')
  }

  private runDockerCompose(
    workingDirectory: string,
    envFilePath: string,
    args: string[]
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const child = spawn('docker', ['compose', '--env-file', envFilePath, ...args], {
        cwd: workingDirectory,
        stdio: ['ignore', 'pipe', 'pipe']
      })
      let stderr = ''
      child.stderr.on('data', (chunk) => {
        stderr += chunk.toString()
      })
      child.on('error', (error) => reject(error))
      child.on('close', (code) => {
        if (code === 0) {
          resolve()
          return
        }
        reject(
          new Error(stderr.trim() || `docker compose falló con código ${code ?? 'desconocido'}`)
        )
      })
    })
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
    return `'${value.replace(/'/g, `'\\''`)}'`
  }
}
