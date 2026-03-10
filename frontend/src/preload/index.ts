import { contextBridge, ipcRenderer } from 'electron'

// Custom APIs for renderer (IPC solo para cerrar app; resto vía HTTP al backend)
const api = {
  closeApp: () => ipcRenderer.invoke('app:close'),
  agent: {
    getStatus: () => ipcRenderer.invoke('agent:get-status'),
    refresh: () => ipcRenderer.invoke('agent:refresh'),
    prepareAppUpdate: () => ipcRenderer.invoke('agent:prepare-app-update'),
    applyAppUpdate: () => ipcRenderer.invoke('agent:apply-app-update'),
    discardAppUpdate: () => ipcRenderer.invoke('agent:discard-app-update'),
    rollbackAppUpdate: () => ipcRenderer.invoke('agent:rollback-app-update'),
    applyBackendUpdate: () => ipcRenderer.invoke('agent:apply-backend-update'),
    rollbackBackendUpdate: () => ipcRenderer.invoke('agent:rollback-backend-update'),
    getOwnerPortfolio: () => ipcRenderer.invoke('agent:get-owner-portfolio'),
    getOwnerEvents: () => ipcRenderer.invoke('agent:get-owner-events'),
    getOwnerBranchTimeline: (branchId: number) =>
      ipcRenderer.invoke('agent:get-owner-branch-timeline', branchId),
    getOwnerCommercial: () => ipcRenderer.invoke('agent:get-owner-commercial'),
    getOwnerHealthSummary: () => ipcRenderer.invoke('agent:get-owner-health-summary'),
    getOwnerAudit: () => ipcRenderer.invoke('agent:get-owner-audit'),
    generateLinkCode: (ttlMinutes?: number) =>
      ipcRenderer.invoke('agent:generate-link-code', ttlMinutes)
  }
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  console.warn('contextIsolation is disabled — API bridge not exposed')
}
