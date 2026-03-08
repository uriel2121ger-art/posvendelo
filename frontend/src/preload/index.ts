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
    rollbackAppUpdate: () => ipcRenderer.invoke('agent:rollback-app-update')
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
