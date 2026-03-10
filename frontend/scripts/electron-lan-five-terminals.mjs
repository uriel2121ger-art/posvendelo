import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect } from '@playwright/test'
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

const dotEnv = parseDotEnv(path.join(repoRoot, '.env'))

function readSetting(name, fallback = '') {
  const value = process.env[name]?.trim()
  if (value) return value
  const fromDotEnv = dotEnv[name]?.trim()
  if (fromDotEnv) return fromDotEnv
  return fallback
}

function requireSetting(name, fallback = '') {
  const value = readSetting(name, fallback)
  if (!value) {
    throw new Error(
      `Falta ${name}. Configúralo en el entorno o en ../.env antes de correr la prueba.`
    )
  }
  return value
}

const API_URL =
  readSetting('E2E_API_URL') ||
  readSetting('TITAN_API_URL') ||
  readSetting('ELECTRON_E2E_BASE_URL') ||
  'http://127.0.0.1:8000'
const ADMIN_USER = requireSetting('E2E_USER', readSetting('ADMIN_API_USER'))
const ADMIN_PASS = requireSetting('E2E_PASS', readSetting('ADMIN_API_PASSWORD'))
const DISCOVER_PORTS = readSetting('E2E_DISCOVER_PORTS', '8000,8080')
const TERMINAL_COUNT = Math.max(
  1,
  Number.parseInt(readSetting('LAN_TEST_TERMINAL_COUNT', '5'), 10) || 5
)
const TERMINAL_START_ID = Math.max(
  1,
  Number.parseInt(readSetting('LAN_TEST_TERMINAL_START_ID', '1'), 10) || 1
)
const TERMINAL_IDS = Array.from(
  { length: TERMINAL_COUNT },
  (_value, index) => TERMINAL_START_ID + index
)
const ROUNDS = Math.max(1, Number.parseInt(readSetting('LAN_TEST_ROUNDS', '3'), 10) || 3)
const DURATION_MINUTES = Math.max(
  0,
  Number.parseInt(readSetting('LAN_TEST_DURATION_MINUTES', '0'), 10) || 0
)
const ROUND_DELAY_MS = Math.max(
  0,
  Number.parseInt(readSetting('LAN_TEST_ROUND_DELAY_MS', '0'), 10) || 0
)
const TARGET_TOTAL_SALES = Math.max(
  0,
  Number.parseInt(readSetting('LAN_TEST_TARGET_TOTAL_SALES', '0'), 10) || 0
)
const DISTINCT_ITEMS_PER_TICKET = Math.max(
  5,
  Number.parseInt(readSetting('LAN_TEST_DISTINCT_ITEMS', '5'), 10) || 5
)
const PRODUCT_POOL_SIZE = Math.max(
  DISTINCT_ITEMS_PER_TICKET,
  Number.parseInt(readSetting('LAN_TEST_PRODUCT_POOL_SIZE', '10'), 10) || 10
)
const MIN_QTY_PER_ITEM = Math.max(
  1,
  Number.parseInt(readSetting('LAN_TEST_MIN_ITEM_QTY', '1'), 10) || 1
)
const MAX_QTY_PER_ITEM = Math.max(
  MIN_QTY_PER_ITEM,
  Number.parseInt(readSetting('LAN_TEST_MAX_ITEM_QTY', '24'), 10) || 24
)

const runState = {
  checks: [],
  httpIssues: [],
  consoleIssues: [],
  pageErrors: []
}
let cachedApiToken = null
let cachedApiTokenPromise = null

const allowedHttpIssuePatterns = [
  { status: 401, url: /\/api\/v1\/auth\/verify$/i },
  { status: 404, url: /\/api\/v1\/license\/status$/i },
  { status: 500, url: /\/api\/v1\/hardware\/print-receipt$/i }
]

function log(line) {
  console.log(line)
}

function recordCheck(name, ok, extra = '') {
  runState.checks.push({ name, ok, extra })
  log(`${ok ? 'OK' : 'FAIL'} | ${name}${extra ? ` | ${extra}` : ''}`)
}

