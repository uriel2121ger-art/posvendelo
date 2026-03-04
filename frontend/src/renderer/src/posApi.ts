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

const FALLBACKS: Record<string, string> = {
  products: '/api/v1/products/',
  customers: '/api/v1/customers/',
  inventory: '/api/v1/inventory/'
}

const _DEFAULT_PORTS = [8000, 8080, 8090, 3000]

function getDiscoverPorts(): number[] {
  try {
    const custom = localStorage.getItem('titan.discoverPorts')
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
  return _DEFAULT_PORTS
}

export async function autoDiscoverBackend(): Promise<string | null> {
  const saved = localStorage.getItem('titan.baseUrl')
  if (saved && _isValidBaseUrl(saved)) {
    try {
      const r = await fetch(`${saved}/api/v1/auth/verify`, { signal: AbortSignal.timeout(1500) })
      if (r.status === 401 || r.ok) return saved
    } catch {
      /* saved URL unreachable, try discovery */
    }
  }
  for (const port of getDiscoverPorts()) {
    const url = `http://localhost:${port}`
    try {
      const r = await fetch(`${url}/api/v1/auth/verify`, { signal: AbortSignal.timeout(1200) })
      if (r.status === 401 || r.ok) {
        localStorage.setItem('titan.baseUrl', url)
        return url
      }
    } catch {
      /* port not responding */
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
    const payload = JSON.parse(atob(parts[1]))
    if (!payload.exp) return false
    return payload.exp * 1000 < Date.now()
  } catch {
    // Malformed base64 or invalid JSON — treat as expired for safety
    return true
  }
}

/** En modo navegador (Vite dev puerto 5173) usar '' para que las peticiones pasen por el proxy a 8000. */
function getEffectiveBaseUrl(saved: string): string {
  if (typeof window === 'undefined') return _isValidBaseUrl(saved) ? saved : 'http://localhost:8000'
  const origin = window.location.origin
  const isViteDev = window.location.port === '5173' && (origin.startsWith('http://localhost:') || origin.startsWith('http://127.0.0.1:'))
  const pointsToLocal8000 =
    saved === 'http://localhost:8000' || saved === 'http://127.0.0.1:8000' || saved === ''
  if (isViteDev && pointsToLocal8000) return ''
  return _isValidBaseUrl(saved) ? saved : 'http://localhost:8000'
}

export function loadRuntimeConfig(): RuntimeConfig {
  try {
    const baseUrl = localStorage.getItem('titan.baseUrl') ?? 'http://localhost:8000'
    let token = localStorage.getItem('titan.token') ?? ''
    // Auto-clear expired tokens to force re-login
    if (token && _isTokenExpired(token)) {
      localStorage.removeItem('titan.token')
      token = ''
    }
    return {
      baseUrl: getEffectiveBaseUrl(baseUrl),
      token,
      terminalId: Math.max(1, parseInt(localStorage.getItem('titan.terminalId') ?? '1', 10) || 1)
    }
  } catch {
    return { baseUrl: 'http://localhost:8000', token: '', terminalId: 1 }
  }
}

export function saveRuntimeConfig(cfg: RuntimeConfig): void {
  try {
    localStorage.setItem('titan.baseUrl', cfg.baseUrl)
    localStorage.setItem('titan.token', cfg.token)
    localStorage.setItem('titan.terminalId', String(cfg.terminalId))
  } catch {
    // QuotaExceededError — silently ignore, config stays in memory
  }
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

function handleExpiredSession(): never {
  try {
    localStorage.removeItem('titan.token')
    localStorage.removeItem('titan.user')
    localStorage.removeItem('titan.currentShift')
  } catch {
    /* storage inaccessible — proceed with redirect */
  }
  window.location.hash = '#/login'
  throw new Error('Sesión expirada. Inicia sesión de nuevo.')
}

function parseErrorDetail(text: string, fallback: string): string {
  try {
    const body = JSON.parse(text)
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      const msgs = body.detail
        .map((e: Record<string, unknown>) => {
          const msg = typeof e.msg === 'string' ? e.msg : ''
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

async function apiFetchOnce(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...init, signal: controller.signal })
    if (res.status === 401) handleExpiredSession()
    return res
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Tiempo de espera agotado. Verifica la conexion al servidor.')
    }
    const msg = err instanceof Error ? err.message : String(err)
    if (/failed to fetch|network error|load failed/i.test(msg) || err instanceof TypeError) {
      throw new Error(
        'No se pudo conectar al servidor. Comprueba que el backend este en marcha (ej. docker compose up -d o uvicorn en puerto 8000).'
      )
    }
    throw err
  } finally {
    clearTimeout(timeout)
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
    return localStorage.getItem('titan.role') ?? 'cashier'
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
    if (!body || typeof body !== 'object') return []
    const candidate = body.data ?? body[table] ?? []
    return Array.isArray(candidate) ? (candidate as Record<string, unknown>[]) : []
  }

  if (primary.status === 404 || primary.status === 405) {
    const fallbackPath = FALLBACKS[table]
    if (fallbackPath) {
      const fallback = await apiFetch(`${cfg.baseUrl}${fallbackPath}`, { headers: headers(cfg) })
      if (fallback.ok) {
        const body = (await fallback.json()) as Record<string, unknown> | null
        if (!body || typeof body !== 'object') return []
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
  return body
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/turns/current`, { headers: headers(cfg) })
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
  return (await res.json()) as Record<string, unknown>
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error abriendo cajon'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error enviando notificacion'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando Wealth'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDashboardAI(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/dashboard/ai`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando AI'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDashboardExecutive(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/dashboard/executive`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando Executive'))
  return (await res.json()) as Record<string, unknown>
}

// ── Sales Extendido ───────────────────────────────

export async function cancelSale(
  cfg: RuntimeConfig,
  saleId: string
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/sales/${encodeURIComponent(saleId)}/cancel`,
    {
      method: 'POST',
      headers: headers(cfg)
    }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cancelando venta'))
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/inventory/alerts`, {
    headers: headers(cfg)
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
  body: { movement_type: string; amount: number; reason: string; manager_pin?: string }
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

export async function createCustomer(
  cfg: RuntimeConfig,
  body: { name: string; phone?: string; email?: string }
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando credito'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando categorias'))
  return (await res.json()) as Record<string, unknown>
}

// ── SAT ────────────────────────────────────────

export async function searchSatCodes(
  cfg: RuntimeConfig,
  query: string,
  limit = 20
): Promise<{ code: string; description: string }[]> {
  const res = await apiFetch(
    `${cfg.baseUrl}/api/v1/sat/search?q=${encodeURIComponent(query)}&limit=${limit}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) return []
  const body = (await res.json()) as Record<string, unknown>
  const data = body.data as Record<string, unknown> | undefined
  return (data?.results ?? []) as { code: string; description: string }[]
}

export async function getSatUnits(cfg: RuntimeConfig): Promise<{ code: string; name: string }[]> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sat/units`, {
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error procesando devolucion'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error parseando XML'))
  return (await res.json()) as Record<string, unknown>
}

export async function runAudit(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/audit/run`, {
    method: 'POST',
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error ejecutando auditoria'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando wallet'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando stats wallet'))
  return (await res.json()) as Record<string, unknown>
}

export async function getExtractionAvailable(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/extraction/available`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando extraccion disponible'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error creando plan extraccion'))
  return (await res.json()) as Record<string, unknown>
}

export async function getOptimalExtraction(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/extraction/optimal`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando extraccion optima'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCryptoAvailable(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/crypto/available`, {
    headers: headers(cfg)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando crypto disponible'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error convirtiendo crypto'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCryptoWealth(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/fiscal/crypto/wealth`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando crypto wealth'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error en eliminacion'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error en fake screen'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error dashboard riqueza'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error lockdown'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error release lockdown'))
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/shadow/dual-stock/${productId}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/cost/dual-view/${productId}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error vista dual costos'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostFiscal(
  cfg: RuntimeConfig,
  productId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/cost/fiscal/${productId}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error costo fiscal'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostReal(
  cfg: RuntimeConfig,
  productId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/cost/real/${productId}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error costo real'))
  return (await res.json()) as Record<string, unknown>
}

export async function getCostProfit(
  cfg: RuntimeConfig,
  saleId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/cost/profit/${saleId}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/fiscal-dashboard/data${qs}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/discrepancy/trend${qs}`,
    { headers: headers(cfg) }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error tendencia'))
  return (await res.json()) as Record<string, unknown>
}

export async function getDiscrepancySuggestExtraction(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/discrepancy/suggest-extraction`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/resico/health${qs}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/resico/monthly-breakdown${qs}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/climate/shrinkage-justification`,
    {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify(body)
    }
  )
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error justificación merma'))
  return (await res.json()) as Record<string, unknown>
}

export async function attachClimateToMerma(
  cfg: RuntimeConfig,
  mermaId: number
): Promise<Record<string, unknown>> {
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/climate/attach-merma/${mermaId}`,
    {
      method: 'POST',
      headers: headers(cfg)
    }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/sat-catalog/search?${params}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/self-consumption/pending-months`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/shrinkage/summary${qs}`,
    { headers: headers(cfg) }
  )
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

export type CupsPrinter = {
  name: string
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

export async function getHardwareConfig(cfg: RuntimeConfig): Promise<HardwareConfig> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/hardware/config`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error cargando config hardware'))
  const json = (await res.json()) as { data: HardwareConfig }
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
  const res = await apiFetchLong(`${cfg.baseUrl}/api/v1/hardware/printers`, {
    headers: headers(cfg)
  })
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error detectando impresoras'))
  const json = (await res.json()) as { data: { printers: CupsPrinter[] } }
  return json.data.printers
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error probando cajon'))
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
  if (!res.ok) throw new Error(parseErrorDetail(await res.text(), 'Error abriendo cajon'))
  return (await res.json()) as Record<string, unknown>
}
