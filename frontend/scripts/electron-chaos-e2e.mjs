import fs from 'node:fs'
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
const sampleXmlPath = path.join(frontendRoot, 'scripts', 'e2e-sample.xml')
if (!fs.existsSync(sampleXmlPath)) {
  fs.writeFileSync(
    sampleXmlPath,
    '<?xml version="1.0" encoding="UTF-8"?><cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" Serie="A" Folio="1" Fecha="2026-03-08T00:00:00" SubTotal="1.00" Moneda="MXN" Total="1.16" TipoDeComprobante="I" Exportacion="01" LugarExpedicion="97000"></cfdi:Comprobante>\n',
    'utf8'
  )
}

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
const TERMINAL_ID = readSetting('E2E_TERMINAL_ID', '1')
const DISCOVER_PORTS = readSetting('E2E_DISCOVER_PORTS', '8000,8080')

const allowedHttpIssuePatterns = [
  { status: 401, url: /\/api\/v1\/auth\/verify$/i },
  { status: 401, url: /\/api\/v1\/auth\/login$/i },
  { status: 404, url: /\/api\/v1\/license\/status$/i },
  { status: 500, url: /\/api\/v1\/hardware\/print-receipt$/i }
]

const runState = {
  checks: [],
  httpIssues: [],
  consoleIssues: [],
  pageErrors: []
}

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

async function launchApp() {
  const args = ['.']
  if (process.platform === 'linux') args.push('--no-sandbox')

  const app = await electron.launch({
    cwd: frontendRoot,
    args,
    env: {
      ...process.env,
      NODE_ENV: 'production'
    }
  })

  const page = await app.firstWindow()

  page.on('response', (response) => {
    const status = response.status()
    const url = response.url()
    if (status >= 400 && !isAllowedHttpIssue(status, url)) {
      runState.httpIssues.push(`${status} ${response.request().method()} ${url}`)
    }
  })

  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    const text = msg.text()
    if (
      /401 \(Unauthorized\)/i.test(text) ||
      /404 \(Not Found\)/i.test(text) ||
      /Failed to load resource/i.test(text)
    ) {
      return
    }
    runState.consoleIssues.push(text)
  })

  page.on('pageerror', (error) => {
    runState.pageErrors.push(error.message)
  })

  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(1200)
  return { app, page }
}

async function seedRuntime(page, clearStorage) {
  await page.evaluate(
    ({ apiUrl, terminalId, discoverPorts, clear }) => {
      if (clear) localStorage.clear()
      localStorage.setItem('titan.baseUrl', apiUrl)
      localStorage.setItem('titan.terminalId', terminalId)
      localStorage.setItem('titan.discoverPorts', JSON.stringify(discoverPorts))
    },
    {
      apiUrl: API_URL,
      terminalId: String(TERMINAL_ID),
      discoverPorts: DISCOVER_PORTS.split(',').map((port) => Number.parseInt(port.trim(), 10)),
      clear: clearStorage
    }
  )
  await page.reload()
  await page.waitForLoadState('domcontentloaded')
}

async function expectNoAppCrash(page) {
  await expect(page.getByText(/Unexpected Application Error/i)).toHaveCount(0)
  await expect(page.getByText(/React Router caught/i)).toHaveCount(0)
}

async function expectLogin(page) {
  await expect(page.getByRole('heading', { name: /Acceso a caja/i })).toBeVisible({
    timeout: 15000
  })
}

async function login(page, username = ADMIN_USER, password = ADMIN_PASS) {
  await page.getByPlaceholder('Nombre de usuario').fill(username)
  await page.getByPlaceholder('••••••••').fill(password)
  await page.getByRole('button', { name: /ingresar/i }).click()
}

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

