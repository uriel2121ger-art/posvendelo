import { app, BrowserWindow, ipcMain } from 'electron'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { OwnerUpdateAgent } from './ownerAgent.js'

const currentDir = fileURLToPath(new URL('.', import.meta.url))
let agent: OwnerUpdateAgent

function createWindow(): void {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1080,
    minHeight: 720,
    backgroundColor: '#09090f',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webviewTag: false,
      preload: join(currentDir, 'preload.js'),
    },
  })

  const devUrl = process.env.OWNER_APP_DEV_URL?.trim()
  if (devUrl) {
    void window.loadURL(devUrl)
    return
  }

  const distIndex = join(currentDir, '..', 'dist', 'index.html')
  if (existsSync(distIndex)) {
    void window.loadFile(distIndex)
    return
  }

  void window.loadURL(
    'data:text/html,<h1>PosVendelo Due%C3%B1o</h1><p>Ejecuta primero npm run build:web o define OWNER_APP_DEV_URL.</p>',
  )
}

app
  .whenReady()
  .then(() => {
    agent = new OwnerUpdateAgent(app.getVersion())
    agent.start()

    ipcMain.handle('owner-update:get-status', () => agent.getStatus())
    ipcMain.handle('owner-update:check', () => agent.checkForUpdate())
    ipcMain.handle('owner-update:download', () => agent.downloadUpdate())
    ipcMain.handle('owner-update:apply', async () => {
      await agent.applyUpdate()
      return agent.getStatus()
    })
    ipcMain.handle('owner-update:discard', () => {
      agent.discardUpdate()
      return agent.getStatus()
    })

    createWindow()
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })
  .catch((error: unknown) => {
    console.error('[main] app.whenReady error:', error)
  })

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    agent?.stop()
    app.quit()
  }
})
