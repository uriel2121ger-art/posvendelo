import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('ownerUpdates', {
  getStatus: () => ipcRenderer.invoke('owner-update:get-status'),
  checkForUpdate: () => ipcRenderer.invoke('owner-update:check'),
  downloadUpdate: () => ipcRenderer.invoke('owner-update:download'),
  applyUpdate: () => ipcRenderer.invoke('owner-update:apply'),
  discardUpdate: () => ipcRenderer.invoke('owner-update:discard'),
})