async function check(name, fn, options = {}) {
  const { fatal = false } = options
  try {
    const extra = await fn()
    recordCheck(name, true, typeof extra === 'string' ? extra : '')
    return { ok: true, extra }
  } catch (error) {
    recordCheck(name, false, error instanceof Error ? error.message : String(error))
    if (fatal) throw error
    return { ok: false, error }
  }
}

function isAllowedHttpIssue(status, url) {
  return allowedHttpIssuePatterns.some((rule) => rule.status === status && rule.url.test(url))
}

function formatPrice(value) {
  return (Math.round(value * 100) / 100).toFixed(2)
}

function buildProductCatalog(runId) {
  const basePrices = [0.5, 1.25, 3.5, 7.99, 15.5, 29.9, 54.75, 89.4, 150, 200]
  const catalog = []
  for (let index = 0; index < PRODUCT_POOL_SIZE; index += 1) {
    const price = basePrices[index % basePrices.length]
    catalog.push({
      sku: `E2E-LAN-${runId}-${String(index + 1).padStart(2, '0')}`,
      name: `Producto LAN ${index + 1} $${formatPrice(price)}`,
      category: 'Pruebas LAN Variables',
      price,
      stock: 500000
    })
  }
  return catalog
}

function buildTicketPlan(products, terminalId, round) {
  const plan = []
  const usedIndexes = new Set()
  const productCount = products.length
  let cursor = (terminalId * 5 + round * 3) % productCount
  const step = productCount > 1 ? 3 : 1

  while (plan.length < DISTINCT_ITEMS_PER_TICKET) {
    while (usedIndexes.has(cursor)) {
      cursor = (cursor + 1) % productCount
    }
    usedIndexes.add(cursor)
    const product = products[cursor]
    const qtySpan = MAX_QTY_PER_ITEM - MIN_QTY_PER_ITEM + 1
    const quantity =
      MIN_QTY_PER_ITEM + ((terminalId * 17 + round * 11 + plan.length * 7) % Math.max(1, qtySpan))
    plan.push({ product, quantity })
    cursor = (cursor + step) % productCount
  }

  return plan
}

function describeTicketPlan(plan) {
  return plan.map((item) => `${item.product.sku}x${item.quantity}`).join(',')
}

async function apiRequest(pathname, options = {}) {
  const response = await fetch(`${API_URL}${pathname}`, options)
  const text = await response.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }
  return {
    ok: response.ok,
    status: response.status,
    body
  }
}

async function apiJson(pathname, options = {}) {
  const response = await apiRequest(pathname, options)
  if (!response.ok) {
    throw new Error(
      `${response.status} ${pathname} :: ${
        typeof response.body === 'string' ? response.body : JSON.stringify(response.body)
      }`
    )
  }
  return response.body
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function apiLoginToken() {
  if (cachedApiToken) return cachedApiToken
  if (cachedApiTokenPromise) return cachedApiTokenPromise

  cachedApiTokenPromise = (async () => {
    let lastError = null
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        const body = await apiJson('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASS })
        })
        const token = body?.access_token || body?.token
        if (!token) throw new Error('No se obtuvo token del login API.')
        cachedApiToken = token
        return token
      } catch (error) {
        lastError = error
        const message = error instanceof Error ? error.message : String(error)
        if (!message.startsWith('429 ')) {
          break
        }
        await sleep(attempt * 1500)
      }
    }
    throw lastError ?? new Error('No se pudo autenticar contra la API.')
  })()

  try {
    return await cachedApiTokenPromise
  } finally {
    cachedApiTokenPromise = null
  }
}

function authHeaders(token, terminalId) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    'X-Terminal-Id': String(terminalId)
  }
}

async function fetchCurrentTurn(terminalId) {
  const token = await apiLoginToken()
  const body = await apiJson(`/api/v1/turns/current?terminal_id=${terminalId}`, {
    headers: authHeaders(token, terminalId)
  })
  return body?.data ?? body ?? null
}

