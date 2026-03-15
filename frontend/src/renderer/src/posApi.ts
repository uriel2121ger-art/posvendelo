import {
  POS_API_URL,
  POS_BROWSER_PORT,
  POS_DISCOVER_HOSTS,
  POS_DISCOVER_PORTS
} from './runtimeEnv'

export type RuntimeConfig = {
  baseUrl: string
  token: string
  terminalId: number
}

export type SaleSearchFilters = {
  folio?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
}

/** Safe localStorage.setItem — silently swallows QuotaExceededError */
function safeSetItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // QuotaExceededError or SecurityError — degrade gracefully
    console.warn(`[POSVENDELO] localStorage.setItem("${key}") failed — storage may be full`)
  }
}

/** Simple semaphore to limit concurrent API requests and prevent TCP starvation */
const MAX_CONCURRENT_REQUESTS = 20
let _activeRequests = 0
const _requestQueue: Array<() => void> = []

function acquireSlot(): Promise<void> {
  if (_activeRequests < MAX_CONCURRENT_REQUESTS) {
    _activeRequests++
    return Promise.resolve()
  }
  return new Promise<void>((resolve) => {
    _requestQueue.push(() => {
      _activeRequests++
      resolve()
    })
  })
}

function releaseSlot(): void {
  const next = _requestQueue.shift()
  if (next) {
    next() // callback increments _activeRequests — counter stays the same
  } else {
    _activeRequests--
  }
}

const FALLBACKS: Record<string, string> = {
  products: '/api/v1/products/',
  customers: '/api/v1/customers/',
  inventory: '/api/v1/inventory/'
}

function getDiscoverPorts(): number[] {
  try {
    const custom = localStorage.getItem('pos.discoverPorts')
    if (custom) {
      const parsed = JSON.parse(custom) as number[]
      if (
        Array.isArray(parsed) &&
        parsed.every((p) => typeof p === 'number' && p > 0 && p < 65536)
      ) {
        return parsed
      }
    }
  } catch {
    /* use defaults */
  }
  return POS_DISCOVER_PORTS
}

export async function autoDiscoverBackend(): Promise<string | null> {
  const saved = localStorage.getItem('pos.baseUrl')
  if (saved && _isValidBaseUrl(saved)) {
    try {
      const r = await fetch(`${saved}/api/v1/auth/verify`, { signal: AbortSignal.timeout(1500) })
      if (r.status === 401 || r.ok) return saved
    } catch {
      /* saved URL unreachable, try discovery */
    }
  }
  for (const port of getDiscoverPorts()) {
    for (const host of POS_DISCOVER_HOSTS) {
      const url = `http://${host}:${port}`
      try {
        const r = await fetch(`${url}/api/v1/auth/verify`, { signal: AbortSignal.timeout(1200) })
        if (r.status === 401 || r.ok) {
          safeSetItem('pos.baseUrl', url)
          return url
        }
      } catch {
        /* host:port not responding */
      }
    }
  }
  return null
}

function _isValidBaseUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

function _isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false // Not a JWT — skip expiry check
    // Normalize base64url → base64 standard (JWTs use - and _ instead of + and /)
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/').padEnd(
      Math.ceil(parts[1].length / 4) * 4, '='
    )
    const payload = JSON.parse(atob(b64)) as Record<string, unknown>
    if (!payload.exp) return false
    return (payload.exp as number) * 1000 < Date.now()
  } catch {
    // Malformed base64 or invalid JSON — treat as expired for safety
    return true
  }
}

/** Migrate localStorage keys from legacy titan.* prefix to pos.* (runs once) */
let _storageMigrated = false
function migrateStorageKeys(): void {
  if (_storageMigrated) return
  _storageMigrated = true
  try {
    const fixed = ['token', 'baseUrl', 'user', 'role', 'terminalId', 'hwConfig',
      'currentShift', 'shiftHistory', 'pendingTickets', 'activeTickets',
      'productsCache', 'configProfiles', 'remoteActionQueue', 'discoverPorts']
    for (const key of fixed) {
      if (!localStorage.getItem(`pos.${key}`)) {
        const old = localStorage.getItem(`titan.${key}`)
        if (old) { localStorage.setItem(`pos.${key}`, old); localStorage.removeItem(`titan.${key}`) }
      }
    }
    // Migrate dynamic keys (per-terminal shifts, per-user tickets)
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i)
      if (k?.startsWith('titan.') && !localStorage.getItem(k.replace('titan.', 'pos.'))) {
        localStorage.setItem(k.replace('titan.', 'pos.'), localStorage.getItem(k)!)
        localStorage.removeItem(k)
      }
    }
  } catch { /* storage inaccessible */ }
}

const DEFAULT_BASE_URL = POS_API_URL

/** En modo navegador puro (Vite dev puerto 5173, NO Electron) usar '' para que las peticiones pasen por el proxy a 8000. */
function getEffectiveBaseUrl(saved: string): string {
  if (typeof window === 'undefined') return _isValidBaseUrl(saved) ? saved : DEFAULT_BASE_URL
  // Electron dev carga desde Vite HMR pero NO tiene proxy — siempre usar URL completa
  if (isElectron()) return _isValidBaseUrl(saved) ? saved : DEFAULT_BASE_URL
  const origin = window.location.origin
  const isViteDev =
    window.location.port === POS_BROWSER_PORT &&
    POS_DISCOVER_HOSTS.some((host) => origin.startsWith(`http://${host}:`))
  const pointsToLocal8000 = saved === DEFAULT_BASE_URL || saved === ''
  if (isViteDev && pointsToLocal8000) return ''
  return _isValidBaseUrl(saved) ? saved : DEFAULT_BASE_URL
}

export function loadRuntimeConfig(): RuntimeConfig {
  migrateStorageKeys()
  try {
    const baseUrl = localStorage.getItem('pos.baseUrl') ?? DEFAULT_BASE_URL
    let token = localStorage.getItem('pos.token') ?? ''
    // Auto-clear expired tokens to force re-login
    if (token && _isTokenExpired(token)) {
      localStorage.removeItem('pos.token')
      token = ''
    }
    return {
      baseUrl: getEffectiveBaseUrl(baseUrl),
      token,
      terminalId: Math.max(1, parseInt(localStorage.getItem('pos.terminalId') ?? '1', 10) || 1)
    }
  } catch {
    return { baseUrl: DEFAULT_BASE_URL, token: '', terminalId: 1 }
  }
}

export function saveRuntimeConfig(cfg: RuntimeConfig): void {
  safeSetItem('pos.baseUrl', cfg.baseUrl)
  safeSetItem('pos.token', cfg.token)
  safeSetItem('pos.terminalId', String(cfg.terminalId))
  // A new token means the session is valid again — clear the expired flag
  // so API calls work without requiring a full page reload.
  if (cfg.token) _sessionExpired = false
}

