import { expect, type Page } from '@playwright/test'

function readRequiredEnv(name: string): string {
  const value = process.env[name]?.trim()
  if (!value) {
    throw new Error(`Falta ${name}. Configura las credenciales E2E antes de ejecutar Playwright.`)
  }
  return value
}

function readEnv(name: string, fallback: string): string {
  const value = process.env[name]?.trim()
  return value || fallback
}

function readPortList(raw: string): number[] {
  const ports = raw
    .split(',')
    .map((part) => Number.parseInt(part.trim(), 10))
    .filter((port) => Number.isInteger(port) && port > 0 && port < 65536)
  return ports.length > 0 ? ports : [8000, 8080]
}

export const ADMIN_USER = readRequiredEnv('E2E_USER')
export const ADMIN_PASS = readRequiredEnv('E2E_PASS')
export const E2E_API_URL = readEnv('E2E_API_URL', 'http://127.0.0.1:8000')
export const E2E_TERMINAL_ID = Math.max(
  1,
  Number.parseInt(readEnv('E2E_TERMINAL_ID', '1'), 10) || 1
)
export const E2E_DISCOVER_PORTS = readPortList(readEnv('E2E_DISCOVER_PORTS', '8000,8080'))

function runtimeSeed(): Record<string, string> {
  return {
    'pos.baseUrl': E2E_API_URL,
    'pos.terminalId': String(E2E_TERMINAL_ID),
    'pos.discoverPorts': JSON.stringify(E2E_DISCOVER_PORTS)
  }
}

export async function primeRuntimeConfig(page: Page, clearStorage = true): Promise<void> {
  await page.goto('/#/login')
  await page.evaluate(
    ({ clearStorage: shouldClear, seed }) => {
      if (shouldClear) localStorage.clear()
      for (const [key, value] of Object.entries(seed)) {
        localStorage.setItem(key, value)
      }
    },
    { clearStorage, seed: runtimeSeed() }
  )
  await page.reload()
}

export async function snapshotLocalStorage(page: Page): Promise<Record<string, string>> {
  return page.evaluate(() => {
    const entries: Record<string, string> = {}
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key) entries[key] = localStorage.getItem(key) || ''
    }
    return entries
  })
}

export async function restoreLocalStorage(
  page: Page,
  entries: Record<string, string>
): Promise<void> {
  await page.goto('/#/login')
  await page.evaluate(
    ({ nextEntries, seed }) => {
      localStorage.clear()
      for (const [key, value] of Object.entries(nextEntries)) {
        localStorage.setItem(key, value)
      }
      for (const [key, value] of Object.entries(seed)) {
        localStorage.setItem(key, value)
      }
    },
    { nextEntries: entries, seed: runtimeSeed() }
  )
  await page.reload()
}

export async function submitLogin(
  page: Page,
  username = ADMIN_USER,
  password = ADMIN_PASS
): Promise<void> {
  await page.getByPlaceholder('Nombre de usuario').fill(username)
  await page.getByPlaceholder('••••••••').fill(password)
  await page.getByRole('button', { name: /ingresar/i }).click()
}

export async function ensureShiftModalClosed(page: Page): Promise<void> {
  const continuar = page.getByRole('button', { name: /continuar turno/i })
  const abrir = page.getByRole('button', { name: /abrir turno/i })

  if (await continuar.isVisible({ timeout: 3000 }).catch(() => false)) {
    await continuar.click()
  } else if (await abrir.isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByLabel(/fondo inicial/i).fill('100')
    await abrir.click()
  }

  await page
    .locator('.fixed.inset-0.z-50.bg-black\\/50')
    .waitFor({ state: 'hidden', timeout: 5000 })
    .catch(() => {})
}

export async function expectNoAppCrash(page: Page): Promise<void> {
  await expect(page.getByText(/Unexpected Application Error/i)).toHaveCount(0)
  await expect(page.getByText(/React Router caught/i)).toHaveCount(0)
}

export const LOGIN_ERROR_PATTERN = /credenciales|incorrectas|invalidas|inválidas/i