async function closeShiftModalIfPresent(page) {
  const continuar = page.getByRole('button', { name: /continuar turno/i })
  const abrir = page.getByRole('button', { name: /abrir turno/i })
  const shiftOverlay = page
    .locator('div.fixed.inset-0.z-50.flex.items-center.justify-center.bg-black\\/60')
    .first()

  if (await continuar.isVisible({ timeout: 4000 }).catch(() => false)) {
    await continuar.evaluate((element) => {
      if (element instanceof HTMLElement) element.click()
    })
  } else if (await abrir.isVisible({ timeout: 4000 }).catch(() => false)) {
    const fondo = page.getByLabel(/fondo inicial/i)
    if (await fondo.isVisible({ timeout: 1500 }).catch(() => false)) {
      await fondo.fill('100')
    }
    await abrir.evaluate((element) => {
      if (element instanceof HTMLElement) element.click()
    })
  }

  await shiftOverlay.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
}

async function ensureShiftReady(page, terminalId) {
  await closeShiftModalIfPresent(page)

  let turn = await fetchCurrentTurn(terminalId).catch(() => null)
  if (turn?.id) {
    return
  }

  const token = await apiLoginToken()
  await apiJson('/api/v1/turns/open', {
    method: 'POST',
    headers: authHeaders(token, terminalId),
    body: JSON.stringify({
      initial_cash: 100,
      branch_id: 1,
      terminal_id: terminalId
    })
  }).catch(() => null)

  await page.reload({ waitUntil: 'domcontentloaded' })
  await closeShiftModalIfPresent(page)

  turn = await fetchCurrentTurn(terminalId).catch(() => null)
  if (!turn?.id) {
    throw new Error(`La terminal ${terminalId} no logró abrir o recuperar turno`)
  }
}

async function loginAndPrepare(page, terminalId) {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const loginHeading = page.getByRole('heading', { name: /Acceso a caja/i })
    if (await loginHeading.isVisible({ timeout: 8000 }).catch(() => false)) {
      await page.getByPlaceholder('Nombre de usuario').fill(ADMIN_USER)
      await page.getByPlaceholder('••••••••').fill(ADMIN_PASS)
      await page.getByRole('button', { name: /ingresar/i }).click()
    }

    const onTerminal = await expect
      .poll(() => page.url(), { timeout: 20000 })
      .toMatch(/#\/terminal/)
      .then(() => true)
      .catch(() => false)

    if (onTerminal) break

    if (attempt === 2) {
      throw new Error(`No fue posible abrir ventas. URL final: ${page.url()}`)
    }

    await page.waitForTimeout(1000)
  }
  await ensureShiftReady(page, terminalId)
  await expect(page.getByPlaceholder(/Buscar producto o escanear/i).first()).toBeVisible({
    timeout: 10000
  })
}

async function launchTerminal(terminalId, runId) {
  const profileRoot = path.join(os.tmpdir(), `titan-pos-lan-${runId}-terminal-${terminalId}`)
  fs.rmSync(profileRoot, { recursive: true, force: true })

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

  page.on('response', (response) => {
    const status = response.status()
    const url = response.url()
    if (status >= 400 && !isAllowedHttpIssue(status, url)) {
      runState.httpIssues.push(
        `terminal=${terminalId} ${status} ${response.request().method()} ${url}`
      )
    }
  })

  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    const text = msg.text()
    if (/Failed to load resource/i.test(text) || /401 \(Unauthorized\)/i.test(text)) return
    runState.consoleIssues.push(`terminal=${terminalId} ${text}`)
  })

  page.on('pageerror', (error) => {
    runState.pageErrors.push(`terminal=${terminalId} ${error.message}`)
  })

  await page.waitForLoadState('domcontentloaded')
  await page.evaluate(
    ({ nextApiUrl, nextTerminalId, nextPorts }) => {
      localStorage.clear()
      localStorage.setItem('titan.baseUrl', nextApiUrl)
      localStorage.setItem('titan.terminalId', String(nextTerminalId))
      localStorage.setItem('titan.discoverPorts', JSON.stringify(nextPorts))
    },
    {
      nextApiUrl: API_URL,
      nextTerminalId: terminalId,
      nextPorts: DISCOVER_PORTS.split(',').map((value) => Number.parseInt(value.trim(), 10))
    }
  )
  await page.reload()
  await page.waitForLoadState('domcontentloaded')
  await loginAndPrepare(page, terminalId)

  return { app, page, terminalId, profileRoot }
}

