import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  loadRuntimeConfig,
  searchSales,
  getDailySummaryReport,
  getProductRanking,
  getHourlyHeatmap
} from '../posApi'
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Activity,
  PieChart,
  Calendar,
  Download,
  RefreshCw,
  ShoppingCart,
  CreditCard,
  Flame,
  Map,
  ArrowRight,
  FileText,
  Hash
} from 'lucide-react'

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
  // eslint-disable-next-line no-control-regex
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
    const productCounter = new globalThis.Map<string, { qty: number; amountCents: number }>()
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
      // setMessage('Error: La fecha inicio no puede ser posterior a la fecha fin.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const rows = await searchSales(cfg, { dateFrom: df, dateTo: dt, limit: 500 })
      if (requestIdRef.current !== reqId) return
      const normalized = rows.map(normalizeSale)
      setSales(normalized)
      // setMessage(`Reporte cargado con ${normalized.length} ventas.`)
    } catch {
      if (requestIdRef.current !== reqId) return
      // setMessage((error as Error).message)
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
    // setMessage('CSV de resumen exportado.')
  }

  function exportTopProductsCsv(): void {
    const rows = totals.topProducts.map((row) => [row.sku, String(row.qty), row.amount.toFixed(2)])
    downloadTextFile(
      `reporte_top_productos_${dateFrom}_${dateTo}.csv`,
      `${buildCsv(['sku', 'cantidad', 'importe'], rows)}\n`,
      'text/csv;charset=utf-8'
    )
    // setMessage('CSV de top productos exportado.')
  }

  useEffect(() => {
    void handleLoad()
    const reqRef = requestIdRef
    return () => {
      reqRef.current++
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
      // setMessage(`Resumen diario: ${(Array.isArray(data) ? data : []).length} registros.`)
    } catch {
      if (requestIdRef.current !== reqId) return
      // setMessage((error as Error).message)
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
      // setMessage(`Ranking: ${(Array.isArray(data) ? data : []).length} productos.`)
    } catch {
      if (requestIdRef.current !== reqId) return
      // setMessage((error as Error).message)
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
      // setMessage(`Heatmap: ${(Array.isArray(data) ? data : []).length} registros.`)
    } catch {
      if (requestIdRef.current !== reqId) return
      // setMessage((error as Error).message)
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
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-y-auto w-full">
      <div className="max-w-7xl mx-auto w-full p-6 md:p-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black text-white flex items-center gap-3 tracking-tight">
              <BarChart3 className="w-8 h-8 text-indigo-500" />
              Dashboard Gerencial
            </h1>
            <p className="text-zinc-500 mt-2 font-medium">
              Análisis de ventas, rendimiento de productos y métricas clave.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-xl p-1">
              <input
                className="bg-transparent py-1.5 px-3 text-sm font-medium focus:outline-none text-zinc-300 w-36"
                type="date"
                value={dateFrom}
                max={dateTo}
                onChange={(e) => setDateFrom(e.target.value)}
              />
              <span className="text-zinc-700 px-1">-</span>
              <input
                className="bg-transparent py-1.5 px-3 text-sm font-medium focus:outline-none text-zinc-300 w-36"
                type="date"
                value={dateTo}
                min={dateFrom}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
            <button
              onClick={() => void handleLoad()}
              disabled={busy}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl font-bold shadow-[0_4px_20px_-5px_rgba(79,70,229,0.4)] transition-all hover:-translate-y-0.5 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Actualizar
            </button>
          </div>
        </div>

        {/* Global KPI Cards (Local data based on date filters) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Total Revenue */}
          <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6 relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl group-hover:bg-emerald-500/20 transition-colors"></div>
            <div className="flex justify-between items-start mb-4 relative">
              <div className="p-3 bg-zinc-950 rounded-2xl border border-zinc-800 shadow-inner">
                <DollarSign className="w-6 h-6 text-emerald-400" />
              </div>
              <span className="text-xs font-bold uppercase tracking-widest text-zinc-500">
                Ingreso Bruto
              </span>
            </div>
            <div className="relative">
              <p className="text-4xl font-black text-white font-mono tracking-tight">
                ${totals.gross.toFixed(2)}
              </p>
              <p className="text-sm font-medium text-emerald-500 mt-2 flex items-center gap-1">
                <TrendingUp className="w-4 h-4" /> Calculado sobre {totals.totalSales} tickets
              </p>
            </div>
          </div>

          {/* Ticket Promedio */}
          <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6 relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl group-hover:bg-blue-500/20 transition-colors"></div>
            <div className="flex justify-between items-start mb-4 relative">
              <div className="p-3 bg-zinc-950 rounded-2xl border border-zinc-800 shadow-inner">
                <Activity className="w-6 h-6 text-blue-400" />
              </div>
              <span className="text-xs font-bold uppercase tracking-widest text-zinc-500">
                Ticket Promedio
              </span>
            </div>
            <div className="relative">
              <p className="text-4xl font-black text-white font-mono tracking-tight">
                ${totals.average.toFixed(2)}
              </p>
              <p className="text-sm font-medium text-zinc-500 mt-2 flex items-center gap-1">
                Gasto medio por cliente
              </p>
            </div>
          </div>

          {/* Artículos (Aprox based on tickets/qty) */}
          <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6 relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-colors"></div>
            <div className="flex justify-between items-start mb-4 relative">
              <div className="p-3 bg-zinc-950 rounded-2xl border border-zinc-800 shadow-inner">
                <ShoppingCart className="w-6 h-6 text-indigo-400" />
              </div>
              <span className="text-xs font-bold uppercase tracking-widest text-zinc-500">
                Ventas
              </span>
            </div>
            <div className="relative">
              <p className="text-4xl font-black text-white font-mono tracking-tight">
                {totals.totalSales}
              </p>
              <p className="text-sm font-medium text-zinc-500 mt-2 flex items-center gap-1">
                Operaciones concretadas
              </p>
            </div>
          </div>
        </div>

        {/* Sub Navigation */}
        <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-px">
          {subTabs.map((t) => (
            <button
              key={t.key}
              className={`px-6 py-3 font-semibold text-sm transition-all border-b-2 ${
                subTab === t.key
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'
              }`}
              onClick={() => setSubTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab Content Areas */}
        <div className="min-h-[500px]">
          {/* LOCAL DASHBOARD */}
          {subTab === 'local' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-fade-in-up">
              {/* Left Col: Methods & Export */}
              <div className="space-y-8">
                <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6">
                  <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2 mb-6">
                    <PieChart className="w-5 h-5 text-zinc-400" /> Distribución de Ingresos
                  </h3>
                  <div className="space-y-4">
                    {Object.entries(totals.byMethod).length === 0 ? (
                      <p className="text-zinc-600 text-sm text-center py-4">
                        Sin datos de métodos.
                      </p>
                    ) : (
                      Object.entries(totals.byMethod)
                        .sort(([, a], [, b]) => b - a)
                        .map(([method, amount]) => {
                          const percentage = totals.gross > 0 ? (amount / totals.gross) * 100 : 0
                          return (
                            <div key={method}>
                              <div className="flex justify-between items-end mb-1">
                                <span className="text-sm font-bold text-zinc-300 capitalize flex items-center gap-2">
                                  {method === 'cash' ? (
                                    <DollarSign className="w-4 h-4 text-emerald-500" />
                                  ) : method === 'card' ? (
                                    <CreditCard className="w-4 h-4 text-blue-500" />
                                  ) : (
                                    <RefreshCw className="w-4 h-4 text-purple-500" />
                                  )}
                                  {method}
                                </span>
                                <span className="text-sm font-mono text-zinc-400">
                                  ${amount.toFixed(2)}
                                </span>
                              </div>
                              <div className="w-full bg-zinc-950 rounded-full h-2 overflow-hidden border border-zinc-800/80">
                                <div
                                  className={`h-full rounded-full ${method === 'cash' ? 'bg-emerald-500' : method === 'card' ? 'bg-blue-500' : 'bg-purple-500'}`}
                                  style={{ width: `${percentage}%` }}
                                ></div>
                              </div>
                            </div>
                          )
                        })
                    )}
                  </div>
                </div>

                <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6">
                  <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2 mb-6">
                    <Download className="w-5 h-5 text-zinc-400" /> Exportaciones
                  </h3>
                  <div className="space-y-3">
                    <button
                      onClick={exportSummaryCsv}
                      disabled={busy || totals.totalSales === 0}
                      className="w-full flex justify-between items-center bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 rounded-xl p-4 transition-colors group disabled:opacity-50"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-indigo-400 group-hover:scale-110 transition-transform" />
                        <div className="text-left">
                          <p className="text-sm font-bold text-white">Resumen Diario</p>
                          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
                            KPIs y Métodos (.CSV)
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-zinc-600 group-hover:text-white transition-colors" />
                    </button>
                    <button
                      onClick={exportTopProductsCsv}
                      disabled={busy || totals.topProducts.length === 0}
                      className="w-full flex justify-between items-center bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 rounded-xl p-4 transition-colors group disabled:opacity-50"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-amber-400 group-hover:scale-110 transition-transform" />
                        <div className="text-left">
                          <p className="text-sm font-bold text-white">Top Productos</p>
                          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
                            SKUs más vendidos (.CSV)
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-zinc-600 group-hover:text-white transition-colors" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Col: Top Products */}
              <div className="lg:col-span-2 bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6 flex flex-col">
                <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2 mb-6">
                  <Flame className="w-5 h-5 text-amber-500" /> Artículos Más Prolíficos (Top 10)
                </h3>
                <div className="flex-1 overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold">
                        <th className="pb-3 pr-4">#</th>
                        <th className="pb-3 px-4">SKU / Producto</th>
                        <th className="pb-3 px-4 text-right">Unidades</th>
                        <th className="pb-3 pl-4 text-right">Ingreso Bruto</th>
                        <th className="pb-3 pl-4 w-32">Proporción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/30">
                      {(() => {
                        const maxRevenue = Math.max(1, ...totals.topProducts.map((tp) => tp.amount))
                        return totals.topProducts.map((p, idx) => {
                          const barWidth = maxRevenue > 0 ? (p.amount / maxRevenue) * 100 : 0
                          return (
                            <tr key={p.sku} className="hover:bg-zinc-800/20 transition-colors">
                              <td className="py-4 pr-4 text-zinc-600 font-bold text-xs">
                                {idx + 1}
                              </td>
                              <td
                                className="py-4 px-4 font-bold text-zinc-200 capitalize w-1/3 truncate max-w-[200px]"
                                title={p.sku}
                              >
                                {p.sku}
                              </td>
                              <td className="py-4 px-4 text-right font-mono text-zinc-400">
                                {p.qty}
                              </td>
                              <td className="py-4 pl-4 text-right font-mono font-bold text-emerald-400">
                                ${p.amount.toFixed(2)}
                              </td>
                              <td className="py-4 pl-4">
                                <div className="w-full bg-zinc-950 h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-amber-500 rounded-full"
                                    style={{ width: `${barWidth}%` }}
                                  ></div>
                                </div>
                              </td>
                            </tr>
                          )
                        })
                      })()}
                      {totals.topProducts.length === 0 && (
                        <tr>
                          <td colSpan={5} className="py-12 text-center text-zinc-600">
                            No hay información suficiente para el top.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* DAILY DASHBOARD */}
          {subTab === 'daily' && (
            <div className="animate-fade-in-up bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-blue-500" /> Resumen Histórico Diario (Backend)
                </h3>
                <button
                  className="bg-zinc-900 border border-zinc-700 text-zinc-300 hover:text-white px-4 py-2 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                  onClick={() => void loadDailySummary()}
                  disabled={busy}
                >
                  Descargar del Servidor
                </button>
              </div>
              <div className="overflow-x-auto rounded-xl border border-zinc-800/80 bg-zinc-950">
                <table className="w-full text-left">
                  <thead className="bg-zinc-900 border-b border-zinc-800/80">
                    <tr className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                      <th className="py-4 px-6">Fecha Operativa</th>
                      <th className="py-4 px-6 text-right">Cant. Ventas</th>
                      <th className="py-4 px-6 text-right">Monto Procesado</th>
                      <th className="py-4 px-6 text-right">Ticket Promedio</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {dailyData.length === 0 && (
                      <tr>
                        <td colSpan={4} className="py-12 text-center text-zinc-600">
                          Presiona &quot;Descargar del Servidor&quot; para consultar históricos.
                        </td>
                      </tr>
                    )}
                    {dailyData.map((d, i) => (
                      <tr key={i} className="hover:bg-zinc-900/50 transition-colors">
                        <td className="py-4 px-6 font-mono text-zinc-300">
                          {String(d.date ?? d.fecha ?? '-')}
                        </td>
                        <td className="py-4 px-6 font-mono text-zinc-400 text-right">
                          {String(d.sales_count ?? d.ventas ?? 0)}
                        </td>
                        <td className="py-4 px-6 font-mono font-bold text-emerald-400 text-right">
                          ${toNumber(d.total_amount ?? d.monto).toFixed(2)}
                        </td>
                        <td className="py-4 px-6 font-mono text-blue-400 text-right">
                          ${toNumber(d.average_ticket ?? d.promedio).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* RANKING GLOBAL */}
          {subTab === 'ranking' && (
            <div className="animate-fade-in-up bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2">
                  <Hash className="w-5 h-5 text-amber-500" /> Ranking Global de Productos (Backend)
                </h3>
                <button
                  className="bg-zinc-900 border border-zinc-700 text-zinc-300 hover:text-white px-4 py-2 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                  onClick={() => void loadRanking()}
                  disabled={busy}
                >
                  Descargar Global
                </button>
              </div>
              <div className="overflow-x-auto rounded-xl border border-zinc-800/80 bg-zinc-950">
                <table className="w-full text-left">
                  <thead className="bg-zinc-900 border-b border-zinc-800/80">
                    <tr className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                      <th className="py-4 px-6 w-16">Rank</th>
                      <th className="py-4 px-6">Identificador / Nombre</th>
                      <th className="py-4 px-6 text-right">Volumen</th>
                      <th className="py-4 px-6 text-right">Recaudación Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {rankingData.length === 0 && (
                      <tr>
                        <td colSpan={4} className="py-12 text-center text-zinc-600">
                          Presiona &quot;Descargar Global&quot; para obtener el histórico.
                        </td>
                      </tr>
                    )}
                    {rankingData.map((d, i) => (
                      <tr key={i} className="hover:bg-zinc-900/50 transition-colors">
                        <td className="py-4 px-6 font-bold text-zinc-600 text-xs">{i + 1}</td>
                        <td className="py-4 px-6 font-bold text-zinc-200 capitalize">
                          {String(d.product_name ?? d.sku ?? d.name ?? '-')}
                        </td>
                        <td className="py-4 px-6 font-mono text-zinc-400 text-right">
                          {String(d.quantity ?? d.qty ?? 0)}
                        </td>
                        <td className="py-4 px-6 font-mono font-bold text-emerald-400 text-right">
                          ${toNumber(d.revenue ?? d.total).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* HEATMAP */}
          {subTab === 'heatmap' && (
            <div className="animate-fade-in-up bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2">
                  <Map className="w-5 h-5 text-rose-500" /> Intensidad de Tráfico (Zonas Calientes)
                </h3>
                <button
                  className="bg-zinc-900 border border-zinc-700 text-zinc-300 hover:text-white px-4 py-2 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                  onClick={() => void loadHeatmap()}
                  disabled={busy}
                >
                  Procesar Matriz Termal
                </button>
              </div>
              <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-12 gap-3">
                {(() => {
                  const maxCount = Math.max(
                    1,
                    ...heatmapData.map((d) => toNumber(d.count ?? d.sales_count ?? 0))
                  )
                  return Array.from({ length: 24 }, (_, h) => {
                    const entry = heatmapData.find((d) => toNumber(d.hour) === h) as
                      | Record<string, unknown>
                      | undefined
                    const count = toNumber(entry?.count ?? entry?.sales_count ?? 0)
                    const amount = toNumber(entry?.amount ?? entry?.total ?? 0)
                    const intensity = Math.min(1, count / maxCount)

                    let bgClass = 'bg-zinc-950 border-zinc-800/80 text-zinc-500'
                    if (intensity > 0)
                      bgClass = 'bg-indigo-900/30 border-indigo-500/30 text-indigo-400'
                    if (intensity > 0.3)
                      bgClass = 'bg-indigo-800/50 border-indigo-400/50 text-indigo-300'
                    if (intensity > 0.6) bgClass = 'bg-rose-900/50 border-rose-500/50 text-rose-300'
                    if (intensity > 0.8)
                      bgClass =
                        'bg-rose-600/80 border-rose-400 shadow-[0_0_15px_rgba(225,29,72,0.4)] text-white'

                    return (
                      <div
                        key={h}
                        className={`relative flex flex-col items-center justify-center p-4 rounded-2xl border transition-all hover:scale-105 cursor-default ${bgClass}`}
                        title={`${h}:00 — ${count} transacciones — ${amount.toFixed(2)}`}
                      >
                        <span className="absolute top-2 left-2 text-[10px] font-bold opacity-70 uppercase tracking-widest">
                          {h}:00
                        </span>
                        <div className="mt-2 text-2xl font-black font-mono">{count}</div>
                        <div className="text-[10px] opacity-80 mt-1 font-mono">
                          ${amount.toFixed(0)}
                        </div>
                      </div>
                    )
                  })
                })()}
              </div>
              {heatmapData.length === 0 && (
                <p className="mt-8 text-center text-zinc-600 text-sm">
                  Ejecuta la descarga del servidor para evaluar los picos de afluencia.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
