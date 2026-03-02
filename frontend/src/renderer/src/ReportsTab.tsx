import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import {
  loadRuntimeConfig,
  searchSales,
  getDailySummaryReport,
  getProductRanking,
  getHourlyHeatmap
} from './posApi'

type SaleReportRow = {
  paymentMethod: string
  total: number
  items: Array<Record<string, unknown>>
}

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function getIsoDateDaysAgo(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

function normalizeSale(raw: Record<string, unknown>): SaleReportRow {
  return {
    paymentMethod: String(raw.payment_method ?? 'cash'),
    total: toNumber(raw.total),
    items: Array.isArray(raw.items) ? (raw.items as Array<Record<string, unknown>>) : []
  }
}

function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

function toCsvCell(value: string): string {
  // Sanitize first: strip control chars, then prefix formula-triggering chars
  const clean = value.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
  const safe = /^[=+\-@\t\r\n]/.test(clean) ? `\t${clean}` : clean
  return `"${safe.replace(/"/g, '""')}"`
}

function buildCsv(headers: string[], rows: string[][]): string {
  return [headers.join(','), ...rows.map((row) => row.map(toCsvCell).join(','))].join('\n')
}

type ReportSubTab = 'local' | 'daily' | 'ranking' | 'heatmap'

export default function ReportsTab(): ReactElement {
  const [subTab, setSubTab] = useState<ReportSubTab>('local')
  const [sales, setSales] = useState<SaleReportRow[]>([])
  const [dateFrom, setDateFrom] = useState(getIsoDateDaysAgo(7))
  const [dateTo, setDateTo] = useState(new Date().toISOString().slice(0, 10))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Reportes operativos listos para analisis diario.')
  const requestIdRef = useRef(0)

  // Extended report data
  const [dailyData, setDailyData] = useState<Record<string, unknown>[]>([])
  const [rankingData, setRankingData] = useState<Record<string, unknown>[]>([])
  const [heatmapData, setHeatmapData] = useState<Record<string, unknown>[]>([])

  const totals = useMemo(() => {
    const totalSales = sales.length
    // Accumulate in cents to avoid float drift over many sales
    const grossCents = sales.reduce((acc, sale) => acc + Math.round(sale.total * 100), 0)
    const gross = grossCents / 100
    const average = totalSales > 0 ? gross / totalSales : 0
    const byMethodCents = sales.reduce<Record<string, number>>((acc, sale) => {
      acc[sale.paymentMethod] = (acc[sale.paymentMethod] ?? 0) + Math.round(sale.total * 100)
      return acc
    }, {})
    const byMethod = Object.fromEntries(Object.entries(byMethodCents).map(([k, v]) => [k, v / 100]))
    const productCounter = new Map<string, { qty: number; amountCents: number }>()
    for (const sale of sales) {
      for (const item of sale.items) {
        const key = String(item.sku ?? item.name ?? 'SIN_SKU')
        const qty = Math.max(0, Math.floor(toNumber(item.qty)))
        const subtotalCents = Math.round(toNumber(item.subtotal) * 100)
        const current = productCounter.get(key) ?? { qty: 0, amountCents: 0 }
        current.qty += qty
        current.amountCents += subtotalCents
        productCounter.set(key, current)
      }
    }
    const topProducts = [...productCounter.entries()]
      .map(([sku, data]) => ({ sku, qty: data.qty, amount: data.amountCents / 100 }))
      .sort((a, b) => b.qty - a.qty)
      .slice(0, 10)

    return { totalSales, gross, average, byMethod, topProducts }
  }, [sales])

  const filtersRef = useRef({ dateFrom, dateTo })
  filtersRef.current = { dateFrom, dateTo }

  const handleLoad = useCallback(async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    const { dateFrom: df, dateTo: dt } = filtersRef.current
    if (df && dt && df > dt) {
      setMessage('Error: La fecha inicio no puede ser posterior a la fecha fin.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const rows = await searchSales(cfg, { dateFrom: df, dateTo: dt, limit: 500 })
      if (requestIdRef.current !== reqId) return
      const normalized = rows.map(normalizeSale)
      setSales(normalized)
      setMessage(`Reporte cargado con ${normalized.length} ventas.`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }, [])

  function exportSummaryCsv(): void {
    const rows: string[][] = [
      ['ventas', String(totals.totalSales)],
      ['monto_total', totals.gross.toFixed(2)],
      ['ticket_promedio', totals.average.toFixed(2)]
    ]
    for (const [method, amount] of Object.entries(totals.byMethod)) {
      rows.push([`metodo_${method}`, amount.toFixed(2)])
    }
    downloadTextFile(
      `reporte_resumen_${dateFrom}_${dateTo}.csv`,
      `${buildCsv(['metrica', 'valor'], rows)}\n`,
      'text/csv;charset=utf-8'
    )
    setMessage('CSV de resumen exportado.')
  }

  function exportTopProductsCsv(): void {
    const rows = totals.topProducts.map((row) => [row.sku, String(row.qty), row.amount.toFixed(2)])
    downloadTextFile(
      `reporte_top_productos_${dateFrom}_${dateTo}.csv`,
      `${buildCsv(['sku', 'cantidad', 'importe'], rows)}\n`,
      'text/csv;charset=utf-8'
    )
    setMessage('CSV de top productos exportado.')
  }

  useEffect(() => {
    void handleLoad()
    return () => {
      requestIdRef.current++
    }
  }, [handleLoad])

  async function loadDailySummary(): Promise<void> {
    const reqId = ++requestIdRef.current
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getDailySummaryReport(cfg)
      if (requestIdRef.current !== reqId) return
      const data = (raw.data ?? raw.summaries ?? []) as Record<string, unknown>[]
      setDailyData(Array.isArray(data) ? data : [])
      setMessage(`Resumen diario: ${(Array.isArray(data) ? data : []).length} registros.`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }

  async function loadRanking(): Promise<void> {
    const reqId = ++requestIdRef.current
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getProductRanking(cfg)
      if (requestIdRef.current !== reqId) return
      const data = (raw.data ?? raw.ranking ?? []) as Record<string, unknown>[]
      setRankingData(Array.isArray(data) ? data : [])
      setMessage(`Ranking: ${(Array.isArray(data) ? data : []).length} productos.`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }

  async function loadHeatmap(): Promise<void> {
    const reqId = ++requestIdRef.current
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getHourlyHeatmap(cfg)
      if (requestIdRef.current !== reqId) return
      const data = (raw.data ?? raw.heatmap ?? []) as Record<string, unknown>[]
      setHeatmapData(Array.isArray(data) ? data : [])
      setMessage(`Heatmap: ${(Array.isArray(data) ? data : []).length} registros.`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }

  const subTabs: { key: ReportSubTab; label: string }[] = [
    { key: 'local', label: 'Local' },
    { key: 'daily', label: 'Resumen Diario' },
    { key: 'ranking', label: 'Ranking' },
    { key: 'heatmap', label: 'Heatmap' }
  ]

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      {/* Sub-tab bar */}
      <div className="flex items-center gap-1 border-b border-zinc-800 bg-zinc-900 p-2 overflow-x-auto shrink-0">
        {subTabs.map((t) => (
          <button
            key={t.key}
            className={`px-4 py-2 rounded font-medium text-sm transition-colors ${
              subTab === t.key
                ? 'bg-zinc-800 shadow-sm border border-zinc-700 font-bold text-blue-400'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
            }`}
            onClick={() => setSubTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {subTab === 'daily' && (
        <div className="flex-1 overflow-auto p-4">
          <div className="flex items-center gap-2 mb-4">
            <button className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50" onClick={() => void loadDailySummary()} disabled={busy}>
              Cargar Resumen Diario
            </button>
          </div>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500">
                <th className="py-3 px-4">Fecha</th>
                <th className="py-3 px-4">Ventas</th>
                <th className="py-3 px-4">Monto</th>
                <th className="py-3 px-4">Ticket Promedio</th>
              </tr>
            </thead>
            <tbody>
              {dailyData.length === 0 && (
                <tr><td colSpan={4} className="py-8 text-center text-zinc-600">Haz clic en Cargar.</td></tr>
              )}
              {dailyData.map((d, i) => (
                <tr key={i} className="border-b border-zinc-800/50">
                  <td className="py-3 px-4">{String(d.date ?? d.fecha ?? '-')}</td>
                  <td className="py-3 px-4">{String(d.sales_count ?? d.ventas ?? 0)}</td>
                  <td className="py-3 px-4">${toNumber(d.total_amount ?? d.monto).toFixed(2)}</td>
                  <td className="py-3 px-4">${toNumber(d.average_ticket ?? d.promedio).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {subTab === 'ranking' && (
        <div className="flex-1 overflow-auto p-4">
          <div className="flex items-center gap-2 mb-4">
            <button className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50" onClick={() => void loadRanking()} disabled={busy}>
              Cargar Ranking
            </button>
          </div>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500">
                <th className="py-3 px-4">Producto</th>
                <th className="py-3 px-4">Cantidad</th>
                <th className="py-3 px-4">Ingreso</th>
              </tr>
            </thead>
            <tbody>
              {rankingData.length === 0 && (
                <tr><td colSpan={3} className="py-8 text-center text-zinc-600">Haz clic en Cargar.</td></tr>
              )}
              {rankingData.map((d, i) => (
                <tr key={i} className="border-b border-zinc-800/50">
                  <td className="py-3 px-4">{String(d.product_name ?? d.sku ?? d.name ?? '-')}</td>
                  <td className="py-3 px-4">{String(d.quantity ?? d.qty ?? 0)}</td>
                  <td className="py-3 px-4">${toNumber(d.revenue ?? d.total).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {subTab === 'heatmap' && (
        <div className="flex-1 overflow-auto p-4">
          <div className="flex items-center gap-2 mb-4">
            <button className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50" onClick={() => void loadHeatmap()} disabled={busy}>
              Cargar Heatmap
            </button>
          </div>
          <div className="grid grid-cols-6 md:grid-cols-12 gap-1">
            {Array.from({ length: 24 }, (_, h) => {
              const entry = heatmapData.find((d) => toNumber(d.hour) === h) as Record<string, unknown> | undefined
              const count = toNumber(entry?.count ?? entry?.sales_count ?? 0)
              const amount = toNumber(entry?.amount ?? entry?.total ?? 0)
              const intensity = Math.min(1, count / Math.max(1, Math.max(...heatmapData.map((d) => toNumber(d.count ?? d.sales_count ?? 0)))))
              return (
                <div
                  key={h}
                  className="rounded-lg border border-zinc-800 p-2 text-center text-xs"
                  style={{ backgroundColor: `rgba(59,130,246,${intensity * 0.6})` }}
                  title={`${h}:00 — ${count} ventas — $${amount.toFixed(2)}`}
                >
                  <div className="font-bold">{h}h</div>
                  <div>{count}</div>
                  <div className="text-zinc-400 text-[10px]">${amount.toFixed(0)}</div>
                </div>
              )
            })}
          </div>
          {heatmapData.length === 0 && (
            <p className="mt-4 text-center text-zinc-600 text-sm">Haz clic en Cargar para ver el heatmap por hora.</p>
          )}
        </div>
      )}

      {subTab === 'local' && (<>
      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[180px_180px_auto_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="date"
          value={dateFrom}
          max={dateTo}
          onChange={(e) => setDateFrom(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="date"
          value={dateTo}
          min={dateFrom}
          onChange={(e) => setDateTo(e.target.value)}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void handleLoad()}
          disabled={busy}
        >
          Recalcular
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={exportSummaryCsv}
          disabled={busy || totals.totalSales === 0}
        >
          Exportar resumen CSV
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={exportTopProductsCsv}
          disabled={busy || totals.topProducts.length === 0}
        >
          Exportar top CSV
        </button>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-4 md:grid-cols-2">
        <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="mb-3 font-semibold">KPIs</h3>
          <div className="space-y-2 text-sm">
            <p>Ventas: {totals.totalSales}</p>
            <p>Monto total: ${totals.gross.toFixed(2)}</p>
            <p>Ticket promedio: ${totals.average.toFixed(2)}</p>
          </div>
        </div>

        <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="mb-3 font-semibold">Metodo de pago</h3>
          <div className="space-y-2 text-sm">
            {Object.entries(totals.byMethod).map(([method, amount]) => (
              <p key={method}>
                {method}: ${amount.toFixed(2)}
              </p>
            ))}
            {Object.keys(totals.byMethod).length === 0 && (
              <p className="text-zinc-400">Sin datos.</p>
            )}
          </div>
        </div>

        <div className="rounded border border-zinc-800 bg-zinc-900 p-4 md:col-span-2">
          <h3 className="mb-3 font-semibold">Top productos</h3>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm">
                <th className="py-4 px-6">SKU/Nombre</th>
                <th className="py-4 px-6">Cantidad</th>
                <th className="py-4 px-6">Importe</th>
              </tr>
            </thead>
            <tbody>
              {totals.topProducts.map((p) => (
                <tr key={p.sku} className="border-b border-zinc-900">
                  <td className="py-4 px-6 font-medium">{p.sku}</td>
                  <td className="py-4 px-6 font-medium">{p.qty}</td>
                  <td className="py-4 px-6 font-medium">${p.amount.toFixed(2)}</td>
                </tr>
              ))}
              {totals.topProducts.length === 0 && (
                <tr>
                  <td className="py-2 text-zinc-400" colSpan={3}>
                    Sin informacion para este rango.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      </>)}

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