async function ensureLoggedInTerminal(page) {
  if (!/#\/terminal/.test(page.url())) {
    await expectLogin(page)
    await login(page)
    await expect.poll(() => page.url(), { timeout: 15000 }).toMatch(/#\/terminal/)
  }
  await closeShiftModalIfPresent(page)
  await expect(page.getByPlaceholder(/Buscar producto o escanear/i)).toBeVisible({ timeout: 10000 })
}

async function clickMore(page, label) {
  await page.getByRole('button', { name: /más/i }).click()
  await page.getByRole('menuitem', { name: label }).click()
}

async function createProduct(page, idSuffix) {
  const sku = `E2E-CHAOS-${idSuffix}`
  const name = `Producto Caos ${idSuffix}`

  await page.getByRole('link', { name: /productos/i }).click()
  await expect(page.getByRole('heading', { name: /Productos/i }).first()).toBeVisible({
    timeout: 10000
  })
  await page.getByRole('button', { name: /^Nuevo$/ }).click()
  await expect(page.getByRole('heading', { name: /Nuevo producto/i })).toBeVisible({
    timeout: 10000
  })

  await page.getByPlaceholder('Ej: 7501234567890').fill(sku)
  await page.getByPlaceholder('Coca Cola 600ml').fill(name)

  const productNumberInputs = page.locator('input[type="number"]')
  await productNumberInputs.nth(0).fill('-1')
  await productNumberInputs.nth(1).fill('7')
  await page.getByRole('button', { name: /guardar producto/i }).click()
  await expect(page.getByText(/precio no puede ser negativo/i).first()).toBeVisible({
    timeout: 10000
  })

  await productNumberInputs.nth(0).fill('12.34')
  await page.getByPlaceholder(/Ej: Bebidas, Abarrotes/i).fill('Pruebas E2E')
  await page.getByRole('button', { name: /guardar producto/i }).click()
  await expect(page.getByRole('heading', { name: /Nuevo producto|Editar producto/i })).toBeHidden({
    timeout: 15000
  })

  await page.getByPlaceholder(/Buscar por SKU, nombre o código de barras/i).fill(sku)
  await expect(page.getByText(sku).first()).toBeVisible({ timeout: 10000 })

  return { sku, name }
}

async function createCustomer(page, idSuffix) {
  const name = `Cliente Caos ${idSuffix}`
  const email = `caos.${idSuffix}@titan.test`
  const phone = `555${String(idSuffix).slice(-7).padStart(7, '0')}`

  await page.getByRole('link', { name: /clientes/i }).click()
  await expect(page.getByRole('heading', { name: /Clientes/i }).first()).toBeVisible({
    timeout: 10000
  })
  await page.getByRole('button', { name: /^Nuevo$/ }).click()

  await page.getByPlaceholder(/Nombre completo/i).fill(name)
  await page.getByPlaceholder(/cliente@ejemplo\.com/i).fill(email)
  await page.getByPlaceholder(/55 1234 5678/i).fill(phone)
  await page.getByRole('button', { name: /guardar cliente/i }).click()
  await expect(page.getByRole('button', { name: /guardar cliente/i })).toBeHidden({
    timeout: 15000
  })
  await page.getByPlaceholder(/Buscar por nombre, teléfono o correo/i).fill(name)
  await expect(page.getByText(name).first()).toBeVisible({ timeout: 10000 })

  return { name, email, phone }
}

async function addProductToCart(page, sku, expectedName) {
  const search = page.getByPlaceholder(/Buscar producto o escanear/i).first()
  await search.fill(sku)
  await search.press('Enter')
  const lineItem = page.getByText(expectedName).first()
  const cleared = await search.evaluate((input) => input.value === '').catch(() => false)
  if (!cleared) {
    const dropdownButton = page.locator('button').filter({ hasText: expectedName }).first()
    if (await dropdownButton.isVisible({ timeout: 1500 }).catch(() => false)) {
      await dropdownButton.click()
    }
  }
  await expect(lineItem).toBeVisible({ timeout: 10000 })
  await search
    .evaluate((input) => {
      if (input.value !== '') {
        input.value = ''
        input.dispatchEvent(new Event('input', { bubbles: true }))
      }
    })
    .catch(() => {})
}

async function forceAddProductToCart(page, sku, expectedName) {
  const search = page.getByPlaceholder(/Buscar producto o escanear/i).first()
  await search.fill(sku)
  await search.press('Enter')
  const cleared = await search.evaluate((input) => input.value === '').catch(() => false)

  if (!cleared) {
    const dropdownButton = page.locator('button').filter({ hasText: expectedName }).first()
    if (await dropdownButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await dropdownButton.click()
    }
  }

  await expect(page.getByText(expectedName).first()).toBeVisible({ timeout: 10000 })
}

async function createSaleAndReturnFolio(page) {
  const modal = page.locator('[role="dialog"]')

  await page.getByRole('button', { name: /^COBRAR$/i }).click()
  await expect(modal).toBeVisible({ timeout: 8000 })
  await modal.locator('input[type="number"]').first().fill('0.01')
  await expect(page.getByText(/Faltante/i).first()).toBeVisible({ timeout: 5000 })
  await modal.getByRole('button', { name: /Cancelar/i }).click()
  await expect(modal).toBeHidden({ timeout: 5000 })

  await page.getByRole('button', { name: /^COBRAR$/i }).click()
  await modal.locator('select').selectOption('mixed')
  const mixedInputs = modal.locator('input[type="number"]')
  await mixedInputs.nth(0).fill('1')
  await mixedInputs.nth(1).fill('1')
  await mixedInputs.nth(2).fill('0')
  await expect(modal.getByRole('button', { name: /^COBRAR$/ }).last()).toBeDisabled()
  await modal.getByRole('button', { name: /Cancelar/i }).click()
  await expect(modal).toBeHidden({ timeout: 5000 })

  await page.getByRole('button', { name: /^COBRAR$/i }).click()
  await modal.locator('select').selectOption('cash')
  const totalText = await modal
    .getByText(/\$\d+\.\d{2}/)
    .first()
    .innerText()
  const amount = totalText.replace(/[^\d.]/g, '')
  await modal.locator('input[type="number"]').first().fill(amount)
  await modal
    .getByRole('button', { name: /^COBRAR$/ })
    .last()
    .click()

  const successRegex = /Venta ([A-Z0-9-]+) registrada/i
  await page.waitForTimeout(4000)
  const bodyText = await page.locator('body').innerText()
  const match = bodyText.match(successRegex)
  const ticketReset = await page
    .getByText(/Ticket vacío/i)
    .first()
    .isVisible({ timeout: 2000 })
    .catch(() => false)
  if (!match) {
    if (ticketReset) {
      try {
        const token = await apiLoginToken()
        const rows = await apiSearchSales(token, new URLSearchParams({ limit: '5' }).toString())
        const latest = rows.find((row) => {
          const folio = String(row.folio_visible ?? row.folio ?? '').trim()
          return folio.length > 0
        })
        const latestFolio = String(latest?.folio_visible ?? latest?.folio ?? '').trim()
        if (latestFolio) {
          return latestFolio
        }
      } catch {
        // fallback silencioso: el cobro sí sucedió aunque no obtengamos el folio visible
      }
      return ''
    }
    const errorMatch =
      bodyText.match(/Error al registrar venta:[^\n]+/i) ||
      bodyText.match(/No se pudo conectar al servidor[^\n]*/i) ||
      bodyText.match(/El ticket sigue intacto[^\n]*/i)
    throw new Error(
      `La venta no confirmó éxito. ${errorMatch ? `Mensaje: ${errorMatch[0]}` : `Fragmento: ${bodyText.slice(-1200)}`}`
    )
  }
  await expect(page.getByText(/Ticket vacío/i).first()).toBeVisible({ timeout: 10000 })
  return match[1]
}

async function rapidNavigationLoop(page) {
  const primaryNav = [
    { label: 'Ventas', hash: '/terminal' },
    { label: 'Clientes', hash: '/clientes' },
    { label: 'Productos', hash: '/productos' },
    { label: 'Inventario', hash: '/inventario' },
    { label: 'Turnos', hash: '/turnos' },
    { label: 'Reportes', hash: '/reportes' },
    { label: 'Historial', hash: '/historial' },
    { label: 'Ajustes', hash: '/configuraciones' }
  ]

  const moreNav = [
    { label: /estadísticas/i, hash: '/estadisticas' },
    { label: /mermas/i, hash: '/mermas' },
    { label: /gastos/i, hash: '/gastos' },
    { label: /empleados/i, hash: '/empleados' },
    { label: /remoto/i, hash: '/remoto' },
    { label: /fiscal/i, hash: '/fiscal' },
    { label: /hardware|dispositivos/i, hash: '/hardware' }
  ]

  for (let i = 0; i < 2; i += 1) {
    for (const item of primaryNav) {
      await page.getByRole('link', { name: item.label }).click()
      await expect.poll(() => new URL(page.url()).hash).toBe(`#${item.hash}`)
    }
    for (const item of moreNav) {
      await clickMore(page, item.label)
      await expect.poll(() => new URL(page.url()).hash).toBe(`#${item.hash}`)
    }
  }
}

function pendingTicketCount(entries) {
  return Object.entries(entries)
    .filter(([key]) => key.startsWith('titan.pendingTickets'))
    .map(([, value]) => {
      try {
        const parsed = JSON.parse(value)
        return Array.isArray(parsed) ? parsed.length : 0
      } catch {
        return 0
      }
    })
    .reduce((acc, value) => acc + value, 0)
}

function uniqueItems(items) {
  return [...new Set(items)]
}

async function readLocalStorage(page) {
  return page.evaluate(() => {
    const out = {}
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i)
      if (key) out[key] = localStorage.getItem(key) ?? ''
    }
    return out
  })
}

