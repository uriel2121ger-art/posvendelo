import { expect, test, type Browser, type Page } from '@playwright/test'

import {
  ensureShiftModalClosed,
  expectNoAppCrash,
  primeRuntimeConfig,
  restoreLocalStorage,
  snapshotLocalStorage,
  submitLogin
} from './runtime-helpers'

let cachedSessionStorage: Record<string, string> | null = null

async function loginAndCloseModal(page: Page): Promise<void> {
  if (cachedSessionStorage) {
    await restoreLocalStorage(page, cachedSessionStorage)
    await page.goto('/#/terminal')
    if (/\/#\/terminal/.test(page.url())) {
      await ensureShiftModalClosed(page)
      return
    }
    cachedSessionStorage = null
  }

  await primeRuntimeConfig(page)
  await submitLogin(page)
  await expect(page).toHaveURL(/\/#\/terminal/, { timeout: 10000 })
  cachedSessionStorage = await snapshotLocalStorage(page)
  await ensureShiftModalClosed(page)
}

async function openMoreAndNavigate(
  page: Page,
  target: RegExp,
  expectedHash: RegExp
): Promise<void> {
  await page.getByRole('button', { name: /más/i }).click()
  await page.getByRole('menuitem', { name: target }).click()
  await expect(page).toHaveURL(expectedHash)
  await expectNoAppCrash(page)
}

async function cloneStorage(fromPage: Page, toPage: Page): Promise<void> {
  const storage = await fromPage.evaluate(() => {
    const entries: Record<string, string> = {}
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key) entries[key] = localStorage.getItem(key) || ''
    }
    return entries
  })
  await toPage.goto('/#/login')
  await toPage.evaluate((entries) => {
    localStorage.clear()
    for (const [key, value] of Object.entries(entries)) {
      localStorage.setItem(key, value)
    }
  }, storage)
}

async function createAuthenticatedPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext()
  const page = await context.newPage()
  await loginAndCloseModal(page)
  return page
}

test.describe('Ultra Browser Stress', () => {
  test('ultra-1: tres ciclos completos de login, logout y reentrada', async ({ page }) => {
    for (let cycle = 0; cycle < 3; cycle++) {
      await loginAndCloseModal(page)
      await expect(page).toHaveURL(/\/#\/terminal/)
      await expectNoAppCrash(page)

      await page.getByRole('button', { name: /cerrar sesión/i }).click()
      await page.getByRole('button', { name: /aceptar/i }).click()
      await expect(page).toHaveURL(/#\/login/)
      cachedSessionStorage = null

      await page.goto('/#/productos')
      await expect(page).toHaveURL(/#\/login/)
    }
  })

  test('ultra-2: churn con menú Más, reloads y corrupción controlada de token', async ({
    page
  }) => {
    await loginAndCloseModal(page)

    await openMoreAndNavigate(page, /estadísticas/i, /\/#\/estadisticas/)
    await page.reload()
    await expectNoAppCrash(page)

    await openMoreAndNavigate(page, /mermas/i, /\/#\/mermas/)
    await page.reload()
    await expectNoAppCrash(page)

    await openMoreAndNavigate(page, /empleados/i, /\/#\/empleados/)
    await openMoreAndNavigate(page, /remoto/i, /\/#\/remoto/)
    await openMoreAndNavigate(page, /fiscal/i, /\/#\/fiscal/)

    await page.goto('/#/gastos')
    await expect(page).toHaveURL(/\/#\/gastos/)
    await expectNoAppCrash(page)

    await page.goto('/#/hardware')
    await expect(page).toHaveURL(/\/#\/hardware/)
    await expectNoAppCrash(page)

    await page.evaluate(() => {
      localStorage.setItem('pos.token', 'token-malformado')
    })
    await page.goto('/#/terminal')
    await expect(page).toHaveURL(/#\/login/)
    await expectNoAppCrash(page)
  })

  test('ultra-3: tormenta concurrente multi-página sin 5xx', async ({ browser }) => {
    const primary = await createAuthenticatedPage(browser)
    const second = await browser.newContext().then((ctx) => ctx.newPage())
    const third = await browser.newContext().then((ctx) => ctx.newPage())

    await cloneStorage(primary, second)
    await cloneStorage(primary, third)

    const runStorm = async (
      page: Page
    ): Promise<{
      total: number
      ok200: number
      client4xx: number
      server5xx: number
    }> => {
      await page.goto('/#/terminal')
      return page.evaluate(async () => {
        const token = localStorage.getItem('pos.token') || ''
        const baseUrl = localStorage.getItem('pos.baseUrl') || ''
        const headers = { Authorization: `Bearer ${token}` }
        const requests = [
          ...Array.from({ length: 150 }, () =>
            fetch(`${baseUrl}/api/v1/products/?limit=1`, { headers }).then((r) => r.status)
          ),
          ...Array.from({ length: 150 }, () =>
            fetch(`${baseUrl}/api/v1/dashboard/quick`, { headers }).then((r) => r.status)
          ),
          ...Array.from({ length: 75 }, () =>
            fetch(`${baseUrl}/api/v1/sales/`, {
              method: 'POST',
              headers: { ...headers, 'Content-Type': 'application/json' },
              body: JSON.stringify({
                items: [],
                payment_method: 'cash',
                cash_received: 0,
                branch_id: 1
              })
            }).then((r) => r.status)
          )
        ]
        const statuses = await Promise.all(requests)
        return {
          total: statuses.length,
          ok200: statuses.filter((status) => status === 200).length,
          client4xx: statuses.filter((status) => status >= 400 && status < 500).length,
          server5xx: statuses.filter((status) => status >= 500).length
        }
      })
    }

    const [a, b, c] = await Promise.all([runStorm(primary), runStorm(second), runStorm(third)])
    for (const result of [a, b, c]) {
      expect(result.total).toBe(375)
      expect(result.server5xx).toBe(0)
      expect(result.ok200).toBeGreaterThan(0)
    }

    await primary.close()
    await second.close()
    await third.close()
  })
})
