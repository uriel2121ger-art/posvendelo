import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { _electron as electron } from 'playwright'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const repoRoot = path.resolve(frontendRoot, '..')

function parseDotEnv(filePath) {
  try {
    const raw = fs.readFileSync(filePath, 'utf8')
    const out = {}
    for (const line of raw.split(/\r?\n/)) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
      const idx = trimmed.indexOf('=')
      const key = trimmed.slice(0, idx).trim()
      const value = trimmed.slice(idx + 1).trim()
      if (key) out[key] = value
    }
    return out
  } catch {
    return {}
  }
}

const envFile = parseDotEnv(path.join(repoRoot, '.env'))
const apiUrl =
  process.env.E2E_API_URL ||
  process.env.TITAN_API_URL ||
  envFile.TITAN_API_URL ||
  'http://127.0.0.1:8000'
const adminUser = process.env.E2E_USER || envFile.ADMIN_API_USER || ''
const adminPass = process.env.E2E_PASS || envFile.ADMIN_API_PASSWORD || ''
const terminalId = Math.max(1, Number.parseInt(process.env.TERMINAL_ID || '1', 10) || 1)
const autoLogin = process.env.AUTO_LOGIN === '1'
const discoverPorts = (process.env.E2E_DISCOVER_PORTS || '8000,8080')
  .split(',')
  .map((value) => Number.parseInt(value.trim(), 10))
  .filter((value) => Number.isFinite(value))

const profileRoot = path.join(os.tmpdir(), `titan-pos-debug-terminal-${terminalId}`)

async function closeShiftModalIfPresent(page) {
  const continuar = page.getByRole('button', { name: /continuar turno/i })
  const abrir = page.getByRole('button', { name: /abrir turno/i })
  const shiftOverlay = page
    .locator('div.fixed.inset-0.z-50.flex.items-center.justify-center.bg-black\\/60')
    .first()

  if (await continuar.isVisible({ timeout: 4000 }).catch(() => false)) {
    await continuar.click()
  } else if (await abrir.isVisible({ timeout: 4000 }).catch(() => false)) {
    const fondo = page.getByLabel(/fondo inicial/i)
    if (await fondo.isVisible({ timeout: 1500 }).catch(() => false)) {
      await fondo.fill('100')
    }
    await abrir.click()
  }

  await shiftOverlay.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
}

async function main() {
  const app = await electron.launch({
    cwd: frontendRoot,
    args: ['.', '--no-sandbox'],
    env: {
      ...process.env,
      NODE_ENV: 'production',
      XDG_CONFIG_HOME: profileRoot
    }
  })

  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')
  await page.evaluate(
    ({ nextApiUrl, nextTerminalId, nextPorts }) => {
      localStorage.setItem('titan.baseUrl', nextApiUrl)
      localStorage.setItem('titan.terminalId', String(nextTerminalId))
      localStorage.setItem('titan.discoverPorts', JSON.stringify(nextPorts))
    },
    {
      nextApiUrl: apiUrl,
      nextTerminalId: terminalId,
      nextPorts: discoverPorts
    }
  )
  await page.reload()
  await page.waitForLoadState('domcontentloaded')

  if (autoLogin && adminUser && adminPass) {
    const loginHeading = page.getByRole('heading', { name: /Acceso a caja/i })
    if (await loginHeading.isVisible({ timeout: 8000 }).catch(() => false)) {
      await page.getByPlaceholder('Nombre de usuario').fill(adminUser)
      await page.getByPlaceholder('••••••••').fill(adminPass)
      await page.getByRole('button', { name: /ingresar/i }).click()
      await page.waitForURL(/#\/terminal/, { timeout: 15000 })
      await closeShiftModalIfPresent(page)
      await page.getByPlaceholder(/Buscar producto o escanear/i).waitFor({ timeout: 10000 })
    }
  }

  console.log(
    `[launch-isolated-terminal] instancia lista terminalId=${terminalId} perfil=${profileRoot} autoLogin=${autoLogin}`
  )

  const shutdown = async () => {
    await app.close().catch(() => {})
    process.exit(0)
  }

  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)

  await new Promise(() => {})
}

main().catch((error) => {
  console.error('[launch-isolated-terminal] error', error)
  process.exit(1)
})