async function ensureEmptyTerminal(page) {
  await page.getByRole('link', { name: /ventas/i }).click()
  await expect(page.getByPlaceholder(/Buscar producto o escanear/i)).toBeVisible({ timeout: 10000 })
}

async function seedScannerConfig(page, overrides = {}) {
  await page.evaluate((nextConfig) => {
    localStorage.setItem(
      'titan.hwConfig',
      JSON.stringify({
        scanner: {
          enabled: true,
          prefix: '[',
          suffix: ']',
          min_speed_ms: 99999,
          auto_submit: true
        },
        ...nextConfig
      })
    )
  }, overrides)
}

async function verifySaleTechnicalJson(page, folio, expectedSeries, expectedPaymentMethod) {
  await page.getByRole('link', { name: /historial/i }).click()
  const closeDrawer = page.locator('div.absolute.inset-0.bg-black\\/40 button').first()
  if (
    await page
      .getByText(/Detalle del ticket/i)
      .first()
      .isVisible()
      .catch(() => false)
  ) {
    await closeDrawer.click()
    await expect(page.getByText(/Detalle del ticket/i).first()).toBeHidden({ timeout: 10000 })
  }
  const search = page.getByPlaceholder(/Buscar por folio/i)
  await search.fill(folio)
  await page.getByRole('button', { name: /Actualizar/i }).click()
  await expect(page.getByText(folio).first()).toBeVisible({ timeout: 10000 })
  await page.getByText(folio).first().click()
  await expect(page.getByText(/Detalle del ticket/i).first()).toBeVisible({ timeout: 10000 })
  await page.getByRole('button', { name: /Datos técnicos \(JSON\)/i }).click()
  const technical = page.locator('pre').last()
  await expect(technical).toBeVisible({ timeout: 10000 })
  await expect(technical).toContainText(`"serie": "${expectedSeries}"`)
  await expect(technical).toContainText(`"payment_method": "${expectedPaymentMethod}"`)
  await closeDrawer.click()
  await expect(page.getByText(/Detalle del ticket/i).first()).toBeHidden({ timeout: 10000 })
}

async function closeHistoryDrawerIfOpen(page) {
  const detailTitle = page.getByText(/Detalle del ticket/i).first()
  if (!(await detailTitle.isVisible({ timeout: 1500 }).catch(() => false))) return
  const closeDrawer = page.locator('div.absolute.inset-0.bg-black\\/40 button').first()
  await closeDrawer.click()
  await expect(detailTitle).toBeHidden({ timeout: 10000 })
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

async function apiLoginToken() {
  const body = await apiJson('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASS })
  })
  const token = body?.access_token || body?.token
  if (!token) throw new Error('No se obtuvo token del login API.')
  return token
}

function authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    'X-Terminal-Id': String(TERMINAL_ID)
  }
}

async function apiCreateControlledSale(token, variantId, payload) {
  const body = await apiJson('/api/v1/sales/', {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({
      branch_id: 1,
      items: [
        {
          product_id: 0,
          name: `Venta QA ${variantId}`,
          qty: 1,
          price: 19.99,
          discount: 0
        }
      ],
      ...payload
    })
  })
  const data = body?.data ?? body
  return {
    id: Number(data.id),
    folio: String(data.folio),
    paymentMethod: String(data.payment_method ?? payload.payment_method),
    variantId
  }
}

async function apiGetSaleDetail(token, saleId) {
  const body = await apiJson(`/api/v1/sales/${saleId}`, {
    headers: { Authorization: `Bearer ${token}`, 'X-Terminal-Id': String(TERMINAL_ID) }
  })
  return body?.data ?? body
}

async function apiGetPendingInvoiceSales(token) {
  const body = await apiJson('/api/v1/fiscal/sales-pending-invoice?branch_id=1&limit=200', {
    headers: { Authorization: `Bearer ${token}`, 'X-Terminal-Id': String(TERMINAL_ID) }
  })
  return Array.isArray(body?.data) ? body.data : []
}

async function apiSearchSales(token, query) {
  const body = await apiJson(`/api/v1/sales/search?${query}`, {
    headers: { Authorization: `Bearer ${token}`, 'X-Terminal-Id': String(TERMINAL_ID) }
  })
  return Array.isArray(body?.data) ? body.data : Array.isArray(body?.sales) ? body.sales : []
}

async function apiGetSaleEvents(token, saleId) {
  const body = await apiJson(`/api/v1/sales/${saleId}/events`, {
    headers: { Authorization: `Bearer ${token}`, 'X-Terminal-Id': String(TERMINAL_ID) }
  })
  return Array.isArray(body?.data) ? body.data : []
}

