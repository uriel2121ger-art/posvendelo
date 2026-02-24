import type { ReactElement } from 'react'
import { useEffect, useMemo, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, searchSales, syncTable } from './posApi'

type ShiftRecord = {
  id: string
  terminalId: number
  openedAt: string
  openedBy: string
  openingCash: number
  status: 'open' | 'closed'
  salesCount?: number
  totalSales?: number
  cashSales?: number
  cardSales?: number
  transferSales?: number
  lastSaleAt?: string
  closedAt?: string
  closingCash?: number
  expectedCash?: number
  cashDifference?: number
  notes?: string
}

const CURRENT_SHIFT_KEY = 'titan.currentShift'
const SHIFT_HISTORY_KEY = 'titan.shiftHistory'

type ShiftReconciliation = {
  shiftId: string
  salesCount: number
  totalSales: number
  cashSales: number
  cardSales: number
  transferSales: number
  diffCount: number
  diffTotal: number
  diffCash: number
  reconciledAt: string
}

type BackendShiftTotals = {
  salesCount: number
  totalSales: number
  cashSales: number
  cardSales: number
  transferSales: number
}

function toNumber(value: string): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function readCurrentShift(): ShiftRecord | null {
  const raw = localStorage.getItem(CURRENT_SHIFT_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as ShiftRecord
    return parsed?.status === 'open' ? parsed : null
  } catch {
    return null
  }
}

