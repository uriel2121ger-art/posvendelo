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

export function loadRuntimeConfig(): RuntimeConfig {
  try {
    return {
      baseUrl: localStorage.getItem('titan.baseUrl') ?? 'http://127.0.0.1:8000',
      token: localStorage.getItem('titan.token') ?? '',
      terminalId: Number(localStorage.getItem('titan.terminalId') ?? '1')
    }
  } catch {
    return { baseUrl: 'http://127.0.0.1:8000', token: '', terminalId: 1 }
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

async function apiFetch(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 3_000)
  try {
    const res = await fetch(url, { ...init, signal: controller.signal })
    if (res.status === 401) handleExpiredSession()
    return res
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Tiempo de espera agotado. Verifica la conexion al servidor.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

async function apiFetchLong(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15_000)
  try {
    const res = await fetch(url, { ...init, signal: controller.signal })
    if (res.status === 401) handleExpiredSession()
    return res
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Tiempo de espera agotado (15s). Operacion pesada — reintenta mas tarde.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
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
    const res = await apiFetch(`${cfg.baseUrl}${path}`, { headers: headers(cfg) })
    if (res.status === 404 || res.status === 405) continue
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(parseErrorDetail(detail, 'Error del servidor'))
    }
    return res
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sync/${table}`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/turns/open`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/turns/${turnId}/close`, {
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
  const body = (await res.json()) as Record<string, unknown>
  const data = body.data as Record<string, unknown> | null
  return data
}

// ── Inventario ────────────────────────────────────

export async function adjustStock(
  cfg: RuntimeConfig,
  body: { product_id: number; quantity: number; reason: string }
): Promise<Record<string, unknown>> {
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/inventory/adjust`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sales/`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/mermas/approve`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/expenses/`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/employees/`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/employees/${id}`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/employees/${id}`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/open-drawer`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/change-price`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/remote/notification`, {
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
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando notificaciones'))
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sales/${encodeURIComponent(saleId)}/cancel`, {
    method: 'POST',
    headers: headers(cfg)
  })
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
  const res = await apiFetch(
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sales/reports/product-ranking${qs}`, {
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/sales/reports/hourly-heatmap${qs}`, {
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
  const res = await apiFetch(
    `${cfg.baseUrl}/api/v1/inventory/movements${qs ? `?${qs}` : ''}`,
    { headers: headers(cfg) }
  )
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/turns/${turnId}/movements`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(body)
  })
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error registrando movimiento caja'))
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
  const res = await apiFetch(`${cfg.baseUrl}/api/v1/products/stock`, {
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

export async function parseXML(
  cfg: RuntimeConfig,
  file: File
): Promise<Record<string, unknown>> {
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
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando discrepancias'))
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
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error recibiendo transferencia'))
  return (await res.json()) as Record<string, unknown>
}

export async function getPendingGhostTransfers(
  cfg: RuntimeConfig,
  branch?: string
): Promise<Record<string, unknown>> {
  const qs = branch ? `?branch=${encodeURIComponent(branch)}` : ''
  const res = await apiFetchLong(
    `${cfg.baseUrl}/api/v1/fiscal/ghost/transfer/pending${qs}`,
    { headers: headers(cfg) }
  )
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error cargando transferencias'))
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

export async function getExtractionAvailable(
  cfg: RuntimeConfig
): Promise<Record<string, unknown>> {
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
  if (!res.ok)
    throw new Error(parseErrorDetail(await res.text(), 'Error analizando proveedor'))
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
  body: { sale_ids: string[]; confirm_phrase: string }
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