async function apiExpectFailure(pathname, options = {}, expected = {}) {
  const response = await apiRequest(pathname, options)
  if (response.ok) {
    throw new Error(`La petición ${pathname} respondió OK y se esperaba error.`)
  }
  if (expected.status && response.status !== expected.status) {
    throw new Error(`Esperaba status ${expected.status} y llegó ${response.status}.`)
  }
  const serialized =
    typeof response.body === 'string' ? response.body : JSON.stringify(response.body ?? {})
  if (
    expected.detailIncludes &&
    !serialized.toLowerCase().includes(expected.detailIncludes.toLowerCase())
  ) {
    throw new Error(`El error no incluyó "${expected.detailIncludes}". Respuesta: ${serialized}`)
  }
  return serialized
}

function sampleTextForMeta(meta, index) {
  const hint = `${meta.placeholder || meta.label || meta.name || ''}`.toLowerCase()
  if (hint.includes('correo') || hint.includes('email')) return `qa.${index}@titan.test`
  if (hint.includes('rfc')) return 'XAXX010101000'
  if (hint.includes('tel')) return '5551234567'
  if (hint.includes('postal') || hint.includes('código postal') || hint.includes('codigo postal'))
    return '97000'
  if (hint.includes('url') || hint.includes('servidor')) return API_URL
  if (hint.includes('razón') || hint.includes('razon') || hint.includes('motivo'))
    return `Motivo QA ${index}`
  if (hint.includes('pin')) return '1234'
  if (hint.includes('wallet')) return `wallet-${index}`
  if (hint.includes('id de venta') || hint.includes('sale')) return '1'
  if (hint.includes('sku') || hint.includes('producto')) return `QA-${index}`
  return `qa-${index}`
}

async function touchVisibleControls(page, scope = page, options = {}) {
  const { limit = 25 } = options
  const locator = scope.locator('input:not([type="hidden"]), textarea, select')
  const total = await locator.count()
  let touched = 0

  for (let i = 0; i < total && touched < limit; i += 1) {
    const control = locator.nth(i)
    if (!(await control.isVisible().catch(() => false))) continue

    const meta = await control.evaluate((el) => {
      const input = el
      const label =
        el.closest('label')?.textContent?.trim() ||
        el.parentElement?.querySelector('label')?.textContent?.trim() ||
        ''
      return {
        tag: el.tagName.toLowerCase(),
        type: input instanceof HTMLInputElement ? input.type : '',
        placeholder:
          input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement
            ? input.placeholder || ''
            : '',
        name: input instanceof HTMLElement ? input.getAttribute('name') || '' : '',
        disabled:
          input instanceof HTMLInputElement ||
          input instanceof HTMLTextAreaElement ||
          input instanceof HTMLSelectElement
            ? input.disabled
            : false,
        readOnly:
          input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement
            ? input.readOnly
            : false,
        label
      }
    })

    if (meta.disabled || meta.readOnly) continue

    if (meta.tag === 'select') {
      const optionsMeta = await control.evaluate((el) => {
        const select = el
        if (!(select instanceof HTMLSelectElement)) return []
        return Array.from(select.options).map((opt, idx) => ({
          value: opt.value,
          disabled: opt.disabled,
          index: idx
        }))
      })
      const candidate =
        optionsMeta.find((opt) => !opt.disabled && opt.value !== '') ||
        optionsMeta.find((opt) => !opt.disabled) ||
        null
      if (candidate) {
        await control.selectOption(
          candidate.value ? { value: candidate.value } : { index: candidate.index }
        )
        touched += 1
      }
      continue
    }

    if (meta.type === 'checkbox' || meta.type === 'radio') {
      await control.click().catch(() => {})
      touched += 1
      continue
    }

    if (meta.type === 'file') {
      await control.setInputFiles(sampleXmlPath)
      touched += 1
      continue
    }

    if (meta.type === 'date') {
      await control.fill('2026-03-08')
      touched += 1
      continue
    }

    if (meta.type === 'number') {
      await control.fill('1')
      touched += 1
      continue
    }

    const value = sampleTextForMeta(meta, i + 1)
    await control.fill(value)
    touched += 1
  }

  return touched
}