async function createProduct(page, product) {
  await closeBlockingModalIfPresent(page)
  await clickElement(page, page.getByRole('link', { name: /productos/i }).first())
  await expect(page.getByRole('heading', { name: /Productos/i }).first()).toBeVisible({
    timeout: 10000
  })
  await clickElement(page, page.getByRole('button', { name: /^Nuevo$/ }).first())
  await expect(page.getByRole('heading', { name: /Nuevo producto/i })).toBeVisible({
    timeout: 10000
  })

  await page.getByPlaceholder('Ej: 7501234567890').fill(product.sku)
  await page.getByPlaceholder('Coca Cola 600ml').fill(product.name)

  const productNumberInputs = page.locator('input[type="number"]')
  await productNumberInputs.nth(0).fill(formatPrice(product.price))
  await productNumberInputs.nth(1).fill(String(product.stock))
  await page.getByPlaceholder(/Ej: Bebidas, Abarrotes/i).fill(product.category)
  await clickElement(page, page.getByRole('button', { name: /guardar producto/i }).first())
  await expect(page.getByRole('heading', { name: /Nuevo producto|Editar producto/i })).toBeHidden({
    timeout: 15000
  })
  return product
}

async function closeBlockingModalIfPresent(page) {
  const checkoutModal = page.locator('#checkout-modal').first()
  if (await checkoutModal.isVisible({ timeout: 1000 }).catch(() => false)) {
    const cancelButton = checkoutModal.getByRole('button', { name: /Cancelar/i }).first()
    if (await cancelButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelButton.evaluate((element) => {
        if (element instanceof HTMLElement) element.click()
      })
      await checkoutModal.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
      return
    }
    await page.keyboard.press('Escape').catch(() => {})
    await checkoutModal.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
    return
  }

  const confirmOverlay = page.locator('div.fixed.inset-0.z-\\[100\\]').first()
  if (await confirmOverlay.isVisible({ timeout: 1000 }).catch(() => false)) {
    const acceptButton = confirmOverlay.getByRole('button', { name: /Aceptar/i }).first()
    const cancelButton = confirmOverlay.getByRole('button', { name: /Cancelar/i }).first()
    if (await acceptButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await acceptButton.evaluate((element) => {
        if (element instanceof HTMLElement) element.click()
      })
      await confirmOverlay.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
      return
    }
    if (await cancelButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await cancelButton.evaluate((element) => {
        if (element instanceof HTMLElement) element.click()
      })
      await confirmOverlay.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
      return
    }
  }

  const dialog = page.locator('[role="dialog"]').first()
  if (!(await dialog.isVisible({ timeout: 1000 }).catch(() => false))) return
  const cancelButton = dialog.getByRole('button', { name: /Cancelar/i }).first()
  if (await cancelButton.isVisible({ timeout: 1000 }).catch(() => false)) {
    await cancelButton.evaluate((element) => {
      if (element instanceof HTMLElement) element.click()
    })
    await dialog.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
    return
  }

  await page.keyboard.press('Escape').catch(() => {})
  await dialog.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {})
}

async function addProductToCart(page, sku, expectedName) {
  await closeBlockingModalIfPresent(page)
  const search = page.getByPlaceholder(/Buscar producto o escanear/i).first()
  const cobrarButton = page.getByRole('button', { name: /^COBRAR$/i }).first()

  for (let attempt = 1; attempt <= 3; attempt += 1) {
    await search.fill('')
    await search.fill(sku)
    await search.press('Enter')

    const dropdownButton = page.locator('button').filter({ hasText: expectedName }).first()
    if (await dropdownButton.isVisible({ timeout: 1500 }).catch(() => false)) {
      await clickElement(page, dropdownButton)
    }

    if (await cobrarButton.isEnabled({ timeout: 2500 }).catch(() => false)) {
      return
    }

    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('titan-products-changed'))
      window.dispatchEvent(new Event('focus'))
    })
    await page.waitForTimeout(1200)
  }

  await expect(cobrarButton).toBeEnabled({ timeout: 10000 })
}

