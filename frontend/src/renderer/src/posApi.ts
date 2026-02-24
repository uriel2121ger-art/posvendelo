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
  return {
    baseUrl: localStorage.getItem('titan.baseUrl') || 'http://127.0.0.1:8000',
    token: localStorage.getItem('titan.token') || '',
    terminalId: Number(localStorage.getItem('titan.terminalId') || '1')
  }
}

export function saveRuntimeConfig(cfg: RuntimeConfig): void {
  localStorage.setItem('titan.baseUrl', cfg.baseUrl)
  localStorage.setItem('titan.token', cfg.token)
  localStorage.setItem('titan.terminalId', String(cfg.terminalId))
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
  const tsRaw = row.timestamp ?? row.created_at ?? row._received_at
  const tsMs = toTimestampMs(tsRaw)
  if (tsMs === null) return false

  const fromMs = dateFrom ? toTimestampMs(`${dateFrom}T00:00:00`) : null
  const toMs = dateTo ? toTimestampMs(`${dateTo}T23:59:59`) : null

  if (fromMs !== null && tsMs < fromMs) return false
  if (toMs !== null && tsMs > toMs) return false
  return true
}

async function getWithFallback(cfg: RuntimeConfig, paths: string[]): Promise<Response> {
  let lastStatus = 0
  let lastDetail = ''

  for (const path of paths) {
    const res = await fetch(`${cfg.baseUrl}${path}`, { headers: headers(cfg) })
    if (res.status === 404 || res.status === 405) {
      lastStatus = res.status
      continue
    }
    if (!res.ok) {
      lastStatus = res.status
      lastDetail = await res.text()
      continue
    }
    return res
  }

  throw new Error(
    `Error ${lastStatus || 500}: ${lastDetail || 'sin endpoint compatible disponible'}`
  )
}

export async function pullTable(
  table: 'products' | 'customers' | 'inventory' | 'shifts',
  cfg: RuntimeConfig
): Promise<Record<string, unknown>[]> {
  const primaryUrl = `${cfg.baseUrl}/api/v1/sync/${table}`
  const primary = await fetch(primaryUrl, { headers: headers(cfg) })

  if (primary.ok) {
    const body = (await primary.json()) as Record<string, unknown>
    return (body.data ?? body[table] ?? []) as Record<string, unknown>[]
  }

  if (primary.status === 404 || primary.status === 405) {
    const fallbackPath = FALLBACKS[table]
    if (fallbackPath) {
      const fallback = await fetch(`${cfg.baseUrl}${fallbackPath}`, { headers: headers(cfg) })
      if (fallback.ok) {
        const body = (await fallback.json()) as Record<string, unknown>
        return (body[table] ?? body.data ?? body.products ?? body.customers ?? []) as Record<
          string,
          unknown
        >[]
      }
      const detail = await fallback.text()
      throw new Error(`Error ${fallback.status}: ${detail || 'fallo en fallback de carga'}`)
    }
  }

  const detail = await primary.text()
  throw new Error(`Error ${primary.status}: ${detail || 'fallo cargando datos'}`)
}

export async function syncTable(
  table: 'products' | 'customers' | 'inventory' | 'shifts',
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
  const res = await fetch(`${cfg.baseUrl}/api/v1/sync/${table}`, {
    method: 'POST',
    headers: headers(cfg),
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`Error ${res.status}: ${detail || 'fallo sincronizando datos'}`)
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
    `/api/sales/${safeSaleId}`,
    '/api/v1/sync/sales?limit=2000'
  ])
  const body = (await res.json()) as Record<string, unknown>
  const data = body.data as Record<string, unknown>[] | undefined
  if (Array.isArray(data)) {
    const found =
      data.find((row) => String(row.id ?? '') === saleId) ??
      data.find((row) => String(row.folio ?? '') === saleId)
    if (!found) {
      throw new Error(`Venta no encontrada: ${saleId}`)
    }
    return found
  }
  return body
}

export async function getSyncStatus(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await getWithFallback(cfg, ['/api/v1/sync/status', '/api/auth/test'])
  const body = (await res.json()) as Record<string, unknown>
  if (typeof body.status === 'string') return body
  return {
    status: body.ok ? 'ok' : 'unknown',
    details: body,
    timestamp: new Date().toISOString()
  }
}

export async function getSystemInfo(cfg: RuntimeConfig): Promise<Record<string, unknown>> {
  const res = await getWithFallback(cfg, ['/api/info', '/api/auth/test'])
  return (await res.json()) as Record<string, unknown>
}