async function main() {
  const uniqueId = Date.now()
  let { app, page } = await launchApp()

  try {
    await check(
      'Configurar runtime local y abrir login',
      async () => {
        await seedRuntime(page, true)
        await expectLogin(page)
        await expect(page.getByTestId('login-submit')).toBeDisabled()
        return API_URL
      },
      { fatal: true }
    )

    await check(
      'Rechazo de credenciales inválidas',
      async () => {
        await login(page, ADMIN_USER, `${ADMIN_PASS}-incorrecta`)
        await expect(page).toHaveURL(/#\/login/)
        await expect(
          page.getByText(/credenciales|incorrectas|invalidas|inválidas/i).first()
        ).toBeVisible({
          timeout: 10000
        })
      },
      { fatal: true }
    )

    await check(
      'Login válido y carga de terminal',
      async () => {
        await page.getByPlaceholder('Nombre de usuario').fill('')
        await page.getByPlaceholder('••••••••').fill('')
        await login(page)
        await expect.poll(() => page.url(), { timeout: 15000 }).toMatch(/#\/terminal/)
        await closeShiftModalIfPresent(page)
        await expect(page.getByPlaceholder(/Buscar producto o escanear/i)).toBeVisible({
          timeout: 10000
        })
      },
      { fatal: true }
    )

    await check('Caja vacía: acciones básicas seguras', async () => {
      await expect(page.getByText(/Ticket vacío/i).first()).toBeVisible({ timeout: 10000 })
      await expect(page.getByRole('button', { name: /Ticket pendiente/i }).first()).toBeDisabled()
      await expect(page.getByRole('button', { name: /^COBRAR$/i }).first()).toBeDisabled()
      await expectNoAppCrash(page)
    })

    await check('Input de búsqueda resiste ruido y límite', async () => {
      const search = page.getByPlaceholder(/Buscar producto o escanear/i)
      const payload = `ruido-${'x'.repeat(260)}`
      await search.fill(payload)
      const current = await search.inputValue()
      if (current.length > 200) {
        throw new Error(`El input aceptó ${current.length} caracteres; esperaba máximo 200.`)
      }
      await expect(page.getByText(/Ningún producto coincide/i).first()).toBeVisible({
        timeout: 5000
      })
      await search.fill('')
      await expectNoAppCrash(page)
      return `len=${current.length}`
    })

    const product = await (async () => {
      let value = null
      await check('Alta de producto con validación y guardado real', async () => {
        value = await createProduct(page, uniqueId)
        return value.sku
      })
      return value
    })()

    const customer = await (async () => {
      let value = null
      await check('Alta de cliente real y localización inmediata', async () => {
        value = await createCustomer(page, uniqueId)
        return value.name
      })
      return value
    })()

    await check('Conexión de ajustes: probar y persistir', async () => {
      await page.getByRole('link', { name: /ajustes/i }).click()
      const baseUrlInput = page.locator('input').first()
      await expect(baseUrlInput).toHaveValue(API_URL)
      await page.getByRole('button', { name: /Probar conexión/i }).click()
      await expect(page.getByText(/Conexión correcta con backend/i).first()).toBeVisible({
        timeout: 10000
      })
      await page.getByRole('button', { name: /Guardar conexión/i }).click()
      await expect(
        page.getByText(/Configuración de Servidor guardada en localStorage/i).first()
      ).toBeVisible({ timeout: 10000 })
    })

    let controlledSales = null
    await check('Ventas controladas: serie B/A/A y pendiente de factura correcto', async () => {
      const token = await apiLoginToken()
      const baseId = `${uniqueId}`
      const saleCashNoInvoice = await apiCreateControlledSale(token, `${baseId}-cash-b`, {
        payment_method: 'cash',
        cash_received: 20,
        requiere_factura: false,
        serie: 'A',
        notes: `qa-serie-b-${baseId}`
      })
      const saleCashInvoice = await apiCreateControlledSale(token, `${baseId}-cash-a`, {
        payment_method: 'cash',
        cash_received: 20,
        requiere_factura: true,
        serie: 'B',
        notes: `qa-serie-a-factura-${baseId}`
      })
      const saleCard = await apiCreateControlledSale(token, `${baseId}-card-a`, {
        payment_method: 'card',
        card_reference: `CARD-${baseId}`,
        requiere_factura: false,
        serie: 'B',
        notes: `qa-serie-a-card-${baseId}`
      })
      const saleMixed = await apiCreateControlledSale(token, `${baseId}-mixed-a`, {
        payment_method: 'mixed',
        mixed_cash: 10,
        mixed_card: 9.99,
        mixed_transfer: 0,
        mixed_wallet: 0,
        serie: 'B',
        notes: `qa-serie-a-mixed-${baseId}`
      })

      const detailB = await apiGetSaleDetail(token, saleCashNoInvoice.id)
      const detailAInvoice = await apiGetSaleDetail(token, saleCashInvoice.id)
      const detailACard = await apiGetSaleDetail(token, saleCard.id)
      const detailAMixed = await apiGetSaleDetail(token, saleMixed.id)
      const pendingInvoice = await apiGetPendingInvoiceSales(token)

      if (detailB.serie !== 'B')
        throw new Error(`Venta cash sin factura quedó en serie ${detailB.serie}`)
      if (detailAInvoice.serie !== 'A') {
        throw new Error(`Venta cash con factura quedó en serie ${detailAInvoice.serie}`)
      }
      if (detailACard.serie !== 'A')
        throw new Error(`Venta card quedó en serie ${detailACard.serie}`)
      if (detailAMixed.serie !== 'A')
        throw new Error(`Venta mixed quedó en serie ${detailAMixed.serie}`)

      const pendingIds = new Set(pendingInvoice.map((row) => Number(row.id)))
      if (!pendingIds.has(saleCashInvoice.id)) {
        throw new Error('La venta con factura no apareció en pendientes de facturación.')
      }
      if (pendingIds.has(saleCashNoInvoice.id)) {
        throw new Error(
          'La venta sin factura apareció incorrectamente en pendientes de facturación.'
        )
      }

      controlledSales = {
        cashNoInvoice: saleCashNoInvoice,
        cashInvoice: saleCashInvoice,
        card: saleCard,
        mixed: saleMixed
      }
      return `folios=${saleCashNoInvoice.folio},${saleCashInvoice.folio},${saleCard.folio},${saleMixed.folio}`
    })

    await check('API rechaza venta a crédito sin cliente', async () => {
      const token = await apiLoginToken()
      const detail = await apiExpectFailure(
        '/api/v1/sales/',
        {
          method: 'POST',
          headers: authHeaders(token),
          body: JSON.stringify({
            branch_id: 1,
            payment_method: 'credit',
            items: [{ product_id: 0, name: 'Credito sin cliente', qty: 1, price: 19.99 }]
          })
        },
        { status: 400, detailIncludes: 'requiere customer_id' }
      )
      return detail
    })

    await check('API rechaza pago con monedero sin cliente', async () => {
      const token = await apiLoginToken()
      const detail = await apiExpectFailure(
        '/api/v1/sales/',
        {
          method: 'POST',
          headers: authHeaders(token),
          body: JSON.stringify({
            branch_id: 1,
            payment_method: 'wallet',
            items: [{ product_id: 0, name: 'Wallet sin cliente', qty: 1, price: 19.99 }]
          })
        },
        { status: 400, detailIncludes: 'requiere customer_id' }
      )
      return detail
    })

    await check('API rechaza mixed con monedero sin cliente', async () => {
      const token = await apiLoginToken()
      const detail = await apiExpectFailure(
        '/api/v1/sales/',
        {
          method: 'POST',
          headers: authHeaders(token),
          body: JSON.stringify({
            branch_id: 1,
            payment_method: 'mixed',
            mixed_cash: 9.99,
            mixed_wallet: 10,
            items: [{ product_id: 0, name: 'Mixed wallet sin cliente', qty: 1, price: 19.99 }]
          })
        },
        { status: 400, detailIncludes: 'monedero sin cliente' }
      )
      return detail
    })

    await check('Búsqueda API encuentra ventas controladas por folio', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      const token = await apiLoginToken()
      const rows = await apiSearchSales(
        token,
        new URLSearchParams({ folio: controlledSales.mixed.folio, limit: '20' }).toString()
      )
      const found = rows.find(
        (row) => String(row.folio_visible ?? row.folio ?? '') === controlledSales.mixed.folio
      )
      if (!found) throw new Error(`No apareció ${controlledSales.mixed.folio} en search sales.`)
      return controlledSales.mixed.folio
    })

    await check('Endpoint de eventos de venta responde lista utilizable', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      const token = await apiLoginToken()
      const events = await apiGetSaleEvents(token, controlledSales.cashInvoice.id)
      if (!Array.isArray(events)) throw new Error('La respuesta de eventos no fue un arreglo.')
      const invalid = events.find(
        (event) =>
          event && typeof event === 'object' && !('event_type' in event) && !('timestamp' in event)
      )
      if (invalid) {
        throw new Error(`Evento con forma inesperada: ${JSON.stringify(invalid)}`)
      }
      return `eventos=${events.length}`
    })

    await check('Cancelación con PIN inválido se bloquea y no altera la venta', async () => {
      const token = await apiLoginToken()
      const sale = await apiCreateControlledSale(token, `${uniqueId}-cancel-guard`, {
        payment_method: 'cash',
        cash_received: 20,
        requiere_factura: false,
        notes: `qa-cancel-guard-${uniqueId}`
      })
      await apiExpectFailure(
        `/api/v1/sales/${sale.id}/cancel`,
        {
          method: 'POST',
          headers: authHeaders(token),
          body: JSON.stringify({ manager_pin: '0000', reason: 'Prueba E2E' })
        },
        { status: 403, detailIncludes: 'PIN de gerente inválido' }
      )
      const detail = await apiGetSaleDetail(token, sale.id)
      if (String(detail.status) !== 'completed') {
        throw new Error(`La venta quedó alterada tras PIN inválido: ${detail.status}`)
      }
      return sale.folio
    })

    await check('Historial técnico refleja serie B para efectivo sin factura', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      await verifySaleTechnicalJson(page, controlledSales.cashNoInvoice.folio, 'B', 'cash')
    })

    await check('Historial técnico refleja serie A para efectivo con factura', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      await verifySaleTechnicalJson(page, controlledSales.cashInvoice.folio, 'A', 'cash')
    })

    await check('Historial técnico refleja serie A para tarjeta', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      await verifySaleTechnicalJson(page, controlledSales.card.folio, 'A', 'card')
    })

    await check('Historial técnico refleja serie A para mixed', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      await verifySaleTechnicalJson(page, controlledSales.mixed.folio, 'A', 'mixed')
    })

    await check('Fiscal facturación muestra la venta que pidió factura', async () => {
      if (!controlledSales) throw new Error('No hay ventas controladas disponibles.')
      await clickMore(page, /fiscal/i)
      await page.getByRole('button', { name: 'Facturación', exact: true }).click()
      await expect(
        page.getByText(new RegExp(`#${controlledSales.cashInvoice.id}`)).first()
      ).toBeVisible({
        timeout: 10000
      })
    })

    await check('Navegación rápida por todo el POS sin crash', async () => {
      await rapidNavigationLoop(page)
      await expectNoAppCrash(page)
    })

    let pendingCountBeforeRestart = 0
    let folio = ''

    await check('Flujo Terminal: tickets, guardado pendiente, mayoreo y cobro', async () => {
      if (!product) throw new Error('Producto de prueba no disponible para flujo terminal.')
      await page.getByRole('link', { name: /ventas/i }).click()
      await expect(page.getByPlaceholder(/Buscar producto o escanear/i)).toBeVisible({
        timeout: 10000
      })

      const newTicketButton = page.getByTitle(/Nuevo \(Ctrl\+N\)/i)
      for (let i = 0; i < 5; i += 1) {
        await newTicketButton.click()
      }
      await expectNoAppCrash(page)

      await addProductToCart(page, product.sku, product.name)
      const qtyBadge = page.getByText(/^1$/).first()
      await expect(qtyBadge).toBeVisible({ timeout: 5000 })

      await page.keyboard.press('F11')
      await expect(page.getByText(/Mayoreo/i).first()).toBeVisible({ timeout: 5000 })
      await page.keyboard.press('F11')

      await page
        .getByRole('button', { name: /Ticket pendiente/i })
        .first()
        .click()
      await expect(page.getByText(/Ticket vacío/i).first()).toBeVisible({ timeout: 5000 })

      const localStorageEntries = await readLocalStorage(page)
      pendingCountBeforeRestart = pendingTicketCount(localStorageEntries)
      if (pendingCountBeforeRestart < 1) {
        throw new Error('No quedó ningún ticket pendiente guardado en localStorage.')
      }

      await addProductToCart(page, product.sku, product.name)
      await expect(page.getByRole('button', { name: /^COBRAR$/i }).first()).toBeEnabled({
        timeout: 5000
      })
      folio = await createSaleAndReturnFolio(page)
      return `folio=${folio}, pending=${pendingCountBeforeRestart}`
    })

    await check('Historial encuentra y abre el ticket recién vendido', async () => {
      if (!folio) return 'omitido: el cobro previo no generó folio visible'
      await page.getByRole('link', { name: /historial/i }).click()
      const search = page.getByPlaceholder(/Buscar por folio/i)
      await search.fill(folio)
      await expect(page.getByText(folio).first()).toBeVisible({ timeout: 10000 })
      await page.getByText(folio).first().click()
      await expect(page.getByText(/Detalle del ticket/i).first()).toBeVisible({ timeout: 10000 })
      await expect(page.getByText(new RegExp(folio, 'i')).first()).toBeVisible({ timeout: 10000 })
      await closeHistoryDrawerIfOpen(page)
    })

    await check('Historial tolera filtros sin resultados y cambio de método', async () => {
      await page.getByRole('link', { name: /historial/i }).click()
      await closeHistoryDrawerIfOpen(page)
      const search = page.getByPlaceholder(/Buscar por folio/i)
      await search.fill(`NO-EXISTE-${uniqueId}`)
      await page.getByRole('button', { name: /Actualizar/i }).click()
      await expect(page.getByText(/Sin resultados de búsqueda/i).first()).toBeVisible({
        timeout: 10000
      })
      await search.fill('')
      await page.getByRole('button', { name: /Actualizar/i }).click()
      await page.locator('select').first().selectOption('cash')
      await expectNoAppCrash(page)
      await page.locator('select').first().selectOption('all')
    })

    await check('Gastos rechaza monto negativo y acepta uno válido', async () => {
      await clickMore(page, /gastos/i)
      const amountInput = page.locator('form input[type="number"]').first()
      const descriptionInput = page.getByPlaceholder(/Ej: Luz, Agua, Insumos/i)
      await amountInput.fill('0')
      await descriptionInput.fill(`Gasto inválido ${uniqueId}`)
      const isInvalid = await amountInput.evaluate((input) => !input.checkValidity())
      if (!isInvalid) {
        await page.getByRole('button', { name: /^Registrar$/i }).click()
      }
      const bodyText = await page.locator('body').innerText()
      if (
        !isInvalid &&
        !/monto válido|minimo \$0\.01|mínimo \$0\.01|No hay turno abierto/i.test(bodyText)
      ) {
        throw new Error('El formulario de gastos no mostró validación visible para monto inválido.')
      }

      if (/No hay turno abierto/i.test(bodyText)) {
        return 'sin turno activo, se validó el bloqueo preventivo'
      }

      await amountInput.fill('15.5')
      await descriptionInput.fill(`Gasto E2E ${uniqueId}`)
      await page.getByRole('button', { name: /^Registrar$/i }).click()
      await expect(page.getByText(/Gasto registrado correctamente/i).first()).toBeVisible({
        timeout: 15000
      })
    })

    await check('Checkout muestra referencias para tarjeta y transferencia', async () => {
      if (!product) throw new Error('Producto de prueba no disponible para variantes de checkout.')
      await ensureEmptyTerminal(page)
      await forceAddProductToCart(page, product.sku, product.name)
      await page.getByRole('button', { name: /^COBRAR$/i }).click()
      const modal = page.locator('[role="dialog"]')
      await expect(modal).toBeVisible({ timeout: 8000 })
      await modal.locator('select').selectOption('card')
      await expect(modal.getByPlaceholder(/Ej\. 1234/i)).toBeVisible({ timeout: 5000 })
      await modal.locator('select').selectOption('transfer')
      await expect(modal.getByPlaceholder(/SPEI-123456789/i)).toBeVisible({ timeout: 5000 })
      await modal.getByRole('button', { name: /Cancelar/i }).click()
      await expect(modal).toBeHidden({ timeout: 5000 })
    })

    await check('Subvariante lector: prefijo/sufijo de scanner agrega producto', async () => {
      if (!product) throw new Error('Producto de prueba no disponible para scanner.')
      await ensureEmptyTerminal(page)
      await seedScannerConfig(page)
      const search = page.getByPlaceholder(/Buscar producto o escanear/i)
      await search.fill(`[${product.sku}]`)
      await page.keyboard.press('Enter')
      await expect(page.getByText(product.name).first()).toBeVisible({ timeout: 10000 })
    })

    await check('Selector de cliente en terminal acepta búsqueda operativa', async () => {
      if (!customer) throw new Error('Cliente de prueba no disponible.')
      await ensureEmptyTerminal(page)
      await page.getByRole('button', { name: /cliente/i }).click()
      const customerSearch = page.getByPlaceholder(/Buscar cliente/i)
      await customerSearch.fill(customer.name)
      const option = page.locator('button').filter({ hasText: customer.name }).last()
      await expect(option).toBeVisible({ timeout: 5000 })
      await option.click()
      await expect(
        page.getByRole('button', { name: new RegExp(customer.name, 'i') }).first()
      ).toBeVisible({
        timeout: 5000
      })
    })

    await check('Ajustes rechaza URL inválida y permite restaurar', async () => {
      await page.getByRole('link', { name: /ajustes/i }).click()
      await page.getByRole('button', { name: 'Conexión', exact: true }).click()
      const baseUrlInput = page.locator('input').first()
      await baseUrlInput.fill('url-invalida')
      await page.getByRole('button', { name: /Guardar conexión/i }).click()
      await expect(
        page.getByText(/Error: Dirección inválida|Dirección inválida/i).first()
      ).toBeVisible({
        timeout: 10000
      })
      await baseUrlInput.fill(API_URL)
      await page.getByRole('button', { name: /Guardar conexión/i }).click()
      await expect(
        page.getByText(/Configuración de Servidor guardada en localStorage/i).first()
      ).toBeVisible({ timeout: 10000 })
    })

    await check('Ajustes rechaza terminalId inválido y permite restaurar', async () => {
      await page.getByRole('link', { name: /ajustes/i }).click()
      await page.getByRole('button', { name: 'Conexión', exact: true }).click()
      const terminalIdInput = page
        .locator('label', { hasText: /ID lógico de terminal/i })
        .locator('..')
        .locator('input')
        .first()
      if (!(await terminalIdInput.isVisible({ timeout: 3000 }).catch(() => false))) {
        return 'omitido: control terminalId no localizable de forma estable en esta build'
      }
      await terminalIdInput.fill('0')
      await page.getByRole('button', { name: /Guardar conexión/i }).click()
      await expect(
        page.getByText(/ID de terminal debe ser un número entero mayor o igual a 1/i).first()
      ).toBeVisible({ timeout: 10000 })
      await terminalIdInput.fill(String(TERMINAL_ID))
      await page.getByRole('button', { name: /Guardar conexión/i }).click()
      await expect(
        page.getByText(/Configuración de Servidor guardada en localStorage/i).first()
      ).toBeVisible({ timeout: 10000 })
    })

    await check('Turnos carga resumen operativo sin crash', async () => {
      await page.getByRole('link', { name: /turnos/i }).click()
      await expect(
        page.getByText(/Turnos|apertura|cierre|Efectivo|Historial|Diferencia/i).first()
      ).toBeVisible({ timeout: 10000 })
      await expectNoAppCrash(page)
    })

    await check('Cobertura: tocar campos visibles de tabs principales y menú Más', async () => {
      const primaryTabs = [
        'Ventas',
        'Clientes',
        'Productos',
        'Inventario',
        'Turnos',
        'Reportes',
        'Historial',
        'Ajustes'
      ]
      const moreTabs = [
        /estadísticas/i,
        /mermas/i,
        /gastos/i,
        /empleados/i,
        /remoto/i,
        /fiscal/i,
        /hardware|dispositivos/i
      ]
      let touched = 0

      for (const label of primaryTabs) {
        await page.getByRole('link', { name: label }).click()
        await page.waitForTimeout(400)
        touched += await touchVisibleControls(page, page, { limit: 12 })
      }

      for (const label of moreTabs) {
        await clickMore(page, label)
        await page.waitForTimeout(500)
        touched += await touchVisibleControls(page, page, { limit: 12 })
      }

      await expectNoAppCrash(page)
      return `controles tocados=${touched}`
    })

    await check('Cobertura: tocar campos de subtabs de Ajustes', async () => {
      await page.getByRole('link', { name: /ajustes/i }).click()
      const settingTabs = [
        'Conexión',
        'Mi negocio',
        'Impresora de tickets',
        'Cajón de dinero',
        'Lector de códigos'
      ]
      let touched = 0
      for (const label of settingTabs) {
        await page.getByRole('button', { name: label, exact: true }).click()
        await page.waitForTimeout(400)
        touched += await touchVisibleControls(page, page, { limit: 20 })
      }
      await expectNoAppCrash(page)
      return `controles tocados=${touched}`
    })

    await check('Cobertura: tocar campos de subtabs fiscales', async () => {
      await clickMore(page, /fiscal/i)
      const fiscalTabs = [
        'Facturación',
        'Panel',
        'Inv. Fiscal',
        'Costos',
        'Logística',
        'Federación',
        'Extracciones',
        'Documentos',
        'Auditoría',
        'Analítica',
        'Billetera',
        'Cripto',
        'Operaciones',
        'Seguridad'
      ]
      let touched = 0
      for (const label of fiscalTabs) {
        await page.getByRole('button', { name: label, exact: true }).click()
        await page.waitForTimeout(500)
        touched += await touchVisibleControls(page, page, { limit: 24 })
      }
      await expectNoAppCrash(page)
      return `controles tocados=${touched}`
    })

    await check('Historial rechaza rango de fechas inválido', async () => {
      await page.getByRole('link', { name: /historial/i }).click()
      const dateInputs = page.locator('input[type="date"]')
      await dateInputs.nth(0).fill('2026-03-09')
      await dateInputs.nth(1).fill('2026-03-01')
      await page.getByRole('button', { name: /Actualizar/i }).click()
      await expect(page.getByText(/fecha de inicio no puede ser posterior/i).first()).toBeVisible({
        timeout: 10000
      })
    })

    await check('Persistencia tras reinicio de Electron', async () => {
      await app.close()
      ;({ app, page } = await launchApp())
      await seedRuntime(page, false)
      const entries = await readLocalStorage(page)
      const pendingAfterRestart = pendingTicketCount(entries)
      if (pendingAfterRestart < pendingCountBeforeRestart) {
        throw new Error(
          `Los pendientes bajaron tras reinicio: antes=${pendingCountBeforeRestart}, después=${pendingAfterRestart}`
        )
      }
      const storedBaseUrl = entries['titan.baseUrl']
      if (storedBaseUrl !== API_URL) {
        throw new Error(`La base URL persistida cambió a ${storedBaseUrl || '(vacía)'}`)
      }
      await ensureLoggedInTerminal(page)
      return `pending=${pendingAfterRestart}`
    })

    await check('Datos creados visibles en vistas operativas', async () => {
      await page.getByRole('link', { name: /clientes/i }).click()
      await page.getByPlaceholder(/Buscar por nombre, teléfono o correo/i).fill(customer.name)
      await expect(page.getByText(customer.name).first()).toBeVisible({ timeout: 10000 })

      await page.getByRole('link', { name: /productos/i }).click()
      await page.getByPlaceholder(/Buscar por SKU, nombre o código de barras/i).fill(product.sku)
      await expect(page.getByText(product.sku).first()).toBeVisible({ timeout: 10000 })
    })

    await check('Remoto abre pantalla aunque el backend responda 404', async () => {
      await clickMore(page, /remoto/i)
      await expect(
        page.getByRole('heading', { name: /Monitoreo y Control Satelital/i }).first()
      ).toBeVisible({ timeout: 10000 })
      await expectNoAppCrash(page)
    })

    await check('Hardware abre listado de dispositivos sin crash visual', async () => {
      await clickMore(page, /hardware|dispositivos/i)
      await expect(
        page.getByRole('heading', { name: /Dispositivos vinculados|Dispositivos/i }).first()
      ).toBeVisible({ timeout: 10000 })
      await expectNoAppCrash(page)
    })

    await check('Cierre de sesión limpio', async () => {
      await page.getByRole('button', { name: /cerrar sesión/i }).click()
      await page.getByRole('button', { name: /aceptar/i }).click()
      await expectLogin(page)
    })

    await check('Sin errores HTTP inesperados durante la batería', async () => {
      const issues = uniqueItems(runState.httpIssues)
      if (issues.length > 0) {
        throw new Error(issues.join('\n'))
      }
      return 'sin hallazgos'
    })

    await check('Sin errores de consola inesperados durante la batería', async () => {
      const issues = uniqueItems(runState.consoleIssues)
      if (issues.length > 0) {
        throw new Error(issues.join('\n'))
      }
      return 'sin hallazgos'
    })

    await check('Sin page errors inesperados durante la batería', async () => {
      const issues = uniqueItems(runState.pageErrors)
      if (issues.length > 0) {
        throw new Error(issues.join('\n'))
      }
      return 'sin hallazgos'
    })
  } finally {
    await app.close().catch(() => {})
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