async function addTicketPlanToCart(page, plan) {
  for (const item of plan) {
    for (let count = 0; count < item.quantity; count += 1) {
      await addProductToCart(page, item.product.sku, item.product.name)
    }
  }
}

async function clickElement(page, locator) {
  await locator.evaluate((element) => {
    if (element instanceof HTMLElement) element.click()
  })
  await page.waitForTimeout(150)
}

async function navigateToVentas(page) {
  if (/#\/terminal$/.test(page.url())) {
    await expect(page.getByPlaceholder(/Buscar producto o escanear/i).first()).toBeVisible({
      timeout: 10000
    })
    return
  }
  await clickElement(page, page.getByRole('link', { name: /ventas/i }).first())
  await expect.poll(() => page.url(), { timeout: 10000 }).toMatch(/#\/terminal$/)
  await expect(page.getByPlaceholder(/Buscar producto o escanear/i).first()).toBeVisible({
    timeout: 10000
  })
}

async function createSaleAndReturnFolio(page) {
  const modal = page.locator('#checkout-modal').first()
  await closeBlockingModalIfPresent(page)
  if (!(await modal.isVisible({ timeout: 1000 }).catch(() => false))) {
    await clickElement(page, page.getByRole('button', { name: /^COBRAR$/i }).first())
    await expect(modal).toBeVisible({ timeout: 8000 })
  }
  await modal.locator('select').selectOption('cash')
  await modal.locator('input[type="number"]').first().fill('999999')
  await clickElement(page, modal.getByRole('button', { name: /^COBRAR$/ }).last())

  await page.waitForTimeout(2500)
  const bodyText = await page.locator('body').innerText()
  const match = bodyText.match(/Venta ([A-Z0-9-]+) registrada/i)
  const ticketReset = await page
    .getByText(/Ticket vacío/i)
    .first()
    .isVisible({ timeout: 3000 })
    .catch(() => false)
  const modalHidden = await modal.isHidden({ timeout: 5000 }).catch(() => false)
  if (!match && !ticketReset && !modalHidden) {
    throw new Error(`No se confirmó el cobro. Fragmento: ${bodyText.slice(-700)}`)
  }
  return match?.[1] ?? ''
}

async function performRound(ctx, products, round) {
  const { page, terminalId } = ctx
  const plan = buildTicketPlan(products, terminalId, round)
  try {
    await closeBlockingModalIfPresent(page)
    await navigateToVentas(page)

    if (round === 2) {
      await addProductToCart(page, plan[0].product.sku, plan[0].product.name)
      await clickElement(page, page.getByRole('button', { name: /Ticket pendiente/i }).first())
      await expect(page.getByText(/Ticket vacío/i).first()).toBeVisible({ timeout: 5000 })
    }

    await addTicketPlanToCart(page, plan)
    const folio = await createSaleAndReturnFolio(page)

    if (round === 3) {
      await clickElement(page, page.getByRole('link', { name: /historial/i }).first())
      await expect(page.getByPlaceholder(/Buscar por folio/i)).toBeVisible({ timeout: 10000 })
      await navigateToVentas(page)
    }

    return `terminal=${terminalId} round=${round} folio=${folio || 'sin-toast'} plan=${describeTicketPlan(plan)}`
  } finally {
    await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {})
    await loginAndPrepare(page, terminalId).catch(() => {})
    await closeBlockingModalIfPresent(page).catch(() => {})
  }
}

async function fetchShiftSummary(terminalId) {
  const token = await apiLoginToken()
  const data = await fetchCurrentTurn(terminalId)
  if (!data?.id) {
    return {
      salesCount: 0,
      totalSales: 0
    }
  }
  const summary = await apiJson(`/api/v1/turns/${Number(data.id)}/summary`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Terminal-Id': String(terminalId)
    }
  })
  const summaryData = summary?.data ?? summary
  return {
    salesCount: Number(summaryData?.sales_count ?? 0),
    totalSales: Number(summaryData?.total_sales ?? 0)
  }
}