function headers(cfg: RuntimeConfig): HeadersInit {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${cfg.token}`,
    'X-Terminal-Id': String(cfg.terminalId)
  }
}

function toTimestampMs(raw: unknown): number | null {
  if (typeof raw !== 'string') return null
  const ms = new Date(raw).getTime()
  return Number.isFinite(ms) ? ms : null
}

function inDateRange(row: Record<string, unknown>, dateFrom?: string, dateTo?: string): boolean {
  if (!dateFrom && !dateTo) return true

  const tsRaw = row.timestamp ?? row.created_at ?? row._received_at
  const tsMs = toTimestampMs(tsRaw)
  if (tsMs === null) return false

  const fromMs = dateFrom ? toTimestampMs(`${dateFrom}T00:00:00`) : null
  const toMs = dateTo ? toTimestampMs(`${dateTo}T23:59:59`) : null

  if (fromMs !== null && tsMs < fromMs) return false
  if (toMs !== null && tsMs > toMs) return false
  return true
}

let _sessionExpired = false

/** Reset the expired flag so API calls work again after re-login. */
export function resetSessionExpired(): void {
  _sessionExpired = false
}

function handleExpiredSession(): never {
  _sessionExpired = true
  try {
    localStorage.removeItem('pos.token')
    localStorage.removeItem('pos.user')
    localStorage.removeItem('pos.currentShift')
  } catch {
    /* storage inaccessible — proceed with redirect */
  }
  window.location.hash = '#/login'
  throw new Error('Sesión expirada. Inicia sesión de nuevo.')
}

/**
 * Fire-and-forget server-side logout to revoke the JWT's JTI.
 * Does NOT throw — safe to call before clearing localStorage.
 */
export async function serverLogout(): Promise<void> {
  try {
    const cfg = loadRuntimeConfig()
    if (!cfg.token) return
    const url = `${cfg.baseUrl}/api/v1/auth/logout`
    await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${cfg.token}` },
      signal: AbortSignal.timeout(3000)
    })
  } catch {
    /* best-effort — token will expire naturally via TTL */
  }
}

function parseErrorDetail(text: string, fallback: string): string {
  try {
    const body = JSON.parse(text) as Record<string, unknown>
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      const msgs = body.detail
        .map((e: Record<string, unknown>) => {
          const msg =
            typeof e.msg === 'string' ? e.msg : typeof e.message === 'string' ? e.message : ''
          const loc = Array.isArray(e.loc) ? String(e.loc[e.loc.length - 1]) : ''
          return loc && msg ? `${loc}: ${msg}` : msg
        })
        .filter(Boolean)
      return msgs.join('; ') || fallback
    }
    if (typeof body.error === 'string') return body.error
    if (typeof body.message === 'string') return body.message
  } catch {
    /* not JSON — use raw text */
  }
  return text || fallback
}

/** Lanza si el cuerpo tiene success: false (respuesta 200 con error en body). */
function assertSuccess(body: Record<string, unknown>, fallbackMessage: string): void {
  if (body.success === false) {
    const msg =
      typeof body.error === 'string'
        ? body.error
        : typeof body.detail === 'string'
          ? body.detail
          : typeof body.message === 'string'
            ? body.message
            : fallbackMessage
    throw new Error(msg)
  }
}

async function apiFetchOnce(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  if (_sessionExpired) throw new Error('Sesión expirada. Inicia sesión de nuevo.')
  await acquireSlot()
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...init, signal: controller.signal })
    if (_sessionExpired) throw new Error('Sesión expirada. Inicia sesión de nuevo.')
    if (res.status === 401) handleExpiredSession()
    return res
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Tiempo de espera agotado. Verifica la conexión al servidor.')
    }
    const msg = err instanceof Error ? err.message : String(err)
    if (
      /failed to fetch|network error|load failed|err_cert|ssl|tls|certificate/i.test(msg) ||
      err instanceof TypeError
    ) {
      throw new Error(
        `No se pudo conectar al servidor. Comprueba que el servidor esté en marcha. Si ya está disponible, actualiza la URL del API en Configuración. URL esperada por defecto: ${DEFAULT_BASE_URL}.`
      )
    }
    throw err
  } finally {
    clearTimeout(timeout)
    releaseSlot()
  }
}

async function apiFetch(url: string, init: RequestInit): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase()
  const isIdempotent = method === 'GET' || method === 'HEAD' || method === 'OPTIONS'
  const maxRetries = isIdempotent ? 2 : 0
  let lastError: unknown
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await apiFetchOnce(url, init, 3_000)
    } catch (err) {
      lastError = err
      if (attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, 200 * Math.pow(2, attempt)))
      }
    }
  }
  throw lastError
}

async function apiFetchLong(url: string, init: RequestInit): Promise<Response> {
  return apiFetchOnce(url, init, 15_000)
}

export function getUserRole(): string {
  try {
    return localStorage.getItem('pos.role') ?? 'cashier'
  } catch {
    return 'cashier'
  }
}

async function getWithFallback(cfg: RuntimeConfig, paths: string[]): Promise<Response> {
  for (const path of paths) {
    try {
      const res = await apiFetch(`${cfg.baseUrl}${path}`, { headers: headers(cfg) })
      if (res.status === 404 || res.status === 405) {
        void res.body?.cancel().catch(() => {})
        continue
      }
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(parseErrorDetail(detail, 'Error del servidor'))
      }
      return res
    } catch (err) {
      // Timeout on this path — try next fallback endpoint
      if (err instanceof Error && err.message.includes('Tiempo de espera')) {
        continue
      }
      throw err
    }
  }

  throw new Error('Sin endpoint compatible disponible')
}

export async function pullTable(
  table: 'products' | 'customers' | 'inventory' | 'shifts',
  cfg: RuntimeConfig
): Promise<Record<string, unknown>[]> {
  const primaryUrl = `${cfg.baseUrl}/api/v1/sync/${table}`
  const primary = await apiFetch(primaryUrl, { headers: headers(cfg) })

  if (primary.ok) {
    const body = (await primary.json()) as Record<string, unknown> | null
    if (!body || typeof body !== 'object') {
      console.warn(`pullTable(${table}): respuesta malformada del servidor`, body)
      return []
    }
    const candidate = body.data ?? body[table] ?? []
    return Array.isArray(candidate) ? (candidate as Record<string, unknown>[]) : []
  }

  if (primary.status === 404 || primary.status === 405) {
    const fallbackPath = FALLBACKS[table]
    if (fallbackPath) {
      const fallback = await apiFetch(`${cfg.baseUrl}${fallbackPath}`, { headers: headers(cfg) })
      if (fallback.ok) {
        const body = (await fallback.json()) as Record<string, unknown> | null
        if (!body || typeof body !== 'object') {
          console.warn(`pullTable(${table}) fallback: respuesta malformada del servidor`, body)
          return []
        }
        const fallbackCandidate = body[table] ?? body.data ?? body.products ?? body.customers ?? []
        return Array.isArray(fallbackCandidate)
          ? (fallbackCandidate as Record<string, unknown>[])
          : []
      }
      const detail = await fallback.text()
      throw new Error(parseErrorDetail(detail, 'Fallo cargando datos'))
    }
  }

  const detail = await primary.text()
  throw new Error(parseErrorDetail(detail, 'Fallo cargando datos'))
}

