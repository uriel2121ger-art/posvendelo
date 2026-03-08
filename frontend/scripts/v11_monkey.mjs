/* eslint-disable @typescript-eslint/explicit-function-return-type */
import puppeteer from 'puppeteer-core'
import { runtimeConfig } from './runtime-config.mjs'

console.log('Iniciando inyector Monkey V11...')

const delay = (ms) => new Promise((res) => setTimeout(res, ms))
const loginUsername = process.env.TITAN_TEST_USER?.trim()
const loginPassword = process.env.TITAN_TEST_PASSWORD?.trim()
const chaosKeys = ['Enter', 'Escape', 'ArrowDown', ' ', 'Backspace', 'F3', 'F12']
const chaosPayloads = [
  'monkey_v11',
  '<script>alert(1)</script>',
  "'; DROP TABLE users--",
  'A'.repeat(2000),
  '-999999',
  'stress_payload'
]

async function runUiChaos(page) {
  const uiErrors = []
  const onPageError = (error) => {
    uiErrors.push(error instanceof Error ? error.message : String(error))
  }
  page.on('pageerror', onPageError)

  const stopAt = Date.now() + 15000
  while (Date.now() < stopAt) {
    const viewport = page.viewport() ?? { width: 1280, height: 720 }
    const x = Math.max(1, Math.floor(Math.random() * viewport.width))
    const y = Math.max(1, Math.floor(Math.random() * viewport.height))
    await page.mouse.click(x, y).catch(() => {})

    const inputs = await page.$$('input, textarea')
    if (inputs.length > 0) {
      const target = inputs[Math.floor(Math.random() * inputs.length)]
      const payload = chaosPayloads[Math.floor(Math.random() * chaosPayloads.length)]
      await target
        .evaluate((element, nextValue) => {
          if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
            element.focus()
            element.value = nextValue
            element.dispatchEvent(new Event('input', { bubbles: true }))
          }
        }, payload)
        .catch(() => {})
    }

    const key = chaosKeys[Math.floor(Math.random() * chaosKeys.length)]
    await page.keyboard.press(key).catch(() => {})
    await delay(30)
  }

  page.off('pageerror', onPageError)
  return uiErrors
}

async function performLogin(page) {
  await page.goto(runtimeConfig.browserLoginUrl, { waitUntil: 'networkidle0', timeout: 30000 })
  await page.waitForSelector('[data-testid="login-username"]', { timeout: 10000 })
  await page.waitForSelector('[data-testid="login-password"]', { timeout: 10000 })

  await page.click('[data-testid="login-username"]', { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('[data-testid="login-username"]', loginUsername, { delay: 25 })

  await page.click('[data-testid="login-password"]', { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('[data-testid="login-password"]', loginPassword, { delay: 25 })

  await page.waitForFunction(
    () => {
      const submit = document.querySelector('[data-testid="login-submit"]')
      return submit instanceof HTMLButtonElement && !submit.disabled
    },
    { timeout: 10000 }
  )

  await Promise.all([
    page.waitForFunction(() => window.location.hash === '#/terminal', { timeout: 10000 }),
    page.click('[data-testid="login-submit"]')
  ])

  await page.waitForFunction(() => !!localStorage.getItem('titan.token'), { timeout: 10000 })
}

;(async () => {
  try {
    if (!loginUsername || !loginPassword) {
      throw new Error(
        'Configura TITAN_TEST_USER y TITAN_TEST_PASSWORD antes de ejecutar v11_monkey.mjs.'
      )
    }

    console.log('Fetching /json/version (Esperando a que Electron levante)...')
    let wsUrl
    for (let i = 0; i < 15; i++) {
      try {
        const response = await fetch(runtimeConfig.devtoolsVersionUrl)
        const data = await response.json()
        wsUrl = data.webSocketDebuggerUrl
        break
      } catch {
        await delay(2000)
      }
    }

    if (!wsUrl)
      throw new Error(
        'No se pudo conectar al puerto de Debugger de Electron 9222 tras 30 segundos.'
      )

    const browser = await puppeteer.connect({
      browserWSEndpoint: wsUrl,
      defaultViewport: null
    })

    const pages = await browser.pages()
    const page =
      pages.find((p) =>
        runtimeConfig.appUrlMatchers.some((candidate) => p.url().startsWith(candidate))
      ) || pages[0]

    console.log('Conectado. Limpiando Caché y LocalStorage...')
    await page
      .goto(runtimeConfig.browserOrigin, { waitUntil: 'load', timeout: 30000 })
      .catch(() => {})

    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
      console.log('Storage purge completado')
    })

    console.log('Caché limpia. Recargando y forzando autologin...')
    await performLogin(page)
    await delay(2000)
    console.log(`Logueado. URL actual: ${page.url()}`)

    console.log('--- FASE 1: MONKEY UI EXTREMO V11 (15s) ---')
    const uiErrors = await runUiChaos(page)

    console.log(
      'Errores de Monkey UI interceptados:',
      uiErrors.length > 0 ? uiErrors.slice(0, 5) : 'Ninguno (App estable)'
    )

    console.log('--- FASE 2: EDGE CASES DE CONCURRENCIA V11 ---')

    const apiTest = await page.evaluate(
      async ({ apiBaseUrl, branchId }) => {
        const tk = localStorage.getItem('titan.token')
        const url = localStorage.getItem('titan.baseUrl') || apiBaseUrl
        const log = []

        if (!tk) {
          log.push('No auth token found, frontend failed to login properly.')
          return log
        }

        try {
          // 1. Concurrent Turn Opening (Race condition test)
          log.push('Testeando Race Condition: Abriendo multiples turnos concurrentes...')
          const turnPromises = Array.from({ length: 5 }).map(() =>
            fetch(`${url}/api/v1/turns/open`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tk}` },
              body: JSON.stringify({ initial_cash: 100, branch_id: branchId })
            })
              .then((r) => r.json())
              .catch((e) => e.message)
          )
          const turnRes = await Promise.all(turnPromises)
          log.push(
            `Resultados Turnos Concurrentes: (Successes: ${turnRes.filter((r) => r.success).length}, Errores: ${turnRes.filter((r) => !r.success).length})`
          )

          // 2. Envenenamiento JSON en sincronización Masiva
          log.push('Testeando Envenenamiento de Sync (String in Array of Ints)...')
          let syncRes = await fetch(`${url}/api/v1/sync/sales`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tk}` },
            body: JSON.stringify({
              data: [{ id: 'MALICIOUS_STRING_NOT_INT', total: 'abc', status: [] }],
              terminal_id: branchId,
              request_id: 'sync_v11_123'
            })
          })
          log.push(
            `Sync Envenenado Status: ${syncRes.status}. Detalle: ${await syncRes.text().catch(() => '')}`
          )
        } catch (e) {
          log.push('Exception general: ' + e.message)
        }
        return log
      },
      {
        apiBaseUrl: runtimeConfig.apiBaseUrl,
        branchId: Number(process.env.TITAN_TEST_BRANCH_ID || '1')
      }
    )

    console.log(JSON.stringify(apiTest, null, 2))

    console.log('Monkey Testing V11 Exitoso. Terminando...')
    process.exit(0)
  } catch (e) {
    console.error('FATAL ERROR V11:', e)
    process.exit(1)
  }
})()
