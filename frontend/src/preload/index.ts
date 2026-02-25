import { contextBridge } from 'electron'

// Custom APIs for renderer (IPC not used — frontend connects to backend via HTTP)
const api = {}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
}