async function closeTerminalTurn(terminalId) {
  const token = await apiLoginToken()
  const currentTurn = await fetchCurrentTurn(terminalId)
  if (!currentTurn?.id) {
    return `terminal=${terminalId} sin turno abierto`
  }

  const summary = await apiJson(`/api/v1/turns/${Number(currentTurn.id)}/summary`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Terminal-Id': String(terminalId)
    }
  })
  const summaryData = summary?.data ?? summary
  const expectedCash = Number(summaryData?.expected_cash ?? 0)

  await apiJson(`/api/v1/turns/${Number(currentTurn.id)}/close`, {
    method: 'POST',
    headers: authHeaders(token, terminalId),
    body: JSON.stringify({
      final_cash: Math.round(expectedCash * 100) / 100,
      notes: `Cierre automático runner LAN terminal ${terminalId}`
    })
  })

  return `terminal=${terminalId} turno=${currentTurn.id} cerrado`
}

async function main() {
  const runId = `${Date.now()}`
  let contexts = []
  try {
    await check(
      `Lanzar ${TERMINAL_COUNT} terminales LAN concurrentes`,
      async () => {
        for (const terminalId of TERMINAL_IDS) {
          contexts.push(await launchTerminal(terminalId, runId))
        }
        return contexts.map((ctx) => ctx.terminalId).join(',')
      },
      { fatal: true }
    )

    const products = await (async () => {
      let created = []
      const productCatalog = buildProductCatalog(runId)
      await check(
        `Crear catálogo LAN variable (${productCatalog.length} productos)`,
        async () => {
          for (const product of productCatalog) {
            created.push(await createProduct(contexts[0].page, product))
          }
          return created
            .map((product) => `${product.sku}=$${formatPrice(product.price)}`)
            .join(' | ')
        },
        { fatal: true }
      )
      return created
    })()

    await check(`Propagar catálogo nuevo a las ${TERMINAL_COUNT} terminales`, async () => {
      await Promise.all(
        contexts.map(async ({ page }) => {
          await page.evaluate(() => {
            window.dispatchEvent(new CustomEvent('titan-products-changed'))
            window.dispatchEvent(new Event('focus'))
          })
        })
      )
      await Promise.all(contexts.map(async ({ page }) => page.waitForTimeout(1500)))
      return products
        .map((product) => product.sku)
        .slice(0, DISTINCT_ITEMS_PER_TICKET)
        .join(',')
    })

    await check(`${TERMINAL_COUNT} terminales listas en pantalla de venta`, async () => {
      await Promise.all(
        contexts.map(async ({ page, terminalId }) => {
          await navigateToVentas(page)
          return terminalId
        })
      )
      return `ventas activas en ${TERMINAL_COUNT}/${TERMINAL_COUNT}`
    })

    const before = await (async () => {
      let snapshot = null
      await check('Capturar baseline de turnos', async () => {
        snapshot = await Promise.all(
          TERMINAL_IDS.map((terminalId) => fetchShiftSummary(terminalId))
        )
        return snapshot.map((item, idx) => `t${TERMINAL_IDS[idx]}=${item.salesCount}`).join(' ')
      })
      return snapshot
    })()

    const deadlineMs = DURATION_MINUTES > 0 ? Date.now() + DURATION_MINUTES * 60_000 : null
    let round = 1
    let successfulSales = 0
    while (true) {
      if (deadlineMs != null && Date.now() >= deadlineMs) break
      if (TARGET_TOTAL_SALES > 0 && successfulSales >= TARGET_TOTAL_SALES) break
      if (deadlineMs == null && round > ROUNDS) break

      await check(`Ronda concurrente LAN ${round}`, async () => {
        const results = await Promise.all(
          contexts.map(
            (ctx, index) =>
              new Promise((resolve, reject) => {
                const jitter = index * 120
                setTimeout(() => {
                  void performRound(ctx, products, round).then(resolve).catch(reject)
                }, jitter)
              })
          )
        )
        successfulSales += results.length
        return results.join(' | ')
      })

      if (ROUND_DELAY_MS > 0) {
        await new Promise((resolve) => setTimeout(resolve, ROUND_DELAY_MS))
      }
      round += 1
    }

    if (TARGET_TOTAL_SALES > 0) {
      await check(`Meta de ${TARGET_TOTAL_SALES} ventas alcanzada`, async () => {
        if (successfulSales < TARGET_TOTAL_SALES) {
          throw new Error(
            `Solo se completaron ${successfulSales} ventas antes del límite de tiempo; meta requerida: ${TARGET_TOTAL_SALES}`
          )
        }
        return `${successfulSales} ventas completadas`
      })
    }

    await check('Post-navegación concurrente sin crash', async () => {
      await Promise.all(
        contexts.map(async ({ page, terminalId }) => {
          await clickElement(page, page.getByRole('link', { name: /turnos/i }).first())
          await expect(
            page.getByText(/Turnos|apertura|cierre|Efectivo|Historial|Diferencia/i).first()
          ).toBeVisible({ timeout: 10000 })
          await navigateToVentas(page)
          return terminalId
        })
      )
      return `turnos->ventas correcto en ${TERMINAL_COUNT}/${TERMINAL_COUNT}`
    })

    await check(`El backend reflejó actividad de las ${TERMINAL_COUNT} terminales`, async () => {
      if (!before) throw new Error('No hubo baseline de turnos.')
      const after = await Promise.all(
        TERMINAL_IDS.map((terminalId) => fetchShiftSummary(terminalId))
      )
      const deltas = after.map((item, index) => item.salesCount - before[index].salesCount)
      const terminalsWithoutGrowth = deltas
        .map((delta, index) => ({ delta, terminalId: TERMINAL_IDS[index] }))
        .filter((item) => item.delta < 1)
      if (terminalsWithoutGrowth.length > 0) {
        throw new Error(
          `Sin crecimiento de ventas en: ${terminalsWithoutGrowth
            .map((item) => `t${item.terminalId}=+${item.delta}`)
            .join(', ')}`
        )
      }
      return deltas.map((delta, index) => `t${TERMINAL_IDS[index]}=+${delta}`).join(' ')
    })

    await check(`Sin errores HTTP inesperados en ${TERMINAL_COUNT} terminales`, async () => {
      if (runState.httpIssues.length > 0)
        throw new Error([...new Set(runState.httpIssues)].join('\n'))
      return 'sin hallazgos'
    })

    await check(`Sin errores de consola inesperados en ${TERMINAL_COUNT} terminales`, async () => {
      if (runState.consoleIssues.length > 0) {
        throw new Error([...new Set(runState.consoleIssues)].join('\n'))
      }
      return 'sin hallazgos'
    })

    await check(`Sin page errors inesperados en ${TERMINAL_COUNT} terminales`, async () => {
      if (runState.pageErrors.length > 0)
        throw new Error([...new Set(runState.pageErrors)].join('\n'))
      return 'sin hallazgos'
    })
  } finally {
    if (contexts.length > 0) {
      await check('Cerrar turnos abiertos por terminal', async () => {
        const closed = await Promise.all(
          TERMINAL_IDS.map((terminalId) => closeTerminalTurn(terminalId))
        )
        return closed.join(' | ')
      })
    }
    await Promise.all(contexts.map(({ app }) => app.close().catch(() => {})))
  }
}

main()
  .then(() => {
    const failed = runState.checks.filter((item) => !item.ok)
    log(
      `SUMMARY ${JSON.stringify(
        {
          total: runState.checks.length,
          failed: failed.length,
          unexpectedHttpIssues: runState.httpIssues.length,
          unexpectedConsoleIssues: runState.consoleIssues.length,
          pageErrors: runState.pageErrors.length
        },
        null,
        2
      )}`
    )
    if (failed.length > 0) process.exitCode = 1
  })
  .catch((error) => {
    log(`FATAL | ${error instanceof Error ? error.stack || error.message : String(error)}`)
    const failed = runState.checks.filter((item) => !item.ok)
    log(
      `SUMMARY ${JSON.stringify(
        {
          total: runState.checks.length,
          failed: failed.length || 1,
          unexpectedHttpIssues: runState.httpIssues.length,
          unexpectedConsoleIssues: runState.consoleIssues.length,
          pageErrors: runState.pageErrors.length
        },
        null,
        2
      )}`
    )
    process.exit(1)
  })
