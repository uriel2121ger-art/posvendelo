/* eslint-disable @typescript-eslint/explicit-function-return-type */
import puppeteer from 'puppeteer-core'
import { runtimeConfig } from './runtime-config.mjs'
console.log('Iniciando inyector Monkey...')

const loginUsername = process.env.TITAN_TEST_USER?.trim()
const loginPassword = process.env.TITAN_TEST_PASSWORD?.trim()
const chaosKeys = ['Enter', 'Escape', 'ArrowDown', ' ', 'Backspace', 'F3', 'F12']
const chaosPayloads = [
  'monkey',
  '<script>alert(1)</script>',
  "'; DROP TABLE users--",
  'A'.repeat(400),
  '-50'
]

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function performLogin(page) {
  if (!loginUsername || !loginPassword) {
    throw new Error('Configura TITAN_TEST_USER y TITAN_TEST_PASSWORD antes de ejecutar monkey.mjs.')
  }

  await page.goto(runtimeConfig.browserLoginUrl, { waitUntil: 'networkidle0', timeout: 30000 })
  const existingToken = await page.evaluate(() => localStorage.getItem('titan.token'))
  if (existingToken) {
    await page.goto(`${runtimeConfig.browserOrigin}/#/terminal`, {
      waitUntil: 'networkidle0',
      timeout: 30000
    })
    if ((await page.evaluate(() => window.location.hash)) === '#/terminal') {
      return
    }
  }
  await page.waitForSelector('[data-testid="login-username"]', { timeout: 10000 })
  await page.waitForSelector('[data-testid="login-password"]', { timeout: 10000 })
  await page.click('[data-testid="login-username"]', { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('[data-testid="login-username"]', loginUsername, { delay: 20 })
  await page.click('[data-testid="login-password"]', { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('[data-testid="login-password"]', loginPassword, { delay: 20 })
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

async function resolveSellableProduct(page, apiBaseUrl) {
  return page.evaluate(async (fallbackApiBaseUrl) => {
    const tk = localStorage.getItem('titan.token') || ''
    const url = localStorage.getItem('titan.baseUrl') || fallbackApiBaseUrl
    const res = await fetch(`${url}/api/v1/products/?limit=200`, {
      headers: { Authorization: `Bearer ${tk}` }
    })
    const body = await res.json().catch(() => ({}))
    const products = Array.isArray(body.data)
      ? body.data
      : Array.isArray(body.data?.data)
        ? body.data.data
        : []
    for (const product of products) {
      const stock = Number(product?.stock ?? 0)
      const price = Number(product?.price ?? 0)
      if (stock > 0 && price > 0 && Number(product?.is_active ?? 1) === 1) {
        return { id: product.id, price }
      }
    }
    return null
  }, apiBaseUrl)
}

async function runUiChaos(page) {
  const uiErrors = []
  const onPageError = (error) => {
    uiErrors.push(error instanceof Error ? error.message : String(error))
  }
  page.on('pageerror', onPageError)

  const stopAt = Date.now() + 10000
  while (Date.now() < stopAt) {
    const viewport = page.viewport() ?? { width: 1280, height: 720 }
    const x = Math.max(1, Math.floor(Math.random() * viewport.width))
    const y = Math.max(1, Math.floor(Math.random() * viewport.height))
    await page.mouse.click(x, y).catch(() => {})

    const inputs = await page.$$('input:not([type="file"]), textarea')
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
    await delay(40)
  }

  page.off('pageerror', onPageError)
  return uiErrors
}

;(async () => {
  try {
    console.log('Fetching /json/version...')
    const response = await fetch(runtimeConfig.devtoolsVersionUrl)
    const data = await response.json()
    const wsUrl = data.webSocketDebuggerUrl

    const browser = await puppeteer.connect({
      browserWSEndpoint: wsUrl,
      defaultViewport: null
    })

    const pages = await browser.pages()
    const page = pages[0]

    console.log(`Forzando navegación a ${runtimeConfig.browserLoginUrl}...`)
    await performLogin(page)

    console.log(`Página activa conectada: ${page.url()}`)

    console.log('--- FASE 1: CHAOS MONKEY (10s) ---')
    const errors = await runUiChaos(page)

    console.log(
      `Errores Crash de UI capturados: ${errors.length}. Detalles: ${JSON.stringify(errors.slice(0, 3))}`
    )

    console.log('--- FASE 2: VARIANTES LOGICAS API ---')
    const sellableProduct = await resolveSellableProduct(page, runtimeConfig.apiBaseUrl)
    const apiTest = await page.evaluate(
      async ({ fallbackApiBaseUrl, sellableProductId, sellableProductPrice }) => {
        const tk = localStorage.getItem('titan.token') || 'token_ausente'
        const url = localStorage.getItem('titan.baseUrl') || fallbackApiBaseUrl
        const log = []
        try {
          if (!sellableProductId || !sellableProductPrice) {
            log.push('No se encontró producto vendible para variantes API.')
            return log
          }
          // Variante A: Float Precision 33.333% a 29.97
          let res1 = await fetch(`${url}/api/v1/sales/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tk}` },
            body: JSON.stringify({
              items: [
                {
                  product_id: sellableProductId,
                  name: 'Float item',
                  qty: 3,
                  price: 9.99,
                  discount: 33.333,
                  is_wholesale: false,
                  price_includes_tax: true
                }
              ],
              payment_method: 'cash',
              cash_received: 19.98,
              branch_id: 1
            })
          })
          log.push(
            `Variante Float (29.97 - 33.3% = 19.98): HTTP ${res1.status} -> ${await res1.text().catch(() => '')}`
          )

          // Variante B: Negativo Stock
          let res2 = await fetch(`${url}/api/v1/sales/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tk}` },
            body: JSON.stringify({
              items: [
                {
                  product_id: sellableProductId,
                  name: 'Negative test',
                  qty: -5,
                  price: 10,
                  discount: 0,
                  is_wholesale: false,
                  price_includes_tax: true
                }
              ],
              payment_method: 'cash',
              cash_received: -50,
              branch_id: 1
            })
          })
          log.push(
            `Variante Stock Negativo (-5 qty): HTTP ${res2.status} -> ${await res2.text().catch(() => '')}`
          )
        } catch (e) {
          log.push('Exception: ' + e.message)
        }
        return log
      },
      {
        fallbackApiBaseUrl: runtimeConfig.apiBaseUrl,
        sellableProductId: sellableProduct?.id ?? null,
        sellableProductPrice: sellableProduct?.price ?? null
      }
    )

    console.log('Resultados Variantes Lógicas API:')
    console.log(JSON.stringify(apiTest, null, 2))

    console.log('Monkey Testing Exitoso. Terminando...')
    process.exit(0)
  } catch (e) {
    console.error('FATAL ERROR:', e)
    process.exit(1)
  }
})()