export async function syncTable(
  table: 'products' | 'customers' | 'inventory' | 'shifts' | 'sales',
  rows: Record<string, unknown>[],
  cfg: RuntimeConfig
): Promise<void> {
  const now = new Date().toISOString()
  const payload = {
    data: rows,
    timestamp: now,
    terminal_id: cfg.terminalId,
    request_id: `sync_${table}_${Date.now()}`
  }
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/sync/${table}`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(parseErrorDetail(detail, 'Fallo sincronizando datos'))
  }
}

export async function searchSales(
  cfg: RuntimeConfig,
  filters: SaleSearchFilters
): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams()
  if (filters.folio?.trim()) params.set('folio', filters.folio.trim())
  if (filters.dateFrom?.trim()) params.set('date_from', filters.dateFrom.trim())
  if (filters.dateTo?.trim()) params.set('date_to', filters.dateTo.trim())
  params.set('limit', String(filters.limit ?? 100))

  const query = params.toString()
  const suffix = query ? `?${query}` : ''
  const syncParams = new URLSearchParams()
  syncParams.set('limit', String(Math.max(filters.limit ?? 100, 500)))
  if (filters.dateFrom?.trim()) syncParams.set('since', `${filters.dateFrom.trim()}T00:00:00`)
  const syncSuffix = `?${syncParams.toString()}`

  const res = await getWithFallback(cfg, [
    `/api/v1/sales/search${suffix}`,
    `/api/v1/sales/${suffix}`,
    `/api/v1/sync/sales${syncSuffix}`
  ])
  const body = (await res.json()) as Record<string, unknown>
  const raw = (body.sales ?? body.data ?? []) as Record<string, unknown>[]

  const folio = filters.folio?.trim().toLowerCase() ?? ''
  const filtered = raw.filter((row) => {
    if (folio) {
      const rowFolio = String(row.folio ?? row.id ?? '').toLowerCase()
      if (!rowFolio.includes(folio)) return false
    }
    return inDateRange(row, filters.dateFrom, filters.dateTo)
  })

  filtered.sort((a, b) => {
    const aMs = toTimestampMs(a.timestamp ?? a.created_at ?? a._received_at) ?? 0
    const bMs = toTimestampMs(b.timestamp ?? b.created_at ?? b._received_at) ?? 0
    return bMs - aMs
  })

  return filtered.slice(0, filters.limit ?? 100)
}

export async function getSaleDetail(
  cfg: RuntimeConfig,
  saleId: string
): Promise<Record<string, unknown>> {
  const safeSaleId = encodeURIComponent(saleId)
  const res = await getWithFallback(cfg, [
    `/api/v1/sales/${safeSaleId}`,
    '/api/v1/sync/sales?limit=2000'
  ])
  const body = (await res.json()) as Record<string, unknown>
  const data = body.data
  if (Array.isArray(data)) {
    const found =
      data.find((row) => String((row as Record<string, unknown>).id ?? '') === saleId) ??
      data.find((row) => String((row as Record<string, unknown>).folio ?? '') === saleId)
    if (!found) {
      throw new Error(`Venta no encontrada: ${saleId}`)
    }
    return found as Record<string, unknown>
  }
  // Primary path: data is the single sale object (unwrap from {success, data} envelope)
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    return data as Record<string, unknown>
  }
  throw new Error(`Respuesta inesperada al obtener venta ${saleId}`)
}

export async function getSyncStatus(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await getWithFallback(cfg, ['/api/v1/sync/status', '/api/v1/auth/verify'])
  const body = (await res.json()) as Record<string, unknown>
  if (typeof body.status === 'string') return body
  return {
    status: body.ok ? 'ok' : 'unknown',
    details: body,
    timestamp: new Date().toISOString()
  }
}

export async function getSystemInfo(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await getWithFallback(cfg, ['/api/v1/remote/system-status', '/api/info'])
  return (await res.json()) as Record<string, unknown>
}

export async function getBackupStatus(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/system/status`, { headers: headers(cfg) })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(parseErrorDetail(detail, 'No se pudo obtener el estado de respaldos'))
  }
  return (await res.json()) as Record<string, unknown>
}

export async function listBackups(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/system/backups`, { headers: headers(cfg) })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(parseErrorDetail(detail, 'No se pudo listar los respaldos'))
  }
  return (await res.json()) as Record<string, unknown>
}

export async function buildRestorePlan(
  cfg: RuntimeConfig,
  backupFile: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/system/restore-plan`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({ backup_file: backupFile })
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(parseErrorDetail(detail, 'No se pudo preparar el plan de recuperación'))
  }
  return (await res.json()) as Record<string, unknown>
}

