import { ElectronAPI } from '@electron-toolkit/preload'

type LocalAgentStatus = {
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
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      closeApp: () => Promise<void>
      agent: {
        getStatus: () => Promise<LocalAgentStatus>
        refresh: () => Promise<LocalAgentStatus>
        prepareAppUpdate: () => Promise<LocalAgentStatus>
        applyAppUpdate: () => Promise<LocalAgentStatus>
        discardAppUpdate: () => Promise<LocalAgentStatus>
        rollbackAppUpdate: () => Promise<LocalAgentStatus>
      }
    }
  }
}
