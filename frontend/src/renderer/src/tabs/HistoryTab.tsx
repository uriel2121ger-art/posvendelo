import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useConfirm } from '../components/ConfirmDialog'
import {
  Search,
  X,
  RefreshCw,
  FileText,
  Receipt,
  Calendar,
  CreditCard,
  Banknote,
  HelpCircle,
  Ban,
  Eye,
  Clock
} from 'lucide-react'
import {
  getSaleDetail,
  loadRuntimeConfig,
  searchSales,
  cancelSale,
  getSaleEvents,
  getUserRole
} from '../posApi'
import { useFocusTrap } from '../hooks/useFocusTrap'

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

function toCsvCell(value: string): string {
  // Strip non-printable control chars, then prefix formula-triggering chars with tab
  // eslint-disable-next-line no-control-regex
  const clean = value.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
  const safe = /^[=+\-@\t\r\n]/.test(clean) ? `\t${clean}` : clean
  return `"${safe.replace(/"/g, '""')}"`
}

function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const csv = [headers.join(','), ...rows.map((r) => r.map(toCsvCell).join(','))].join('\n')
  const blob = new Blob([`${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

function getIsoDateDaysAgo(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

export default function HistoryTab(): ReactElement {
  const confirm = useConfirm()
  const [rows, setRows] = useState<SaleRow[]>([])
  const [folio, setFolio] = useState('')
  const [paymentFilter, setPaymentFilter] = useState<'all' | 'cash' | 'card' | 'transfer'>('all')
  const [minTotal, setMinTotal] = useState('')
  const [maxTotal, setMaxTotal] = useState('')
  const [dateFrom, setDateFrom] = useState(getIsoDateDaysAgo(7))
  const [dateTo, setDateTo] = useState(new Date().toISOString().slice(0, 10))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Historial operativo: busca y revisa detalle de ventas.')
  const [events, setEvents] = useState<Record<string, unknown>[]>([])
  const requestIdRef = useRef(0)
  const detailRequestId = useRef(0)
  const drawerRef = useRef<HTMLDivElement>(null)
  const role = getUserRole()

  useFocusTrap(drawerRef, isDrawerOpen)
  const canManage = role === 'manager' || role === 'owner' || role === 'admin'

  const visibleRows = useMemo(() => {
    const min = minTotal.trim() ? toNumber(minTotal) : 0
    const max = maxTotal.trim() ? toNumber(maxTotal) : Number.POSITIVE_INFINITY
    return rows.filter((row) => {
      if (paymentFilter !== 'all' && row.paymentMethod !== paymentFilter) return false
      if (min > 0 && row.total < min) return false
      if (max < Number.POSITIVE_INFINITY && row.total > max) return false
      return true
    })
  }, [maxTotal, minTotal, paymentFilter, rows])

  const selectedSale = useMemo(
    () => visibleRows.find((r) => r.id === selectedId) ?? rows.find((r) => r.id === selectedId),
    [rows, selectedId, visibleRows]
  )

  // Use refs for current filter values to avoid re-creating the callback on every keystroke
  const filtersRef = useRef({ folio, dateFrom, dateTo })
  filtersRef.current = { folio, dateFrom, dateTo }

  const handleLoad = useCallback(async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    const { folio: f, dateFrom: df, dateTo: dt } = filtersRef.current
    if (df && dt && df > dt) {
      setMessage('Error: La fecha inicio no puede ser posterior a la fecha fin.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const sales = await searchSales(cfg, { folio: f, dateFrom: df, dateTo: dt, limit: 200 })
      if (requestIdRef.current !== reqId) return
      const normalized = sales.map(normalizeSale)
      setRows(normalized)
      setMessage(`Ventas encontradas: ${normalized.length}`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }, [])

  async function loadDetail(saleId: string): Promise<void> {
    const reqId = ++detailRequestId.current
    setSelectedId(saleId)
    setDetail(null)
    try {
      const cfg = loadRuntimeConfig()
      const payload = await getSaleDetail(cfg, saleId)
      if (detailRequestId.current !== reqId) return
      setDetail(payload)
      setMessage(`Detalle cargado: ${saleId}`)
      void loadEvents(saleId)
    } catch {
      if (detailRequestId.current !== reqId) return
      setDetail(null)
      setMessage('No se pudo cargar detalle completo, mostrando resumen.')
    }
  }

  async function handleCancelSale(): Promise<void> {
    if (!selectedId || !canManage) return
    if (
      !(await confirm('¿Cancelar esta venta? Esta accion no se puede deshacer.', {
        variant: 'danger',
        title: 'Cancelar venta'
      }))
    )
      return
    if (
      !(await confirm('SEGUNDA CONFIRMACION: ¿Estas seguro de cancelar?', {
        variant: 'danger',
        title: 'Confirmar cancelacion'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await cancelSale(cfg, selectedId)
      setMessage(`Venta ${selectedId} cancelada.`)
      setSelectedId(null)
      setDetail(null)
      setEvents([])
      setIsDrawerOpen(false)
      void handleLoad()
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function loadEvents(saleId: string): Promise<void> {
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getSaleEvents(cfg, saleId)
      const data = (raw.data ?? raw.events ?? []) as Record<string, unknown>[]
      setEvents(Array.isArray(data) ? data : [])
    } catch {
      setEvents([])
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
    const reqRef = requestIdRef
    const detailRef = detailRequestId
    return () => {
      reqRef.current++
      detailRef.current++
    }
  }, [handleLoad])

  return (
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-hidden relative">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Header Area */}
        <div className="px-8 py-6 border-b border-zinc-900 bg-zinc-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Receipt className="w-7 h-7 text-indigo-500" />
              Historial de Transacciones
            </h1>
            <p className="text-zinc-500 text-sm mt-1">
              {rows.length} operaciones registradas en el periodo actual
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={exportVisibleCsv}
              disabled={busy || visibleRows.length === 0}
              className="flex items-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 px-4 py-2.5 rounded-xl font-semibold transition-colors border border-zinc-800 disabled:opacity-50"
            >
              <FileText className="w-4 h-4" />
              <span>Exportar CSV</span>
            </button>
            <button
              onClick={() => void handleLoad()}
              disabled={busy}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl font-bold shadow-[0_4px_20px_-5px_rgba(79,70,229,0.4)] transition-all hover:-translate-y-0.5"
            >
              <RefreshCw className={`w-5 h-5 ${busy ? 'animate-spin' : ''}`} />
              <span>Actualizar</span>
            </button>
          </div>
        </div>

        {/* Filters Toolbar */}
        <div className="px-8 py-4 bg-zinc-950/50 flex flex-wrap items-center gap-3 shrink-0">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-2 pl-10 pr-4 text-sm font-medium focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-zinc-600"
              placeholder="Buscar por Folio..."
              value={folio}
              onChange={(e) => setFolio(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-xl px-2 py-1">
            <Calendar className="w-4 h-4 text-zinc-500 ml-2" />
            <input
              className="bg-transparent py-1 px-2 text-sm font-medium focus:outline-none text-zinc-300"
              type="date"
              value={dateFrom}
              max={dateTo}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <span className="text-zinc-600">-</span>
            <input
              className="bg-transparent py-1 px-2 text-sm font-medium focus:outline-none text-zinc-300"
              type="date"
              value={dateTo}
              min={dateFrom}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <select
            className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2 text-sm font-medium focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            value={paymentFilter}
            onChange={(e) =>
              setPaymentFilter(e.target.value as 'all' | 'cash' | 'card' | 'transfer')
            }
          >
            <option value="all">Todos los métodos</option>
            <option value="cash">Efectivo</option>
            <option value="card">Tarjeta</option>
            <option value="transfer">Transferencia</option>
          </select>
          <div className="flex items-center gap-2">
            <input
              className="w-24 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-sm font-medium focus:outline-none focus:border-indigo-500 placeholder:text-zinc-600 text-center"
              type="number"
              min={0}
              placeholder="Min $"
              value={minTotal}
              onChange={(e) => setMinTotal(e.target.value)}
            />
            <span className="text-zinc-600">-</span>
            <input
              className="w-24 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-sm font-medium focus:outline-none focus:border-indigo-500 placeholder:text-zinc-600 text-center"
              type="number"
              min={0}
              placeholder="Max $"
              value={maxTotal}
              onChange={(e) => setMaxTotal(e.target.value)}
            />
          </div>
        </div>

        {/* Master List (Data Grid) */}
        <div className="flex-1 overflow-y-auto px-8 py-4">
          {visibleRows.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500 bg-zinc-900/20 border border-zinc-800/50 rounded-2xl">
              <Receipt className="w-16 h-16 mb-4 opacity-20" />
              <p className="text-lg font-medium text-zinc-400">Sin resultados de búsqueda</p>
              <p className="text-sm mt-1">Ajusta los filtros o intenta con otras fechas.</p>
            </div>
          ) : (
            <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-2xl overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-zinc-900/90 backdrop-blur-sm z-10">
                  <tr className="border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold">
                    <th className="px-6 py-4 w-40">Folio Transacción</th>
                    <th className="px-6 py-4 w-48">Fecha y Hora</th>
                    <th className="px-6 py-4">Cliente</th>
                    <th className="px-6 py-4 w-32">Método</th>
                    <th className="px-6 py-4 text-right w-32">Monto Total</th>
                    <th className="px-6 py-4 w-16"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {visibleRows.map((sale) => (
                    <tr
                      key={sale.id}
                      onClick={() => {
                        void loadDetail(sale.id)
                        setIsDrawerOpen(true)
                      }}
                      className="group hover:bg-zinc-800/40 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 font-mono text-sm text-zinc-300 group-hover:text-indigo-400 transition-colors">
                        {sale.folio}
                      </td>
                      <td className="px-6 py-4 text-zinc-400 text-sm">
                        {sale.timestamp.slice(0, 16).replace('T', ' ')}
                      </td>
                      <td className="px-6 py-4 font-medium text-zinc-200 truncate">
                        {sale.customerName}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {sale.paymentMethod === 'cash' ? (
                            <Banknote className="w-4 h-4 text-emerald-500" />
                          ) : sale.paymentMethod === 'card' ? (
                            <CreditCard className="w-4 h-4 text-blue-500" />
                          ) : sale.paymentMethod === 'transfer' ? (
                            <RefreshCw className="w-4 h-4 text-purple-500" />
                          ) : (
                            <HelpCircle className="w-4 h-4 text-zinc-500" />
                          )}
                          <span className="text-xs font-bold text-zinc-400 uppercase">
                            {sale.paymentMethod}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="font-mono font-bold text-emerald-400 text-base">
                          ${sale.total.toFixed(2)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="p-2 -mr-2 text-zinc-600 hover:text-indigo-400 opacity-0 group-hover:opacity-100 transition-all rounded-lg hover:bg-indigo-500/10">
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="bg-zinc-950 border-t border-zinc-900 px-8 py-3 flex items-center justify-between shrink-0 text-sm">
          <span className="text-zinc-500">{message}</span>
          <span className="text-zinc-600 font-bold">{visibleRows.length} tickets encontrados</span>
        </div>
      </div>

      {/* Drawer Overlay */}
      {isDrawerOpen && (
        <div
          className="absolute inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity flex justify-end"
          onClick={() => setIsDrawerOpen(false)}
        >
          {/* Drawer Panel */}
          <div
            ref={drawerRef}
            className="w-[500px] bg-zinc-950 border-l border-zinc-800 h-full shadow-2xl flex flex-col transform transition-transform duration-300 translate-x-0 cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/30">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Receipt className="w-5 h-5 text-indigo-500" />
                Detalle del Ticket
              </h2>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {!selectedSale ? (
                <div className="flex flex-col items-center justify-center animate-pulse py-12">
                  <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  <p className="text-zinc-500 mt-4 font-medium text-sm">
                    Obteniendo recibo de los servidores...
                  </p>
                </div>
              ) : (
                <>
                  {/* Summary Card */}
                  <div className="bg-indigo-950/20 border border-indigo-900/30 rounded-2xl p-6 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl -mr-10 -mt-10"></div>
                    <div className="flex justify-between items-start mb-6 relative">
                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-indigo-400 font-bold mb-1">
                          Folio Oficial
                        </p>
                        <p className="text-2xl font-mono text-white tracking-tight">
                          {selectedSale.folio}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] uppercase tracking-widest text-indigo-400 font-bold mb-1">
                          Monto Total
                        </p>
                        <p className="text-2xl font-black font-mono text-emerald-400">
                          ${selectedSale.total.toFixed(2)}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm relative border-t border-indigo-900/30 pt-4 mt-2">
                      <div>
                        <p className="text-zinc-500 text-[10px] uppercase font-bold mb-1">
                          Cliente
                        </p>
                        <p className="text-zinc-200 font-medium truncate">
                          {selectedSale.customerName}
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-500 text-[10px] uppercase font-bold mb-1">
                          Método de Pago
                        </p>
                        <div className="flex items-center gap-1.5 text-zinc-200 font-medium capitalize">
                          {selectedSale.paymentMethod === 'cash' ? (
                            <Banknote className="w-3.5 h-3.5 text-emerald-500" />
                          ) : selectedSale.paymentMethod === 'card' ? (
                            <CreditCard className="w-3.5 h-3.5 text-blue-500" />
                          ) : selectedSale.paymentMethod === 'transfer' ? (
                            <RefreshCw className="w-3.5 h-3.5 text-purple-500" />
                          ) : (
                            <HelpCircle className="w-3.5 h-3.5 text-zinc-500" />
                          )}
                          {selectedSale.paymentMethod}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Raw API Detail */}
                  {detail && (
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-2">
                        <FileText className="w-4 h-4" /> Desglose Técnico
                      </h3>
                      <pre className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-[11px] font-mono text-zinc-400 overflow-x-auto shadow-inner">
                        {JSON.stringify(detail, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Events Timeline */}
                  {events.length > 0 && (
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-2">
                        <Clock className="w-4 h-4" /> Trazabilidad de Auditoría
                      </h3>
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-zinc-900/80">
                            <tr className="border-b border-zinc-800 text-zinc-500">
                              <th className="px-4 py-2 font-medium w-12">Nº</th>
                              <th className="px-4 py-2 font-medium">Evento</th>
                              <th className="px-4 py-2 font-medium text-right">Timestamp</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-800/50">
                            {events.map((ev, i) => (
                              <tr key={i} className="text-zinc-300 hover:bg-zinc-800/30">
                                <td className="px-4 py-2.5 font-mono text-zinc-500">
                                  {String(ev.sequence ?? i + 1)}
                                </td>
                                <td className="px-4 py-2.5">
                                  <span className="bg-zinc-800 px-2 py-0.5 rounded uppercase tracking-wider text-[10px] font-bold text-zinc-300">
                                    {String(ev.event_type ?? ev.type ?? '-')}
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 text-right font-mono text-zinc-500">
                                  {String(ev.timestamp ?? ev.created_at ?? '-').slice(11, 19)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Danger Actions Area */}
            {canManage && selectedSale && (
              <div className="p-6 border-t border-zinc-800 bg-zinc-950 flex flex-col gap-3 shrink-0">
                <div className="text-[10px] text-zinc-500 text-center uppercase font-bold tracking-widest mb-1 flex items-center justify-center gap-2">
                  <Ban className="w-3 h-3" /> Zona de Riesgo (Manager)
                </div>
                <button
                  onClick={() => void handleCancelSale()}
                  disabled={busy}
                  className="w-full py-3.5 bg-rose-500/10 border border-rose-500/30 text-rose-500 rounded-xl font-bold tracking-wider hover:bg-rose-500/20 hover:border-rose-500/50 transition-colors disabled:opacity-50 text-sm flex items-center justify-center gap-2"
                >
                  ANULAR ESTA VENTA COMPLETAMENTE
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
