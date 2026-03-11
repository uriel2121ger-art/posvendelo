import { app, BrowserWindow } from 'electron'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir = fileURLToPath(new URL('.', import.meta.url))

function createWindow() {
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
      webviewTag: false
    }
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

  void window.loadURL('data:text/html,<h1>PosVendelo Dueño</h1><p>Ejecuta primero npm run build:web o define OWNER_APP_DEV_URL.</p>')
}

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
