import { app, shell, BrowserWindow, ipcMain, type PrinterInfo } from 'electron'
import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { LocalNodeAgent } from './localAgent'
import { ensureBackend } from './autoSetup'

const defaultConnectSrc =
  process.env.ELECTRON_ALLOWED_CONNECT_SRC?.trim() || 'http://localhost:* http://127.0.0.1:*'

const localAgent = new LocalNodeAgent()

/** Returns 'client' if this install is a secondary terminal (no local backend); otherwise 'principal'. */
function getInstallMode(): 'principal' | 'client' {
  const path =
    process.platform === 'win32'
      ? join(process.env.PROGRAMDATA || 'C:\\ProgramData', 'POSVENDELO', 'install-mode')
      : join(homedir(), '.config', 'posvendelo', 'install-mode')
  if (!existsSync(path)) return 'principal'
  try {
    const content = readFileSync(path, 'utf8').trim().toLowerCase()
    return content === 'client' ? 'client' : 'principal'
  } catch {
    return 'principal'
  }
}

function isSafeExternalUrl(rawUrl: string): boolean {
  try {
    const parsed = new URL(rawUrl)
    // SECURITY: Only allow HTTPS for external URLs — HTTP can be MITM'd
    return parsed.protocol === 'https:'
  } catch {
    return false
  }
}

function createWindow(): void {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: false,
      devTools: is.dev
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.maximize()
    mainWindow.setFullScreen(true)
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    if (isSafeExternalUrl(details.url)) {
      shell.openExternal(details.url)
    }
    return { action: 'deny' }
  })

  // CSP: In production, enforce strict Content-Security-Policy via response headers
  if (!is.dev) {
    mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          'Content-Security-Policy': [
            "default-src 'self'; " +
              "script-src 'self'; " +
              "style-src 'self' 'unsafe-inline'; " +
              "img-src 'self' data: blob:; " +
              "font-src 'self' data:; " +
              `connect-src 'self' ${defaultConnectSrc}; ` +
              "object-src 'none'; " +
              "base-uri 'self'"
          ]
        }
      })
    })
  }

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(async () => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.posvendelo.pos')

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Modo caja secundaria: no hay backend local; la app conecta a un servidor en LAN.
  const installMode = getInstallMode()
  if (installMode !== 'client') {
    // Ensure backend is running before loading the renderer.
    // In dev mode the backend is started separately so this is a fast no-op.
    const backendReady = await ensureBackend()
    if (!backendReady) {
      app.quit()
      return
    }
  }

  createWindow()

  // Cerrar ventana desde el renderer (botón "Cerrar programa" en ShiftStartupModal)
  ipcMain.handle('app:close', () => {
    const win = BrowserWindow.getAllWindows()[0]
    if (win) win.close()
    else app.quit()
  })

  ipcMain.handle('app:get-install-mode', () => getInstallMode())

  ipcMain.handle('agent:get-status', async () => localAgent.getStatus())
  ipcMain.handle('agent:refresh', async () => localAgent.refreshNow())
  ipcMain.handle('agent:prepare-app-update', async () => localAgent.prepareAppUpdate())
  ipcMain.handle('agent:apply-app-update', async () => localAgent.applyStagedAppUpdate())
  ipcMain.handle('agent:discard-app-update', async () => localAgent.discardAppUpdate())
  ipcMain.handle('agent:rollback-app-update', async () => localAgent.rollbackLastAppUpdate())
  ipcMain.handle('agent:apply-backend-update', async () => localAgent.applyBackendUpdate())
  ipcMain.handle('agent:rollback-backend-update', async () =>
    localAgent.rollbackLastBackendUpdate()
  )
  ipcMain.handle('agent:get-owner-portfolio', async () => localAgent.getOwnerPortfolio())
  ipcMain.handle('agent:get-owner-events', async () => localAgent.getOwnerEvents())
  ipcMain.handle('agent:get-owner-branch-timeline', async (_, branchId: unknown) => {
    const id = Number(branchId)
    if (!Number.isInteger(id) || id < 1) return { success: false, error: 'branchId inválido' }
    return localAgent.getOwnerBranchTimeline(id)
  })
  ipcMain.handle('agent:get-owner-commercial', async () => localAgent.getOwnerCommercial())
  ipcMain.handle('agent:get-owner-health-summary', async () => localAgent.getOwnerHealthSummary())
  ipcMain.handle('agent:get-owner-audit', async () => localAgent.getOwnerAudit())
  ipcMain.handle('agent:generate-link-code', async (_, ttlMinutes?: unknown) => {
    const ttl = Number(ttlMinutes)
    const safeTtl = Number.isInteger(ttl) && ttl >= 1 && ttl <= 1440 ? ttl : 15
    return localAgent.generateLinkCode(safeTtl)
  })

  // Hardware: list system printers via Electron (host-level, not Docker)
  ipcMain.handle('hardware:list-printers', async (): Promise<PrinterInfo[]> => {
    const win = BrowserWindow.getAllWindows()[0]
    if (!win) return []
    return win.webContents.getPrintersAsync()
  })

  localAgent.start()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    localAgent.stop()
    app.quit()
  }
})

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and require them here.