export async function getLicenseStatus(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/license/status`, { headers: headers(cfg) })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(parseErrorDetail(detail, 'No se pudo obtener el estado de licencia'))
  }
  const body = (await res.json()) as Record<string, unknown>
  assertSuccess(body, 'No se pudo obtener el estado de licencia')
  return body
}

// ── Turnos ────────────────────────────────────────

export async function openTurn(
  cfg: RuntimeConfig,
  body: { initial_cash: number; branch_id?: number; notes?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/turns/open`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({
      initial_cash: body.initial_cash,
      branch_id: body.branch_id ?? 1,
      terminal_id: cfg.terminalId,
      notes: body.notes || undefined
    })
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

export async function closeTurn(
  cfg: RuntimeConfig,
  turnId: number,
  body: { final_cash: number; notes?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/turns/${turnId}/close`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({
      final_cash: body.final_cash,
      notes: body.notes || undefined
    })
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCurrentTurn(cfg: RuntimeConfig): Promise<Record<string, unknown> | null> {
  const params = new URLSearchParams({ terminal_id: String(cfg.terminalId) })
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/turns/current?${params.toString()}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  const body = (await res.json()) as Record<string, unknown> | null
  if (!body || typeof body !== 'object') return null
  const data = body.data as Record<string, unknown> | null
  return data
}

// ── Inventario ────────────────────────────────────

export async function adjustStock(
  cfg: RuntimeConfig,
  body: { product_id: number; quantity: number; reason: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/inventory/adjust`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

// ── Ventas ────────────────────────────────────────

export type SaleItemPayload = {
  product_id: number | null
  name?: string
  qty: number
  price: number
  price_wholesale?: number
  discount: number
  is_wholesale: boolean
  price_includes_tax: boolean
  sat_clave_prod_serv?: string
  sat_clave_unidad?: string
}

export type CreateSalePayload = {
  items: SaleItemPayload[]
  payment_method: string
  customer_id?: number | null
  turn_id?: number | null
  branch_id?: number
  serie?: string
  cash_received?: number
  notes?: string
  requiere_factura?: boolean
  card_reference?: string | null
  transfer_reference?: string | null
  mixed_cash?: number
  mixed_card?: number
  mixed_transfer?: number
  mixed_wallet?: number
  mixed_gift_card?: number
}

export async function createSale(
  cfg: RuntimeConfig,
  sale: CreateSalePayload
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/sales/`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(sale)
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(parseErrorDetail(detail, 'Error creando venta'))
  }
  const body = (await res.json()) as Record<string, unknown>
  assertSuccess(body, 'Error creando venta')
  return body
}

// ── Dashboard ──────────────────────────────────────

export async function getDashboardQuick(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/dashboard/quick`, { headers: headers(cfg) })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

// ── Mermas ─────────────────────────────────────────

export async function getMermasPending(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/mermas/pending`, { headers: headers(cfg) })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

export async function approveMerma(
  cfg: RuntimeConfig,
  id: number,
  approved: boolean,
  notes?: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/mermas/approve`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({ merma_id: id, approved, notes: notes || undefined })
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

// ── Gastos ─────────────────────────────────────────

export async function getExpensesSummary(
  cfg: RuntimeConfig,
  month?: number,
  year?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (month) params.set('month', String(month))
  if (year) params.set('year', String(year))
  const qs = params.toString()
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/expenses/summary${qs ? `?${qs}` : ''}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

export async function registerExpense(
  cfg: RuntimeConfig,
  expense: { amount: number; description: string; reason?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/expenses/`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(expense)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error del servidor'))
  return (await res.json()) as Record<string, unknown>
}

// ── Empleados ─────────────────────────────────────

export async function listEmployees(
  cfg: RuntimeConfig,
  search?: string,
  limit?: number,
  offset?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (search?.trim()) params.set('search', search.trim())
  if (limit) params.set('limit', String(limit))
  if (offset) params.set('offset', String(offset))
  const qs = params.toString()
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/employees/${qs ? `?${qs}` : ''}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando empleados'))
  return (await res.json()) as Record<string, unknown>
}

export async function createEmployee(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/employees/`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando empleado'))
  return (await res.json()) as Record<string, unknown>
}

export async function updateEmployee(
  cfg: RuntimeConfig,
  id: number,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/employees/${id}`, {
    method: 'PUT',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error actualizando empleado'))
  return (await res.json()) as Record<string, unknown>
}

export async function deleteEmployee(
  cfg: RuntimeConfig,
  id: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/employees/${id}`, {
    method: 'DELETE',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error eliminando empleado'))
  return (await res.json()) as Record<string, unknown>
}

// ── Remote ────────────────────────────────────────

export async function getLiveSales(
  cfg: RuntimeConfig,
  limit?: number
): Promise<Record<string, unknown>> {
  const qs = limit ? `?limit=${limit}` : ''
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/live-sales${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando ventas en vivo'))
  return (await res.json()) as Record<string, unknown>
}

export async function getTurnStatusRemote(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/turn-status`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error obteniendo estado turno'))
  return (await res.json()) as Record<string, unknown>
}

export async function remoteOpenDrawer(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/remote/open-drawer`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error abriendo cajón'))
  return (await res.json()) as Record<string, unknown>
}

export async function remoteChangePrice(
  cfg: RuntimeConfig,
  body: { sku: string; new_price: number; reason: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/remote/change-price`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cambiando precio'))
  return (await res.json()) as Record<string, unknown>
}

export async function sendNotification(
  cfg: RuntimeConfig,
  body: { title: string; body: string; notification_type: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/remote/notification`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error enviando notificación'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPendingNotifications(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/notifications/pending`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando notificaciones'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPendingRemoteRequests(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/requests/pending`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando solicitudes remotas'))
  return (await res.json()) as Record<string, unknown>
}

export async function resolvePendingRemoteRequest(
  cfg: RuntimeConfig,
  requestId: number,
  approved: boolean,
  notes?: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/remote/requests/${requestId}/resolve`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({ approved, notes: notes || undefined })
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error resolviendo solicitud remota'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPairQrPayload(
  cfg: RuntimeConfig,
  branchId: number,
  terminalId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetch(
    `${cfg.baseUrl}/api/v1/auth/pair-qr?branch_id=${branchId}&terminal_id=${terminalId}`,
    { headers: headers(cfg) }
  )
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error generando payload de vinculación'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPairedDevices(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/auth/devices`, { headers: headers(cfg) })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando dispositivos vinculados'))
  return (await res.json()) as Record<string, unknown>
}

export async function revokePairedDevice(
  cfg: RuntimeConfig,
  pairingId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/auth/devices/${pairingId}`, {
    method: 'DELETE',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error revocando dispositivo'))
  return (await res.json()) as Record<string, unknown>
}

// ── Dashboard Extendido ───────────────────────────

export async function getDashboardResico(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/dashboard/resico`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando RESICO'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDashboardWealth(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/dashboard/wealth`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando patrimonio'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDashboardAI(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/dashboard/ai`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando IA'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDashboardExecutive(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/dashboard/executive`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando vista ejecutiva'))
  return (await res.json()) as Record<string, unknown>
}

// ── Sales Extendido ───────────────────────────────

export async function cancelSale(
  cfg: RuntimeConfig,
  saleId: string,
  body: { manager_pin: string; reason?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/sales/${encodeURIComponent(saleId)}/cancel`,
    {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify(body)
    }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cancelando venta'))
  return (await res.json()) as Record<string, unknown>
}

export async function remoteCancelSale(
  cfg: RuntimeConfig,
  body: { sale_id: number; manager_pin: string; reason?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/remote/cancel-sale`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cancelando venta remotamente'))
  return (await res.json()) as Record<string, unknown>
}

export async function getSaleEvents(
  cfg: RuntimeConfig,
  saleId: string
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sales/${encodeURIComponent(saleId)}/events`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando eventos'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDailySummaryReport(
  cfg: RuntimeConfig,
  branchId?: number,
  limit?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (branchId) params.set('branch_id', String(branchId))
  if (limit) params.set('limit', String(limit))
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/sales/reports/daily-summary${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando reporte diario'))
  return (await res.json()) as Record<string, unknown>
}

export async function getProductRanking(
  cfg: RuntimeConfig,
  limit?: number
): Promise<Record<string, unknown>> {
  const qs = limit ? `?limit=${limit}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/sales/reports/product-ranking${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando ranking'))
  return (await res.json()) as Record<string, unknown>
}

export async function getHourlyHeatmap(
  cfg: RuntimeConfig,
  branchId?: number
): Promise<Record<string, unknown>> {
  const qs = branchId ? `?branch_id=${branchId}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/sales/reports/hourly-heatmap${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando heatmap'))
  return (await res.json()) as Record<string, unknown>
}

// ── Inventario Extendido ──────────────────────────

export async function getInventoryMovements(
  cfg: RuntimeConfig,
  productId?: number,
  type?: string,
  limit?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (productId) params.set('product_id', String(productId))
  if (type) params.set('movement_type', type)
  if (limit) params.set('limit', String(limit))
  const qs = params.toString()
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/inventory/movements${qs ? `?${qs}` : ''}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando movimientos'))
  return (await res.json()) as Record<string, unknown>
}

export async function getStockAlerts(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const url = `${cfg.baseUrl}/api/v1/inventory/alerts?_=${Date.now()}`
  const res = await apiFetch(url, {
    headers: headers(cfg),
    cache: 'no-store'
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando alertas'))
  return (await res.json()) as Record<string, unknown>
}

// ── Turnos Extendido ──────────────────────────────

export async function getTurnSummary(
  cfg: RuntimeConfig,
  turnId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/turns/${turnId}/summary`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando resumen turno'))
  return (await res.json()) as Record<string, unknown>
}

export async function createCashMovement(
  cfg: RuntimeConfig,
  turnId: number,
  body: { movement_type: string; amount: number; reason: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/turns/${turnId}/movements`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error registrando movimiento caja'))
  return (await res.json()) as Record<string, unknown>
}

// ── Clientes CRUD ─────────────────────────────────

export type CreateCustomerBody = {
  name: string
  phone?: string
  email?: string
  rfc?: string
  codigo_postal?: string
  razon_social?: string
  regimen_fiscal?: string
}

export async function createCustomer(
  cfg: RuntimeConfig,
  body: CreateCustomerBody
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/customers/`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando cliente'))
  return (await res.json()) as Record<string, unknown>
}

// ── Clientes Extendido ────────────────────────────

export async function getCustomerCredit(
  cfg: RuntimeConfig,
  customerId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/customers/${customerId}/credit`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando crédito'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCustomerSales(
  cfg: RuntimeConfig,
  customerId: number,
  limit?: number
): Promise<Record<string, unknown>> {
  const qs = limit ? `?limit=${limit}` : ''
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/customers/${customerId}/sales${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando ventas del cliente'))
  return (await res.json()) as Record<string, unknown>
}

// ── Productos Extendido ───────────────────────────

export async function getProductCategories(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/products/categories/list`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando categorías'))
  return (await res.json()) as Record<string, unknown>
}

// ── SAT ────────────────────────────────────────

export async function searchSatCodes(
  cfg: RuntimeConfig,
  query: string,
  limit = 20
): Promise<{ code: string; description: string }[]> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/sat/search?q=${encodeURIComponent(query)}&limit=${limit}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) return []
  const body = (await res.json()) as Record<string, unknown>
  const data = body.data as Record<string, unknown> | undefined
  return (data?.results ?? []) as { code: string; description: string }[]
}

export async function getSatUnits(cfg: RuntimeConfig): Promise<{ code: string; name: string }[]> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/sat/units`, {
    headers: headers(cfg)
  })
  if (!res.ok) return []
  const body = (await res.json()) as Record<string, unknown>
  return (body.data ?? []) as { code: string; name: string }[]
}

// ── Productos CRUD ────────────────────────────

export async function createProduct(
  cfg: RuntimeConfig,
  data: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/products/`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando producto'))
  return (await res.json()) as Record<string, unknown>
}

export async function updateProduct(
  cfg: RuntimeConfig,
  id: number | string,
  data: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/products/${id}`, {
    method: 'PUT',
    headers: headers(cfg),
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error actualizando producto'))
  return (await res.json()) as Record<string, unknown>
}

export async function scanProduct(
  cfg: RuntimeConfig,
  sku: string
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/products/scan/${encodeURIComponent(sku)}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Producto no encontrado'))
  return (await res.json()) as Record<string, unknown>
}

export async function getLowStockProducts(
  cfg: RuntimeConfig,
  limit?: number
): Promise<Record<string, unknown>> {
  const qs = limit ? `?limit=${limit}` : ''
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/products/low-stock${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando stock bajo'))
  return (await res.json()) as Record<string, unknown>
}

export async function remoteStockUpdate(
  cfg: RuntimeConfig,
  body: { sku: string; quantity: number; operation: string; reason: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/products/stock`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error actualizando stock'))
  return (await res.json()) as Record<string, unknown>
}

// ── Fiscal ────────────────────────────────────────

export async function generateCFDI(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/generate`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error generando CFDI'))
  return (await res.json()) as Record<string, unknown>
}

export async function getSalesPendingInvoice(
  cfg: RuntimeConfig,
  branchId: number = 1,
  limit: number = 100
): Promise<Record<string, unknown>> {
  const res = await apiFetch(
    `${cfg.baseUrl}/api/v1/fiscal/sales-pending-invoice?branch_id=${branchId}&limit=${limit}`,
    { headers: headers(cfg) }
  )
  if (!res.ok)
    throw new Error(
      parseErrorDetail(await res.text(), 'Error listando ventas pendientes de factura')
    )
  return (await res.json()) as Record<string, unknown>
}

export async function generateGlobalCFDI(
  cfg: RuntimeConfig,
  body: { period_type: string; date: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/global/generate`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error generando CFDI global'))
  return (await res.json()) as Record<string, unknown>
}

export async function processReturn(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/returns/process`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error procesando devolución'))
  return (await res.json()) as Record<string, unknown>
}

export async function getReturnsSummary(
  cfg: RuntimeConfig,
  startDate?: string,
  endDate?: string
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/returns/summary${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando resumen devoluciones'))
  return (await res.json()) as Record<string, unknown>
}

export async function parseXML(cfg: RuntimeConfig, file: File): Promise<Record<string, unknown>> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/xml/parse`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${cfg.token}`,
      'X-Terminal-Id': String(cfg.terminalId)
    },
    body: formData
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error al procesar XML'))
  return (await res.json()) as Record<string, unknown>
}

export async function runAudit(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/audit/run`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error ejecutando auditoría'))
  return (await res.json()) as Record<string, unknown>
}

export async function getShadowAuditView(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/audit-view`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando vista SAT'))
  return (await res.json()) as Record<string, unknown>
}

export async function getShadowRealView(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/real-view`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando vista real'))
  return (await res.json()) as Record<string, unknown>
}

export async function getShadowDiscrepancy(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/discrepancy`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando discrepancias'))
  return (await res.json()) as Record<string, unknown>
}

export async function reconcileShadow(
  cfg: RuntimeConfig,
  body: { product_id: number; fiscal_stock: number }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/reconcile`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error reconciliando'))
  return (await res.json()) as Record<string, unknown>
}

export async function createGhostTransfer(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/ghost/transfer/create`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando transferencia'))
  return (await res.json()) as Record<string, unknown>
}

export async function receiveGhostTransfer(
  cfg: RuntimeConfig,
  body: { transfer_code: string; user_id: number }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/ghost/transfer/receive`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error recibiendo transferencia'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPendingGhostTransfers(
  cfg: RuntimeConfig,
  branch?: string
): Promise<Record<string, unknown>> {
  const qs = branch ? `?branch=${encodeURIComponent(branch)}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/ghost/transfer/pending${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando transferencias'))
  return (await res.json()) as Record<string, unknown>
}

export async function getFederationOperational(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/federation/operational`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando federation'))
  return (await res.json()) as Record<string, unknown>
}

export async function getFederationFiscal(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/federation/fiscal`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando inteligencia fiscal'))
  return (await res.json()) as Record<string, unknown>
}

export async function createGhostWallet(
  cfg: RuntimeConfig,
  seed?: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/wallet/create`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(seed ? { seed } : {})
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando billetera'))
  return (await res.json()) as Record<string, unknown>
}

export async function addWalletPoints(
  cfg: RuntimeConfig,
  body: { hash_id: string; sale_amount: number; sale_id?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/wallet/add`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error agregando puntos'))
  return (await res.json()) as Record<string, unknown>
}

export async function redeemWalletPoints(
  cfg: RuntimeConfig,
  body: { hash_id: string; amount: number }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/wallet/redeem`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error redimiendo puntos'))
  return (await res.json()) as Record<string, unknown>
}

export async function getWalletStats(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/wallet/stats`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando estadísticas de billetera'))
  return (await res.json()) as Record<string, unknown>
}

export async function getExtractionAvailable(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/extraction/available`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando extracción disponible'))
  return (await res.json()) as Record<string, unknown>
}

export async function createExtractionPlan(
  cfg: RuntimeConfig,
  body: { target_amount: number }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/extraction/plan`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error creando plan de extracción'))
  return (await res.json()) as Record<string, unknown>
}

export async function getOptimalExtraction(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/extraction/optimal`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando extracción óptima'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCryptoAvailable(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/crypto/available`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando criptomoneda disponible'))
  return (await res.json()) as Record<string, unknown>
}

export async function convertCrypto(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/crypto/convert`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error convirtiendo criptomoneda'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCryptoWealth(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/crypto/wealth`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando patrimonio cripto'))
  return (await res.json()) as Record<string, unknown>
}

export async function supplierAnalyze(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/supplier/analyze`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error analizando proveedor'))
  return (await res.json()) as Record<string, unknown>
}

export async function verifyStealthPin(
  cfg: RuntimeConfig,
  body: { pin: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/stealth/verify-pin`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error verificando PIN'))
  return (await res.json()) as Record<string, unknown>
}

export async function configureStealthPins(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/stealth/configure-pins`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error configurando PINs'))
  return (await res.json()) as Record<string, unknown>
}

export async function surgicalDelete(
  cfg: RuntimeConfig,
  body: { sale_ids: number[]; confirm_phrase: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/stealth/surgical-delete`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error en eliminación'))
  return (await res.json()) as Record<string, unknown>
}

export async function triggerPanic(
  cfg: RuntimeConfig,
  body?: { immediate?: boolean }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/evasion/panic`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error en panic'))
  return (await res.json()) as Record<string, unknown>
}

export async function triggerFakeScreen(
  cfg: RuntimeConfig,
  body?: { screen_type?: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/evasion/fake-screen`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error en pantalla falsa'))
  return (await res.json()) as Record<string, unknown>
}

export async function runShaper(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shaper/run`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error ejecutando shaper'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: federation ---
export async function getFederationWealth(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/federation/wealth`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error al cargar panel de riqueza'))
  return (await res.json()) as Record<string, unknown>
}

export async function federationLockdown(
  cfg: RuntimeConfig,
  body: { branch_id: number }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/federation/lockdown`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error en bloqueo de sucursal'))
  return (await res.json()) as Record<string, unknown>
}

export async function federationRelease(
  cfg: RuntimeConfig,
  body: { branch_id: number; auth_code: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/federation/release`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error al liberar bloqueo'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: ghost transfer slip ---
export async function getGhostTransferSlip(
  cfg: RuntimeConfig,
  transferCode: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/ghost/transfer/slip/${encodeURIComponent(transferCode)}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error obteniendo remisión'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: shadow dual-stock, add, sell ---
export async function getShadowDualStock(
  cfg: RuntimeConfig,
  productId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/dual-stock/${productId}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error stock dual'))
  return (await res.json()) as Record<string, unknown>
}

export async function shadowAdd(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/add`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error agregando shadow'))
  return (await res.json()) as Record<string, unknown>
}

export async function shadowSell(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shadow/sell`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error venta shadow'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: evasion dead-drive ---
export async function triggerDeadDrive(
  cfg: RuntimeConfig,
  body: { device: string; confirm: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/evasion/dead-drive`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error dead-drive'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: cost reconciliation ---
export async function registerCostPurchase(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cost/purchase`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error registrando compra'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostDualView(
  cfg: RuntimeConfig,
  productId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cost/dual-view/${productId}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error vista dual costos'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostFiscal(
  cfg: RuntimeConfig,
  productId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cost/fiscal/${productId}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error costo fiscal'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostReal(
  cfg: RuntimeConfig,
  productId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cost/real/${productId}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error costo real'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostProfit(
  cfg: RuntimeConfig,
  saleId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cost/profit/${saleId}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error utilidad'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostGlobalReport(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cost/global-report`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error reporte global costos'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: dashboard ---
export async function getFiscalDashboardData(
  cfg: RuntimeConfig,
  year?: number
): Promise<Record<string, unknown>> {
  const qs = year != null ? `?year=${year}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/fiscal-dashboard/data${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error dashboard fiscal'))
  return (await res.json()) as Record<string, unknown>
}

export async function getFiscalDashboardSmartSelection(
  cfg: RuntimeConfig,
  maxAmount?: number
): Promise<Record<string, unknown>> {
  const qs = maxAmount != null ? `?max_amount=${maxAmount}` : ''
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/fiscal-dashboard/smart-selection${qs}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error selección inteligente'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: intercompany ---
export async function selectOptimalRfc(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/intercompany/select-rfc`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error RFC óptimo'))
  return (await res.json()) as Record<string, unknown>
}

export async function processCrossInvoice(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/intercompany/process-cross`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error factura cruzada'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: legal ---
export async function generateDestructionActa(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/legal/destruction-acta`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error acta destrucción'))
  return (await res.json()) as Record<string, unknown>
}

export async function generateReturnDocument(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/legal/return-document`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error documento devolución'))
  return (await res.json()) as Record<string, unknown>
}

export async function generateLegalSelfConsumptionVoucher(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/legal/selfconsumption-voucher`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error voucher autoconsumo'))
  return (await res.json()) as Record<string, unknown>
}

export async function getLegalMonthlySummary(
  cfg: RuntimeConfig,
  year?: number,
  month?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (year != null) params.set('year', String(year))
  if (month != null) params.set('month', String(month))
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/legal/monthly-summary${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error resumen legal'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: variance (price analytics) ---
export async function calculateSmartLoss(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/variance/smart-loss`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error pérdida inteligente'))
  return (await res.json()) as Record<string, unknown>
}

export async function suggestOptimalCast(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/variance/optimal-cast`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error CAST óptimo'))
  return (await res.json()) as Record<string, unknown>
}

export async function generateBatchVariance(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/variance/batch`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error varianza batch'))
  return (await res.json()) as Record<string, unknown>
}

export async function getSeasonalFactor(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/variance/seasonal-factor`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error factor estacional'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: discrepancy ---
export async function registerDiscrepancyExpense(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/discrepancy/expense`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error registrando gasto'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDiscrepancyAnalysis(
  cfg: RuntimeConfig,
  year?: number,
  month?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (year != null) params.set('year', String(year))
  if (month != null) params.set('month', String(month))
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/discrepancy/analysis${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error análisis discrepancias'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDiscrepancyTrend(
  cfg: RuntimeConfig,
  year?: number
): Promise<Record<string, unknown>> {
  const qs = year != null ? `?year=${year}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/discrepancy/trend${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error tendencia'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDiscrepancySuggestExtraction(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/discrepancy/suggest-extraction`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error sugerencia extracción'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDiscrepancyExpenses(
  cfg: RuntimeConfig,
  year?: number,
  month?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (year != null) params.set('year', String(year))
  if (month != null) params.set('month', String(month))
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/discrepancy/expenses${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error gastos'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: resico ---
export async function getResicoHealth(
  cfg: RuntimeConfig,
  year?: number
): Promise<Record<string, unknown>> {
  const qs = year != null ? `?year=${year}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/resico/health${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error salud RESICO'))
  return (await res.json()) as Record<string, unknown>
}

export async function getResicoShouldPause(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/resico/should-pause`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error pausa fiscal'))
  return (await res.json()) as Record<string, unknown>
}

export async function getResicoMonthlyBreakdown(
  cfg: RuntimeConfig,
  year?: number
): Promise<Record<string, unknown>> {
  const qs = year != null ? `?year=${year}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/resico/monthly-breakdown${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error desglose RESICO'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: proxy / jitter ---
export async function proxyTimbrar(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/proxy/timbrar`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error timbrar proxy'))
  return (await res.json()) as Record<string, unknown>
}

export async function configureProxies(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/proxy/configure`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error configurar proxies'))
  return (await res.json()) as Record<string, unknown>
}

export async function getJitterRandomTime(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/jitter/random-time`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error tiempo aleatorio'))
  return (await res.json()) as Record<string, unknown>
}

export async function distributeTimbrados(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/jitter/distribute`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error distribuir timbrados'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: cash-extraction ---
export async function addRelatedPerson(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cash-extraction/related-person`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error persona relacionada'))
  return (await res.json()) as Record<string, unknown>
}

export async function getSerieBBalance(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cash-extraction/balance`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error balance Serie B'))
  return (await res.json()) as Record<string, unknown>
}

export async function createCashExtraction(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/cash-extraction/create`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error crear extracción'))
  return (await res.json()) as Record<string, unknown>
}

export async function getExtractionContract(
  cfg: RuntimeConfig,
  extractionId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/cash-extraction/contract/${extractionId}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error contrato extracción'))
  return (await res.json()) as Record<string, unknown>
}

export async function getExtractionAnnualSummary(
  cfg: RuntimeConfig,
  year?: number
): Promise<Record<string, unknown>> {
  const qs = year != null ? `?year=${year}` : ''
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/cash-extraction/annual-summary${qs}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error resumen anual'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: climate ---
export async function getCurrentClimate(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/climate/current`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error clima actual'))
  return (await res.json()) as Record<string, unknown>
}

export async function evaluateDegradationRisk(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/climate/evaluate-risk`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error riesgo degradación'))
  return (await res.json()) as Record<string, unknown>
}

export async function generateShrinkageJustification(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/climate/shrinkage-justification`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error justificación merma'))
  return (await res.json()) as Record<string, unknown>
}

export async function attachClimateToMerma(
  cfg: RuntimeConfig,
  mermaId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/climate/attach-merma/${mermaId}`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error adjuntar clima'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: sat-catalog ---
export async function satCatalogSearch(
  cfg: RuntimeConfig,
  q: string,
  limit?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ q })
  if (limit != null) params.set('limit', String(limit))
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/sat-catalog/search?${params}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error búsqueda SAT'))
  return (await res.json()) as Record<string, unknown>
}

export async function satCatalogDescription(
  cfg: RuntimeConfig,
  clave: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/sat-catalog/description/${encodeURIComponent(clave)}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error descripción SAT'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: self-consumption ---
export async function registerSelfConsumption(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/self-consumption/register`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error autoconsumo'))
  return (await res.json()) as Record<string, unknown>
}

export async function registerSample(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/self-consumption/sample`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error muestra'))
  return (await res.json()) as Record<string, unknown>
}

export async function registerEmployeeConsumption(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/self-consumption/employee`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error consumo empleado'))
  return (await res.json()) as Record<string, unknown>
}

export async function getSelfConsumptionSummary(
  cfg: RuntimeConfig,
  year?: number,
  month?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (year != null) params.set('year', String(year))
  if (month != null) params.set('month', String(month))
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/self-consumption/summary${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error resumen autoconsumo'))
  return (await res.json()) as Record<string, unknown>
}

export async function generateSelfConsumptionVoucher(
  cfg: RuntimeConfig,
  year?: number,
  month?: number
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams()
  if (year != null) params.set('year', String(year))
  if (month != null) params.set('month', String(month))
  const qs = params.toString()
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/self-consumption/voucher${qs ? `?${qs}` : ''}`,
    { method: 'POST', headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error voucher autoconsumo'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPendingVoucherMonths(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/self-consumption/pending-months`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error meses pendientes'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: shrinkage ---
export async function registerShrinkageLoss(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shrinkage/register`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error registrar pérdida'))
  return (await res.json()) as Record<string, unknown>
}

export async function authorizeShrinkageLoss(
  cfg: RuntimeConfig,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shrinkage/authorize`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error autorizar pérdida'))
  return (await res.json()) as Record<string, unknown>
}

export async function getShrinkageActa(
  cfg: RuntimeConfig,
  actaNumber: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/shrinkage/acta/${encodeURIComponent(actaNumber)}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error acta pérdida'))
  return (await res.json()) as Record<string, unknown>
}

export async function getShrinkagePending(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shrinkage/pending`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error pérdidas pendientes'))
  return (await res.json()) as Record<string, unknown>
}

export async function getShrinkageSummary(
  cfg: RuntimeConfig,
  year?: number
): Promise<Record<string, unknown>> {
  const qs = year != null ? `?year=${year}` : ''
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/shrinkage/summary${qs}`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error resumen pérdidas'))
  return (await res.json()) as Record<string, unknown>
}

// --- Fiscal: noise ---
export async function getOptimalNoise(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/noise/optimal`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error ruido óptimo'))
  return (await res.json()) as Record<string, unknown>
}

export async function generateNoiseTransaction(
  cfg: RuntimeConfig,
  body?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/noise/generate`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error transacción ruido'))
  return (await res.json()) as Record<string, unknown>
}

export async function startDailyNoise(
  cfg: RuntimeConfig,
  body?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/noise/start-daily`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body ?? {})
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error ruido diario'))
  return (await res.json()) as Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Hardware
// ---------------------------------------------------------------------------

export type InitialSetupStatus = {
  completed: boolean
  completed_at: string | null
  business_name: string
  printer_name: string
}

export type InitialSetupPayload = {
  business_name: string
  business_legal_name?: string
  business_address?: string
  business_rfc?: string
  business_regimen?: string
  business_phone?: string
  business_footer?: string
  receipt_printer_name?: string
  receipt_printer_enabled: boolean
  receipt_paper_width?: 58 | 80
  receipt_auto_print: boolean
  scanner_enabled: boolean
  cash_drawer_enabled: boolean
  cash_drawer_auto_open_cash?: boolean
}

export async function getInitialSetupStatus(cfg: RuntimeConfig): Promise<InitialSetupStatus> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/hardware/setup-status`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error consultando setup inicial'))
  const json = (await res.json()) as { data?: InitialSetupStatus }
  if (!json?.data) throw new Error('Respuesta inesperada del servidor en setup-status')
  return json.data
}

export async function completeInitialSetup(
  cfg: RuntimeConfig,
  body: InitialSetupPayload
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/setup-wizard`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error guardando setup inicial'))
  return (await res.json()) as Record<string, unknown>
}

export type CloudStatus = {
  cloud_activated: boolean
  control_plane_connected: boolean
}

export async function getCloudStatus(cfg: RuntimeConfig): Promise<CloudStatus> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/cloud/status`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error consultando estado de nube'))
  const json = (await res.json()) as { data?: CloudStatus }
  if (!json?.data) throw new Error('Respuesta inesperada del servidor en cloud/status')
  return json.data
}

export type ActivateCloudPayload = {
  email: string
  password: string
  full_name?: string
  business_name?: string
}

export async function activateCloud(
  cfg: RuntimeConfig,
  payload: ActivateCloudPayload
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/cloud/activate`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(payload)
  })
  const text = await res.text()
  if (res.status === 409) {
    throw new Error('Ese correo ya está registrado; inicia sesión en la app del dueño con ese correo.')
  }
  if (!res.ok) {
    throw new Error(parseErrorDetail(text, 'Servidor central no disponible; inténtalo más tarde o en Configuración.'))
  }
  try {
    return JSON.parse(text) as Record<string, unknown>
  } catch {
    return {}
  }
}

export type CupsPrinter = {
  name: string
  display_name: string
  enabled: boolean
  status: string
  is_default: boolean
}

export type HardwareConfig = {
  printer: {
    name: string
    enabled: boolean
    paper_width: number
    char_width: number
    auto_print: boolean
    mode: string
    cut_type: string
  }
  business: {
    name: string
    legal_name: string
    address: string
    rfc: string
    regimen: string
    phone: string
    footer: string
  }
  scanner: {
    enabled: boolean
    prefix: string
    suffix: string
    min_speed_ms: number
    auto_submit: boolean
  }
  drawer: {
    enabled: boolean
    printer_name: string
    auto_open_cash: boolean
    auto_open_card: boolean
    auto_open_transfer: boolean
  }
}

/** True if running inside Electron desktop (reliable at any render phase). */
export function isElectron(): boolean {
  if (typeof window === 'undefined') return false
  return navigator.userAgent.includes('Electron')
}

/** True if running inside a Capacitor native app (Android/iOS). */
export function isCapacitor(): boolean {
  if (typeof window === 'undefined') return false
  if (!('Capacitor' in window)) return false
  const cap = (window as unknown as Record<string, unknown>).Capacitor as
    | { isNativePlatform?: () => boolean }
    | undefined
  return typeof cap?.isNativePlatform === 'function' && cap.isNativePlatform()
}

const HW_CACHE_KEY = 'pos.hwConfig'

/** Read cached HardwareConfig from localStorage (null if missing/corrupt). */
export function loadHwConfigFromCache(): HardwareConfig | null {
  try {
    const raw = localStorage.getItem(HW_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed as HardwareConfig
  } catch {
    return null
  }
}

/** Save HardwareConfig to localStorage cache. */
export function saveHwConfigToCache(cfg: HardwareConfig): void {
  try {
    localStorage.setItem(HW_CACHE_KEY, JSON.stringify(cfg))
  } catch { /* quota exceeded */ }
}

export async function getHardwareConfig(cfg: RuntimeConfig): Promise<HardwareConfig> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/hardware/config`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando config hardware'))
  const json = (await res.json()) as { data?: HardwareConfig }
  if (!json?.data) throw new Error('Respuesta inesperada del servidor en hardware config')
  return json.data
}

export async function updateHardwareConfig(
  cfg: RuntimeConfig,
  section: 'printer' | 'business' | 'scanner' | 'drawer',
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/config/${section}`, {
    method: 'PUT',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error actualizando config'))
  return (await res.json()) as Record<string, unknown>
}

export async function discoverPrinters(cfg: RuntimeConfig): Promise<CupsPrinter[]> {
  // Prefer Electron IPC (host-level CUPS/WinPrint) over backend API (Docker container)
  const api = (window as Window & { api?: { hardware?: { listPrinters?: () => Promise<Array<{ name: string; displayName: string; description: string; status: number; isDefault: boolean }>> } } }).api
  if (typeof api?.hardware?.listPrinters === 'function') {
    const raw = await api.hardware.listPrinters()
    return raw.map((p) => ({
      name: p.name,
      display_name: p.displayName || p.name,
      enabled: p.status === 0,
      status: p.isDefault ? 'idle (default)' : `status ${p.status}`,
      is_default: p.isDefault
    }))
  }
  // Fallback: backend API (works when backend has CUPS access, e.g., bare-metal install)
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/printers`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error detectando impresoras'))
  const json = (await res.json()) as { data?: { printers?: CupsPrinter[] } }
  return json?.data?.printers ?? []
}

export async function testPrint(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/test-print`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error imprimiendo prueba'))
  return (await res.json()) as Record<string, unknown>
}

export async function testDrawer(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/test-drawer`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error probando cajón'))
  return (await res.json()) as Record<string, unknown>
}

export async function printReceipt(
  cfg: RuntimeConfig,
  saleId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/print-receipt`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({ sale_id: saleId })
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error imprimiendo ticket'))
  return (await res.json()) as Record<string, unknown>
}

export async function printShiftReport(
  cfg: RuntimeConfig,
  turnId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/print-shift-report`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify({ turn_id: turnId })
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error imprimiendo corte'))
  return (await res.json()) as Record<string, unknown>
}

export async function openDrawerForSale(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/open-drawer`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error abriendo cajón'))
  return (await res.json()) as Record<string, unknown>
}

// ── Public auth endpoints (no Authorization header) ────────────────────────

/**
 * Checks whether the system needs a first admin user to be created.
 * Public endpoint — no auth headers sent.
 */
export async function checkNeedsFirstUser(cfg: RuntimeConfig): Promise<boolean> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  let res: Response
  try {
    res = await fetch(`${cfg.baseUrl}/api/v1/auth/needs-setup`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal
    })
  } finally {
    clearTimeout(timeout)
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const body = (await res.json()) as { success: boolean; data: { needs_first_user: boolean } }
  return Boolean(body.data?.needs_first_user)
}

/**
 * Creates the first admin (owner) user during initial setup.
 * Public endpoint — no auth headers sent.
 * Throws on network error or non-2xx response.
 * Throws an error with name "ConflictError" on HTTP 409.
 */
export async function setupOwnerUser(
  cfg: RuntimeConfig,
  payload: { username: string; password: string; name?: string }
): Promise<{ token: string; role: string }> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  let res: Response
  try {
    res = await fetch(`${cfg.baseUrl}/api/v1/auth/setup-owner`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    })
  } finally {
    clearTimeout(timeout)
  }
  if (res.status === 409) {
    const err = new Error('Ya existe un usuario administrador. Inicia sesión.')
    err.name = 'ConflictError'
    throw err
  }
  if (!res.ok) {
    throw new Error(parseErrorDetail(await res.text(), 'Error al crear el usuario administrador'))
  }
  const body = (await res.json()) as {
    access_token: string
    role: string
    token_type: string
  }
  return { token: body.access_token, role: body.role }
}
