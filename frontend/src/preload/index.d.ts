import { ElectronAPI } from '@electron-toolkit/preload'

type LocalAgentStatus = {
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
  manifest: unknown
  license: {
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
  desktopUpdate: {
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
  backendUpdate: {
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
}

type OwnerPortfolioStatus = {
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

type OwnerEventsStatus = {
  controlPlaneUrl: string | null
  events: Array<Record<string, unknown>>
  lastError: string | null
}

type OwnerBranchTimelineStatus = {
  controlPlaneUrl: string | null
  branch: Record<string, unknown> | null
  timeline: Array<Record<string, unknown>>
  lastError: string | null
}

type OwnerCommercialStatus = {
  controlPlaneUrl: string | null
  license: Record<string, unknown> | null
  health: Record<string, unknown> | null
  events: Array<Record<string, unknown>>
  lastError: string | null
}

type OwnerHealthSummaryStatus = {
  controlPlaneUrl: string | null
  summary: Record<string, unknown> | null
  lastError: string | null
}

type OwnerAuditStatus = {
  controlPlaneUrl: string | null
  audit: Array<Record<string, unknown>>
  lastError: string | null
}

type BranchLinkCodeStatus = {
  controlPlaneUrl: string | null
  branchId: number | null
  branchName: string | null
  code: string | null
  expiresAt: string | null
  lastError: string | null
}

type ElectronPrinterInfo = {
  name: string
  displayName: string
  description: string
  status: number
  isDefault: boolean
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      closeApp: () => Promise<void>
      getInstallMode: () => Promise<'principal' | 'client'>
      hardware: {
        listPrinters: () => Promise<ElectronPrinterInfo[]>
      }
      agent: {
        getStatus: () => Promise<LocalAgentStatus>
        refresh: () => Promise<LocalAgentStatus>
        prepareAppUpdate: () => Promise<LocalAgentStatus>
        applyAppUpdate: () => Promise<LocalAgentStatus>
        discardAppUpdate: () => Promise<LocalAgentStatus>
        rollbackAppUpdate: () => Promise<LocalAgentStatus>
        applyBackendUpdate: () => Promise<LocalAgentStatus>
        rollbackBackendUpdate: () => Promise<LocalAgentStatus>
        getOwnerPortfolio: () => Promise<OwnerPortfolioStatus>
        getOwnerEvents: () => Promise<OwnerEventsStatus>
        getOwnerBranchTimeline: (branchId: number) => Promise<OwnerBranchTimelineStatus>
        getOwnerCommercial: () => Promise<OwnerCommercialStatus>
        getOwnerHealthSummary: () => Promise<OwnerHealthSummaryStatus>
        getOwnerAudit: () => Promise<OwnerAuditStatus>
        generateLinkCode: (ttlMinutes?: number) => Promise<BranchLinkCodeStatus>
      }
    }
  }
}
