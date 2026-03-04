import { contextBridge, ipcRenderer } from 'electron'

// Custom APIs for renderer (IPC solo para cerrar app; resto vía HTTP al backend)
const api = {
  closeApp: () => ipcRenderer.invoke('app:close')
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
