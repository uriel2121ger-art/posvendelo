import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { getSaleDetail, loadRuntimeConfig, searchSales } from './posApi'

type SaleRow = {
  id: string
  folio: string
  timestamp: string
  customerName: string
  paymentMethod: string
  total: number
}

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeSale(raw: Record<string, unknown>): SaleRow {
  const id = String(raw.id ?? raw.folio ?? `sale-${Date.now()}`)
  return {
    id,
    folio: String(raw.folio ?? id),
    timestamp: String(raw.timestamp ?? raw.created_at ?? ''),
    customerName: String(raw.customer_name ?? raw.customer ?? 'Publico General'),
    paymentMethod: String(raw.payment_method ?? 'cash'),
    total: toNumber(raw.total)
  }
}

function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const toCsvCell = (value: string): string => `"${value.replace(/"/g, '""')}"`
  const csv = [headers.join(','), ...rows.map((r) => r.map(toCsvCell).join(','))].join('\n')
  const blob = new Blob([`${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function getIsoDateDaysAgo(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

export default function HistoryTab(): ReactElement {
  const [rows, setRows] = useState<SaleRow[]>([])
  const [folio, setFolio] = useState('')
  const [paymentFilter, setPaymentFilter] = useState<'all' | 'cash' | 'card' | 'transfer'>('all')
  const [minTotal, setMinTotal] = useState('')
  const [maxTotal, setMaxTotal] = useState('')
  const [dateFrom, setDateFrom] = useState(getIsoDateDaysAgo(7))
  const [dateTo, setDateTo] = useState(new Date().toISOString().slice(0, 10))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Historial operativo: busca y revisa detalle de ventas.')

  const visibleRows = useMemo(() => {
    const min = toNumber(minTotal)
    const max = maxTotal.trim() ? toNumber(maxTotal) : Number.POSITIVE_INFINITY
    return rows.filter((row) => {
      if (paymentFilter !== 'all' && row.paymentMethod !== paymentFilter) return false
      if (row.total < min) return false
      if (row.total > max) return false
      return true
    })
  }, [maxTotal, minTotal, paymentFilter, rows])

  const selectedSale = useMemo(
    () => visibleRows.find((r) => r.id === selectedId) ?? rows.find((r) => r.id === selectedId),
    [rows, selectedId, visibleRows]
  )

  const handleLoad = useCallback(async (): Promise<void> => {
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const sales = await searchSales(cfg, { folio, dateFrom, dateTo, limit: 200 })
      const normalized = sales.map(normalizeSale)
      setRows(normalized)
      setMessage(`Ventas encontradas: ${normalized.length}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }, [dateFrom, dateTo, folio])

  async function loadDetail(saleId: string): Promise<void> {
    setSelectedId(saleId)
    try {
      const cfg = loadRuntimeConfig()
      const payload = await getSaleDetail(cfg, saleId)
      setDetail(payload)
      setMessage(`Detalle cargado: ${saleId}`)
    } catch {
      setDetail(null)
      setMessage('No se pudo cargar detalle completo, mostrando resumen.')
    }
  }

  function exportVisibleCsv(): void {
    const csvRows = visibleRows.map((row) => [
      row.folio,
      row.timestamp,
      row.customerName,
      row.paymentMethod,
      row.total.toFixed(2)
    ])
    downloadCsv(
      `historial_${dateFrom}_${dateTo}.csv`,
      ['folio', 'timestamp', 'cliente', 'metodo_pago', 'total'],
      csvRows
    )
    setMessage('CSV de historial exportado.')
  }

  useEffect(() => {
    void handleLoad()
  }, [handleLoad])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_160px_140px_140px_180px_180px_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Folio"
          value={folio}
          onChange={(e) => setFolio(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
        />
        <select
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={paymentFilter}
          onChange={(e) => setPaymentFilter(e.target.value as 'all' | 'cash' | 'card' | 'transfer')}
        >
          <option value="all">Todos metodos</option>
          <option value="cash">Efectivo</option>
          <option value="card">Tarjeta</option>
          <option value="transfer">Transferencia</option>
        </select>
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={0}
          placeholder="Total min"
          value={minTotal}
          onChange={(e) => setMinTotal(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={0}
          placeholder="Total max"
          value={maxTotal}
          onChange={(e) => setMaxTotal(e.target.value)}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void handleLoad()}
          disabled={busy}
        >
          Buscar
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={exportVisibleCsv}
          disabled={busy || visibleRows.length === 0}
        >
          Exportar CSV
        </button>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden p-4 md:grid-cols-[1fr_360px]">
        <div className="overflow-hidden rounded border border-zinc-800">
          <div className="grid grid-cols-12 gap-2 bg-zinc-900 px-4 py-2 text-xs uppercase text-zinc-400">
            <div className="col-span-3">Folio</div>
            <div className="col-span-3">Fecha</div>
            <div className="col-span-3">Cliente</div>
            <div className="col-span-3 text-right">Total</div>
          </div>
          <div className="max-h-[65vh] overflow-y-auto bg-zinc-950">
            {visibleRows.map((sale) => (
              <button
                key={sale.id}
                className={`grid w-full grid-cols-12 gap-2 border-b border-zinc-900 px-4 py-2 text-left text-sm ${
                  selectedId === sale.id ? 'bg-zinc-900' : 'hover:bg-zinc-900'
                }`}
                onClick={() => void loadDetail(sale.id)}
              >
                <div className="col-span-3 font-mono">{sale.folio}</div>
                <div className="col-span-3">{sale.timestamp.slice(0, 19).replace('T', ' ')}</div>
                <div className="col-span-3 truncate">{sale.customerName}</div>
                <div className="col-span-3 text-right">${sale.total.toFixed(2)}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-hidden rounded border border-zinc-800 bg-zinc-900">
          <div className="border-b border-zinc-800 px-4 py-3 font-semibold">Detalle de venta</div>
          <div className="p-4 text-sm">
            {!selectedSale && (
              <p className="text-zinc-400">Selecciona una venta para ver detalle.</p>
            )}
            {selectedSale && (
              <div className="space-y-2">
                <p>
                  <span className="text-zinc-400">Folio:</span> {selectedSale.folio}
                </p>
                <p>
                  <span className="text-zinc-400">Cliente:</span> {selectedSale.customerName}
                </p>
                <p>
                  <span className="text-zinc-400">Metodo:</span> {selectedSale.paymentMethod}
                </p>
                <p>
                  <span className="text-zinc-400">Total:</span> ${selectedSale.total.toFixed(2)}
                </p>
                {detail && (
                  <pre className="mt-3 max-h-80 overflow-auto rounded border border-zinc-800 bg-zinc-950 p-2 text-xs">
                    {JSON.stringify(detail, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