function readHistory(): ShiftRecord[] {
  const raw = localStorage.getItem(SHIFT_HISTORY_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as ShiftRecord[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveCurrentShift(shift: ShiftRecord | null): void {
  if (!shift) {
    localStorage.removeItem(CURRENT_SHIFT_KEY)
    return
  }
  localStorage.setItem(CURRENT_SHIFT_KEY, JSON.stringify(shift))
}

function saveHistory(history: ShiftRecord[]): void {
  localStorage.setItem(SHIFT_HISTORY_KEY, JSON.stringify(history.slice(0, 100)))
}

function toCsvCell(value: string): string {
  const safe = value.replace(/"/g, '""')
  return `"${safe}"`
}

function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const csv = [headers.join(','), ...rows.map((row) => row.map(toCsvCell).join(','))].join('\n')
  const blob = new Blob([`${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function toMoney(value: number): string {
  return `$${value.toFixed(2)}`
}

export default function ShiftsTab(): ReactElement {
  const [currentShift, setCurrentShift] = useState<ShiftRecord | null>(() => readCurrentShift())
  const [history, setHistory] = useState<ShiftRecord[]>(() => readHistory())
  const [operator, setOperator] = useState('Cajero 1')
  const [openingCash, setOpeningCash] = useState('0')
  const [closingCash, setClosingCash] = useState('0')
  const [expectedCash, setExpectedCash] = useState('0')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Turnos (F5): apertura y cierre operativos.')
  const [selectedShiftId, setSelectedShiftId] = useState<string | null>(null)
  const [reconciliation, setReconciliation] = useState<ShiftReconciliation | null>(null)

  useEffect((): (() => void) => {
    const refresh = (): void => setCurrentShift(readCurrentShift())
    const onStorage = (event: StorageEvent): void => {
      if (event.key === CURRENT_SHIFT_KEY) refresh()
      if (event.key === SHIFT_HISTORY_KEY) setHistory(readHistory())
    }
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  const shiftDuration = useMemo(() => {
    if (!currentShift) return '-'
    const opened = new Date(currentShift.openedAt).getTime()
    const now = Date.now()
    const diffMin = Math.max(0, Math.floor((now - opened) / 60000))
    const hh = String(Math.floor(diffMin / 60)).padStart(2, '0')
    const mm = String(diffMin % 60).padStart(2, '0')
    return `${hh}:${mm}`
  }, [currentShift])

  const selectedShift = useMemo(() => {
    if (selectedShiftId) {
      return history.find((item) => item.id === selectedShiftId) ?? null
    }
    return currentShift
  }, [currentShift, history, selectedShiftId])

  const selectedShiftReconciliation = useMemo(() => {
    if (!selectedShift || !reconciliation) return null
    return reconciliation.shiftId === selectedShift.id ? reconciliation : null
  }, [reconciliation, selectedShift])

  async function openShift(): Promise<void> {
    if (currentShift) {
      setMessage('Ya existe un turno abierto.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const shift: ShiftRecord = {
        id: `shift-${Date.now()}`,
        terminalId: cfg.terminalId,
        openedAt: new Date().toISOString(),
        openedBy: operator.trim() || 'Sin nombre',
        openingCash: Math.max(0, toNumber(openingCash)),
        status: 'open',
        salesCount: 0,
        totalSales: 0,
        cashSales: 0,
        cardSales: 0,
        transferSales: 0,
        notes: notes.trim()
      }
      await syncTable('shifts', [shift], cfg)
      setCurrentShift(shift)
      saveCurrentShift(shift)
      setMessage(`Turno abierto: ${shift.openedBy}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function closeShift(): Promise<void> {
    if (!currentShift) {
      setMessage('No hay turno abierto.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const closing = Math.max(0, toNumber(closingCash))
      const expectedBase =
        expectedCash.trim().length > 0
          ? Math.max(0, toNumber(expectedCash))
          : currentShift.openingCash + (currentShift.cashSales ?? 0)
      const expected = expectedBase
      const closed: ShiftRecord = {
        ...currentShift,
        status: 'closed',
        closedAt: new Date().toISOString(),
        closingCash: closing,
        expectedCash: expected,
        cashDifference: closing - expected,
        notes: notes.trim()
      }
      await syncTable('shifts', [closed], cfg)
      const nextHistory = [closed, ...history]
      setHistory(nextHistory)
      saveHistory(nextHistory)
      setCurrentShift(null)
      saveCurrentShift(null)
      setClosingCash('0')
      setExpectedCash('0')
      setNotes('')
      setSelectedShiftId(closed.id)
      setMessage(`Turno cerrado. Diferencia: $${(closed.cashDifference ?? 0).toFixed(2)}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function reconcileShift(shift: ShiftRecord): Promise<void> {
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const dateFrom = shift.openedAt.slice(0, 10)
      const dateTo = (shift.closedAt ?? new Date().toISOString()).slice(0, 10)
      const backendSales = await searchSales(cfg, { dateFrom, dateTo, limit: 2000 })
      const openedMs = new Date(shift.openedAt).getTime()
      const closedMs = new Date(shift.closedAt ?? new Date().toISOString()).getTime()
      const scoped = backendSales.filter((sale) => {
        const terminal = Number(sale.terminal_id ?? sale._terminal_id ?? 0)
        if (terminal !== shift.terminalId) return false
        const tsRaw = String(sale.timestamp ?? sale.created_at ?? sale._received_at ?? '')
        const tsMs = new Date(tsRaw).getTime()
        return Number.isFinite(tsMs) && tsMs >= openedMs && tsMs <= closedMs
      })

      const backend = scoped.reduce<BackendShiftTotals>(
        (acc, sale) => {
          const total = Math.max(0, Number(sale.total ?? 0))
          const method = String(sale.payment_method ?? '')
          acc.salesCount += 1
          acc.totalSales += total
          if (method === 'cash') acc.cashSales += total
          else if (method === 'card') acc.cardSales += total
          else if (method === 'transfer') acc.transferSales += total
          return acc
        },
        { salesCount: 0, totalSales: 0, cashSales: 0, cardSales: 0, transferSales: 0 }
      )

      const localSalesCount = shift.salesCount ?? 0
      const localTotal = shift.totalSales ?? 0
      const localCash = shift.cashSales ?? 0

      const result: ShiftReconciliation = {
        shiftId: shift.id,
        salesCount: backend.salesCount,
        totalSales: backend.totalSales,
        cashSales: backend.cashSales,
        cardSales: backend.cardSales,
        transferSales: backend.transferSales,
        diffCount: backend.salesCount - localSalesCount,
        diffTotal: backend.totalSales - localTotal,
        diffCash: backend.cashSales - localCash,
        reconciledAt: new Date().toISOString()
      }
      setReconciliation(result)
      setMessage(`Conciliacion completada para turno ${shift.id}.`)
    } catch (error) {
      setMessage((error as Error).message)
      setReconciliation(null)
    } finally {
      setBusy(false)
    }
  }

  function exportShiftCutCsv(shift: ShiftRecord): void {
    const scopedReconciliation =
      reconciliation && reconciliation.shiftId === shift.id ? reconciliation : null
    const rows = [
      ['turno_id', shift.id],
      ['terminal_id', String(shift.terminalId)],
      ['abierto_en', shift.openedAt],
      ['cerrado_en', shift.closedAt ?? ''],
      ['operador', shift.openedBy],
      ['efectivo_inicial', (shift.openingCash ?? 0).toFixed(2)],
      ['ventas_local_count', String(shift.salesCount ?? 0)],
      ['ventas_local_total', (shift.totalSales ?? 0).toFixed(2)],
      ['ventas_local_efectivo', (shift.cashSales ?? 0).toFixed(2)],
      ['ventas_local_tarjeta', (shift.cardSales ?? 0).toFixed(2)],
      ['ventas_local_transferencia', (shift.transferSales ?? 0).toFixed(2)],
      ['efectivo_cierre', (shift.closingCash ?? 0).toFixed(2)],
      ['efectivo_esperado', (shift.expectedCash ?? 0).toFixed(2)],
      ['diferencia_caja', (shift.cashDifference ?? 0).toFixed(2)]
    ]
    if (scopedReconciliation) {
      rows.push(
        ['backend_reconciled_at', scopedReconciliation.reconciledAt],
        ['backend_count', String(scopedReconciliation.salesCount)],
        ['backend_total', scopedReconciliation.totalSales.toFixed(2)],
        ['backend_efectivo', scopedReconciliation.cashSales.toFixed(2)],
        ['diff_count_backend_vs_local', scopedReconciliation.diffCount.toFixed(2)],
        ['diff_total_backend_vs_local', scopedReconciliation.diffTotal.toFixed(2)],
        ['diff_efectivo_backend_vs_local', scopedReconciliation.diffCash.toFixed(2)]
      )
    }
    downloadCsv(`corte_turno_${shift.id}.csv`, ['campo', 'valor'], rows)
    setMessage(`Corte de turno exportado: ${shift.id}`)
  }

  function applySuggestedExpectedCash(): void {
    if (!currentShift) {
      setMessage('No hay turno abierto para proponer cierre.')
      return
    }
    const scopedReconciliation =
      reconciliation && reconciliation.shiftId === currentShift.id ? reconciliation : null
    const base =
      currentShift.openingCash +
      (scopedReconciliation ? scopedReconciliation.cashSales : (currentShift.cashSales ?? 0))
    setExpectedCash(base.toFixed(2))
    setMessage(
      scopedReconciliation
        ? 'Esperado ajustado con efectivo conciliado de backend.'
        : 'Esperado ajustado con efectivo local del turno.'
    )
  }

  function printShiftCut(shift: ShiftRecord): void {
    const scopedReconciliation =
      reconciliation && reconciliation.shiftId === shift.id ? reconciliation : null
    const backendCash = scopedReconciliation?.cashSales ?? 0
    const backendTotal = scopedReconciliation?.totalSales ?? 0
    const expectedByBackend = shift.openingCash + backendCash
    const expectedByLocal = shift.openingCash + (shift.cashSales ?? 0)
    const detail = [
      ['Turno', shift.id],
      ['Terminal', String(shift.terminalId)],
      ['Operador', shift.openedBy],
      ['Apertura', shift.openedAt],
      ['Cierre', shift.closedAt ?? '-'],
      ['Efectivo inicial', toMoney(shift.openingCash)],
      ['Ventas locales', String(shift.salesCount ?? 0)],
      ['Total local', toMoney(shift.totalSales ?? 0)],
      ['Efectivo local', toMoney(shift.cashSales ?? 0)],
      ['Efectivo backend', scopedReconciliation ? toMoney(backendCash) : '-'],
      ['Total backend', scopedReconciliation ? toMoney(backendTotal) : '-'],
      ['Esperado local', toMoney(expectedByLocal)],
      ['Esperado backend', scopedReconciliation ? toMoney(expectedByBackend) : '-'],
      ['Cierre capturado', toMoney(shift.closingCash ?? 0)],
      ['Diferencia caja', toMoney(shift.cashDifference ?? 0)],
      ['Diff backend vs local', scopedReconciliation ? toMoney(scopedReconciliation.diffCash) : '-']
    ]
    const rowsHtml = detail
      .map(
        ([label, value]) =>
          `<tr><td style="padding:6px 8px;border:1px solid #ddd;">${label}</td><td style="padding:6px 8px;border:1px solid #ddd;">${value}</td></tr>`
      )
      .join('')
    const html = `
      <html>
        <head>
          <title>Corte de turno ${shift.id}</title>
        </head>
        <body style="font-family: Arial, sans-serif; padding: 16px;">
          <h2 style="margin: 0 0 12px 0;">TITAN POS - Corte de Turno</h2>
          <table style="border-collapse: collapse; width: 100%; max-width: 700px;">
            <tbody>${rowsHtml}</tbody>
          </table>
          <p style="margin-top: 16px; color: #666;">Generado: ${new Date().toISOString()}</p>
        </body>
      </html>
    `
    const popup = window.open('', '_blank', 'width=900,height=700')
    if (!popup) {
      setMessage('No se pudo abrir ventana de impresion. Verifica bloqueador de popups.')
      return
    }
    popup.document.open()
    popup.document.write(html)
    popup.document.close()
    popup.focus()
    popup.print()
    setMessage(`Reporte imprimible preparado para turno ${shift.id}.`)
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />
      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_200px_200px_200px]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Operador"
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
          disabled={Boolean(currentShift)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={0}
          placeholder="Efectivo inicial"
          value={openingCash}
          onChange={(e) => setOpeningCash(e.target.value)}
          disabled={Boolean(currentShift)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={0}
          placeholder="Efectivo cierre"
          value={closingCash}
          onChange={(e) => setClosingCash(e.target.value)}
          disabled={!currentShift}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={0}
          placeholder="Efectivo esperado"
          value={expectedCash}
          onChange={(e) => setExpectedCash(e.target.value)}
          disabled={!currentShift}
        />
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Notas de turno"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void openShift()}
          disabled={busy || Boolean(currentShift)}
        >
          Abrir turno
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void closeShift()}
          disabled={busy || !currentShift}
        >
          Cerrar turno
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_auto_auto_auto]">
        <select
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={selectedShiftId ?? ''}
          onChange={(e) => setSelectedShiftId(e.target.value || null)}
        >
          <option value="">Turno activo</option>
          {history.map((shift) => (
            <option key={shift.id} value={shift.id}>
              {shift.id} - {shift.openedBy}
            </option>
          ))}
        </select>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={() => selectedShift && void reconcileShift(selectedShift)}
          disabled={busy || !selectedShift}
        >
          Conciliar con backend
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => selectedShift && exportShiftCutCsv(selectedShift)}
          disabled={busy || !selectedShift}
        >
          Exportar corte CSV
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={() => selectedShift && printShiftCut(selectedShift)}
          disabled={busy || !selectedShift}
        >
          Imprimir corte
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_auto]">
        <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300">
          Sugerencia de esperado: usa conciliacion backend si existe; si no, acumulado local.
        </div>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={applySuggestedExpectedCash}
          disabled={!currentShift || busy}
        >
          Aplicar esperado sugerido
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-3">
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Estado</p>
          <p className="mt-1 font-semibold">{currentShift ? 'Abierto' : 'Sin turno activo'}</p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Operador actual</p>
          <p className="mt-1 font-semibold">{currentShift?.openedBy ?? '-'}</p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Duracion turno</p>
          <p className="mt-1 font-semibold">{shiftDuration}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-4">
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Ventas turno</p>
          <p className="mt-1 font-semibold">{currentShift?.salesCount ?? 0}</p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Total turno</p>
          <p className="mt-1 font-semibold">${(currentShift?.totalSales ?? 0).toFixed(2)}</p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Efectivo acumulado</p>
          <p className="mt-1 font-semibold">${(currentShift?.cashSales ?? 0).toFixed(2)}</p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Esperado sugerido cierre</p>
          <p className="mt-1 font-semibold">
            ${((currentShift?.openingCash ?? 0) + (currentShift?.cashSales ?? 0)).toFixed(2)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-3">
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Conciliacion backend: ventas</p>
          <p className="mt-1 font-semibold">
            {selectedShiftReconciliation ? selectedShiftReconciliation.salesCount : '-'}
          </p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Diferencia total backend vs local</p>
          <p
            className={`mt-1 font-semibold ${
              selectedShiftReconciliation && Math.abs(selectedShiftReconciliation.diffTotal) > 0.009
                ? 'text-amber-300'
                : 'text-emerald-300'
            }`}
          >
            {selectedShiftReconciliation
              ? `$${selectedShiftReconciliation.diffTotal.toFixed(2)}`
              : '-'}
          </p>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <p className="text-zinc-400">Diferencia efectivo backend vs local</p>
          <p
            className={`mt-1 font-semibold ${
              selectedShiftReconciliation && Math.abs(selectedShiftReconciliation.diffCash) > 0.009
                ? 'text-amber-300'
                : 'text-emerald-300'
            }`}
          >
            {selectedShiftReconciliation
              ? `$${selectedShiftReconciliation.diffCash.toFixed(2)}`
              : '-'}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <h3 className="mb-3 font-semibold">Historial de turnos</h3>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm">
              <th className="py-4 px-6">Apertura</th>
              <th className="py-4 px-6">Cierre</th>
              <th className="py-4 px-6">Operador</th>
              <th className="py-4 px-6">Inicial</th>
              <th className="py-4 px-6">Ventas</th>
              <th className="py-4 px-6">Total</th>
              <th className="py-4 px-6">Efectivo</th>
              <th className="py-4 px-6">Cierre</th>
              <th className="py-4 px-6">Esperado</th>
              <th className="py-4 px-6">Diferencia</th>
            </tr>
          </thead>
          <tbody>
            {history.map((shift) => (
              <tr key={shift.id} className="border-b border-zinc-900">
                <td className="py-4 px-6 font-medium">
                  {shift.openedAt.slice(0, 19).replace('T', ' ')}
                </td>
                <td className="py-4 px-6 font-medium">
                  {shift.closedAt?.slice(0, 19).replace('T', ' ') ?? '-'}
                </td>
                <td className="py-4 px-6 font-medium">{shift.openedBy}</td>
                <td className="py-4 px-6 font-medium">${shift.openingCash.toFixed(2)}</td>
                <td className="py-4 px-6 font-medium">{shift.salesCount ?? 0}</td>
                <td className="py-4 px-6 font-medium">${(shift.totalSales ?? 0).toFixed(2)}</td>
                <td className="py-4 px-6 font-medium">${(shift.cashSales ?? 0).toFixed(2)}</td>
                <td className="py-4 px-6 font-medium">${(shift.closingCash ?? 0).toFixed(2)}</td>
                <td className="py-4 px-6 font-medium">${(shift.expectedCash ?? 0).toFixed(2)}</td>
                <td
                  className={`py-2 font-semibold ${
                    (shift.cashDifference ?? 0) < 0 ? 'text-red-300' : 'text-emerald-300'
                  }`}
                >
                  ${(shift.cashDifference ?? 0).toFixed(2)}
                </td>
              </tr>
            ))}
            {history.length === 0 && (
              <tr>
                <td className="py-2 text-zinc-400" colSpan={10}>
                  Sin turnos cerrados aun.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
