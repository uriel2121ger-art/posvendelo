import { expect, test } from '@playwright/test'

import {
  ensureShiftModalClosed,
  expectNoAppCrash,
  primeRuntimeConfig,
  restoreLocalStorage,
  snapshotLocalStorage,
  submitLogin
} from './runtime-helpers'

let cachedSessionStorage: Record<string, string> | null = null

async function loginAndCloseModal(page: import('@playwright/test').Page): Promise<void> {
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

test.describe('Stress Browser Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndCloseModal(page)
  })

  test('stress-1: churn de rutas y recarga parcial sin crash', async ({ page }) => {
    const routes = [
      '/terminal',
      '/clientes',
      '/productos',
      '/inventario',
      '/turnos',
      '/reportes',
      '/historial',
      '/configuraciones',
      '/mermas',
      '/gastos',
      '/empleados',
      '/remoto',
      '/fiscal',
      '/hardware'
    ]

    for (let round = 0; round < 3; round++) {
      for (const route of routes) {
        await page.goto(`/#${route}`)
        await page.waitForTimeout(150)
        await expectNoAppCrash(page)
      }
    }
  })

  test('stress-2: fuzz de input y teclado en terminal', async ({ page }) => {
    const payloads = [
      '1',
      "'; DROP TABLE sales--",
      '<script>alert(1)</script>',
      'A'.repeat(1024),
      '999999999999999999999999',
      'áéíóú ñ 漢字'
    ]

    const search = page.getByPlaceholder(/Buscar (SKU|producto|producto o escanear)/i)
    await expect(search).toBeVisible({ timeout: 10000 })

    for (const payload of payloads) {
      await search.fill(payload)
      await page.keyboard.press('Enter')
      await page.keyboard.press('Escape')
      await page.keyboard.press('F9').catch(() => {})
      await page.keyboard.press('F10').catch(() => {})
      await page.waitForTimeout(120)
      await expect(page).toHaveURL(/\/#\/terminal/)
      await expectNoAppCrash(page)
    }
  })

  test('stress-3: rafaga API desde navegador sin 5xx', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const token = localStorage.getItem('titan.token') || ''
      const baseUrl = localStorage.getItem('titan.baseUrl') || ''
      const headers = { Authorization: `Bearer ${token}` }
      const requests = [
        ...Array.from({ length: 120 }, () =>
          fetch(`${baseUrl}/api/v1/products/?limit=1`, { headers }).then((r) => r.status)
        ),
        ...Array.from({ length: 120 }, () =>
          fetch(`${baseUrl}/api/v1/dashboard/quick`, { headers }).then((r) => r.status)
        ),
        ...Array.from({ length: 60 }, () =>
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

    expect(result.total).toBe(300)
    expect(result.server5xx).toBe(0)
    expect(result.ok200).toBeGreaterThan(0)
  })
})
