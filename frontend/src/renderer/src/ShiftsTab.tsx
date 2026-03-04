import type { ReactElement } from 'react'
import { useEffect, useMemo, useState } from 'react'

import { useConfirm } from './components/ConfirmDialog'
import {
  Play,
  Square,
  RefreshCw,
  FileText,
  CheckCircle,
  Clock,
  User,
  List,
  Printer,
  AlertCircle,
  ArrowRightLeft,
  ShieldAlert
} from 'lucide-react'
import {
  loadRuntimeConfig,
  searchSales,
  openTurn,
  closeTurn,
  getTurnSummary,
  createCashMovement,
  getUserRole,
  printShiftReport
} from './posApi'
import {
  type ShiftRecord,
  CURRENT_SHIFT_KEY,
  SHIFT_HISTORY_KEY,
  readCurrentShift,
  saveCurrentShift,
  readShiftHistory,
  saveShiftHistory
} from './shiftTypes'

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

function toCsvCell(value: string): string {
  // Sanitize first: strip control chars, then prefix formula-triggering chars
  // eslint-disable-next-line no-control-regex
  const clean = value.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
  const safe = /^[=+\-@\t\r\n]/.test(clean) ? `\t${clean}` : clean
  return `"${safe.replace(/"/g, '""')}"`
}

function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const csv = [headers.join(','), ...rows.map((row) => row.map(toCsvCell).join(','))].join('\n')
  const blob = new Blob([`${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

function toMoney(value: number): string {
  return `$${value.toFixed(2)}`
}

export default function ShiftsTab(): ReactElement {
  const confirm = useConfirm()
  const [currentShift, setCurrentShift] = useState<ShiftRecord | null>(() => readCurrentShift())
  const [history, setHistory] = useState<ShiftRecord[]>(() => readShiftHistory())
  const [operator, setOperator] = useState('Cajero 1')
  const [openingCash, setOpeningCash] = useState('0')
  const [closingCash, setClosingCash] = useState('0')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Turnos (F5): apertura y cierre operativos.')
  const [selectedShiftId, setSelectedShiftId] = useState<string | null>(null)
  const [reconciliation, setReconciliation] = useState<ShiftReconciliation | null>(null)
  const [backendSummary, setBackendSummary] = useState<Record<string, unknown> | null>(null)
  const [cashMovType, setCashMovType] = useState<'in' | 'out' | 'expense'>('in')
  const [cashMovAmount, setCashMovAmount] = useState('')
  const [cashMovReason, setCashMovReason] = useState('')
  const [cashMovPin, setCashMovPin] = useState('')
  const role = getUserRole()
  const canManage = role === 'manager' || role === 'owner' || role === 'admin'
  const [expectedCash, setExpectedCash] = useState<number | null>(null)

  useEffect((): (() => void) => {
    const refresh = (): void => setCurrentShift(readCurrentShift())
    const onStorage = (event: StorageEvent): void => {
      if (event.key === CURRENT_SHIFT_KEY) refresh()
      if (event.key === SHIFT_HISTORY_KEY) setHistory(readShiftHistory())
    }
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  // Auto-fetch expected cash from backend when shift is open
  useEffect(() => {
    if (!currentShift?.backendTurnId) {
      setExpectedCash(null)
      return
    }
    let cancelled = false
    const cfg = loadRuntimeConfig()
    getTurnSummary(cfg, currentShift.backendTurnId)
      .then((raw) => {
        if (cancelled) return
        const data = (raw.data ?? raw) as Record<string, unknown>
        const exp = Number(data.expected_cash ?? 0)
        if (Number.isFinite(exp)) {
          setExpectedCash(Math.round(exp * 100) / 100)
          setClosingCash(exp.toFixed(2))
        }
      })
      .catch(() => {
        /* summary unavailable */
      })
    return () => {
      cancelled = true
    }
  }, [currentShift?.backendTurnId])

  const [durationTick, setDurationTick] = useState(0)

  useEffect(() => {
    if (!currentShift) return
    const timer = setInterval(() => setDurationTick((t) => t + 1), 60_000)
    return () => clearInterval(timer)
  }, [currentShift])

  const shiftDuration = useMemo(() => {
    if (!currentShift) return '-'
    const opened = new Date(currentShift.openedAt).getTime()
    const now = Date.now()
    const diffMin = Math.max(0, Math.floor((now - opened) / 60000))
    const hh = String(Math.floor(diffMin / 60)).padStart(2, '0')
    const mm = String(diffMin % 60).padStart(2, '0')
    return `${hh}:${mm}`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentShift, durationTick])

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
    const initialCash = Math.max(0, toNumber(openingCash))
    if (
      initialCash === 0 &&
      !(await confirm('El efectivo inicial es $0.00. ¿Abrir turno asi?', {
        variant: 'warning',
        title: 'Abrir turno'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const result = await openTurn(cfg, {
        initial_cash: initialCash,
        notes: notes.trim() || undefined
      })
      const data = result.data as Record<string, unknown>
      const backendId = Number(data?.id ?? data?.turn_id ?? 0)
      if (!backendId) {
        setMessage('Turno abierto pero sin ID de backend. Revisa la conexion.')
        setBusy(false)
        return
      }
      const shift: ShiftRecord = {
        id: `shift-${Date.now()}`,
        backendTurnId: backendId,
        terminalId: cfg.terminalId,
        openedAt: new Date().toISOString(),
        openedBy: operator.trim() || 'Sin nombre',
        openingCash: initialCash,
        status: 'open',
        salesCount: 0,
        totalSales: 0,
        cashSales: 0,
        cardSales: 0,
        transferSales: 0,
        notes: notes.trim()
      }
      setCurrentShift(shift)
      saveCurrentShift(shift)
      setMessage(`Turno abierto en backend (ID: ${backendId}): ${shift.openedBy}`)
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
    if (!currentShift.backendTurnId) {
      setMessage('Error: turno sin ID de backend. Abre un turno nuevo.')
      return
    }
    const closing = Math.max(0, toNumber(closingCash))
    if (
      !(await confirm(
        (closing === 0 ? 'El efectivo de cierre es $0.00. ' : '') +
          '¿Cerrar turno? Esta accion no se puede deshacer.',
        { variant: 'danger', title: 'Cerrar turno' }
      ))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const result = await closeTurn(cfg, currentShift.backendTurnId, {
        final_cash: closing,
        notes: notes.trim() || undefined
      })
      const data = result.data as Record<string, unknown>
      const expectedFromBackend = Number(data?.expected_cash ?? 0)
      const differenceFromBackend = Number(data?.difference ?? 0)
      const closed: ShiftRecord = {
        ...currentShift,
        status: 'closed',
        closedAt: new Date().toISOString(),
        closingCash: closing,
        expectedCash: expectedFromBackend,
        cashDifference: differenceFromBackend,
        notes: notes.trim()
      }
      const nextHistory = [closed, ...history]
      saveShiftHistory(nextHistory)
      setHistory(nextHistory)
      setCurrentShift(null)
      saveCurrentShift(null)
      setClosingCash('0')
      setNotes('')
      setSelectedShiftId(closed.id)
      setMessage(`Turno cerrado en backend. Diferencia: $${differenceFromBackend.toFixed(2)}`)
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
        if (terminal !== 0 && terminal !== shift.terminalId) return false
        const tsRaw = String(sale.timestamp ?? sale.created_at ?? sale._received_at ?? '').replace(
          /^(\d{4}-\d{2}-\d{2}) /,
          '$1T'
        )
        const tsMs = new Date(tsRaw).getTime()
        return Number.isFinite(tsMs) && tsMs >= openedMs && tsMs <= closedMs
      })

      // Accumulate in cents to avoid float drift over many sales
      const initial = { salesCount: 0, totalSales: 0, cashSales: 0, cardSales: 0, transferSales: 0 }
      const backendCents = scoped.reduce<typeof initial>((acc, sale) => {
        const status = String(sale.status ?? '')
        if (status === 'cancelled' || status === 'canceled') return acc
        const totalCents = Math.round(Math.max(0, Number(sale.total ?? 0)) * 100)
        const method = String(sale.payment_method ?? '')
        const mixedCashCents = Math.round(Math.max(0, Number(sale.mixed_cash ?? 0)) * 100)
        acc.salesCount += 1
        acc.totalSales += totalCents
        if (method === 'cash') acc.cashSales += totalCents
        else if (method === 'card') acc.cardSales += totalCents
        else if (method === 'transfer') acc.transferSales += totalCents
        else if (method === 'mixed') {
          acc.cashSales += mixedCashCents
          const mixedCardCents = Math.round(Math.max(0, Number(sale.mixed_card ?? 0)) * 100)
          const mixedTransferCents = Math.round(Math.max(0, Number(sale.mixed_transfer ?? 0)) * 100)
          acc.cardSales += mixedCardCents
          acc.transferSales += mixedTransferCents
        }
        return acc
      }, initial)
      const backend: BackendShiftTotals = {
        salesCount: backendCents.salesCount,
        totalSales: backendCents.totalSales / 100,
        cashSales: backendCents.cashSales / 100,
        cardSales: backendCents.cardSales / 100,
        transferSales: backendCents.transferSales / 100
      }

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
        ['diff_count_backend_vs_local', String(scopedReconciliation.diffCount)],
        ['diff_total_backend_vs_local', scopedReconciliation.diffTotal.toFixed(2)],
        ['diff_efectivo_backend_vs_local', scopedReconciliation.diffCash.toFixed(2)]
      )
    }
    downloadCsv(`corte_turno_${shift.id}.csv`, ['campo', 'valor'], rows)
    setMessage(`Corte de turno exportado: ${shift.id}`)
  }

  async function applySuggestedExpectedCash(): Promise<void> {
    if (!currentShift?.backendTurnId) {
      setMessage('No hay turno abierto para proponer cierre.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getTurnSummary(cfg, currentShift.backendTurnId)
      const data = (raw.data ?? raw) as Record<string, unknown>
      const exp = Number(data.expected_cash ?? 0)
      if (Number.isFinite(exp)) {
        setExpectedCash(Math.round(exp * 100) / 100)
        setClosingCash(exp.toFixed(2))
        setMessage(`Efectivo esperado: $${exp.toFixed(2)} (calculado por backend)`)
      }
    } catch {
      // Fallback to local calculation
      const scopedReconciliation =
        reconciliation && reconciliation.shiftId === currentShift.id ? reconciliation : null
      const base =
        currentShift.openingCash +
        (scopedReconciliation ? scopedReconciliation.cashSales : (currentShift.cashSales ?? 0))
      setClosingCash(base.toFixed(2))
      setMessage('Esperado ajustado con datos locales (backend no disponible).')
    } finally {
      setBusy(false)
    }
  }

  async function loadBackendSummary(): Promise<void> {
    const shift = selectedShift
    if (!shift?.backendTurnId) {
      setMessage('Sin ID de backend para este turno.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getTurnSummary(cfg, shift.backendTurnId)
      const data = (raw.data ?? raw) as Record<string, unknown>
      setBackendSummary(data)
      setMessage(`Resumen backend cargado para turno ${shift.backendTurnId}.`)
    } catch (err) {
      setMessage((err as Error).message)
      setBackendSummary(null)
    } finally {
      setBusy(false)
    }
  }

  async function handleCashMovement(): Promise<void> {
    if (!currentShift?.backendTurnId) return
    const amount = Math.max(0, toNumber(cashMovAmount))
    if (amount <= 0) {
      setMessage('Monto debe ser mayor a 0.')
      return
    }
    if (!cashMovReason.trim()) {
      setMessage('La razon del movimiento es obligatoria.')
      return
    }
    if (
      !(await confirm(`¿Registrar ${cashMovType} de $${amount.toFixed(2)}?`, {
        variant: 'warning',
        title: 'Movimiento de efectivo'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await createCashMovement(cfg, currentShift.backendTurnId, {
        movement_type: cashMovType,
        amount,
        reason: cashMovReason.trim(),
        manager_pin: cashMovPin.trim() || undefined
      })
      setMessage(`Movimiento ${cashMovType} de $${amount.toFixed(2)} registrado.`)
      setCashMovAmount('')
      setCashMovReason('')
      setCashMovPin('')
    } catch (err) {
      setMessage((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function printShiftCut(shift: ShiftRecord): Promise<void> {
    if (!shift.backendTurnId) {
      setMessage('Sin ID de backend — no se puede imprimir.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await printShiftReport(cfg, shift.backendTurnId)
      setMessage(`Corte de turno #${shift.backendTurnId} enviado a impresora.`)
    } catch {
      // Fallback: browser print dialog
      setMessage('Impresora no disponible — abriendo vista de impresion...')
      printShiftCutBrowser(shift)
    } finally {
      setBusy(false)
    }
  }

  function printShiftCutBrowser(shift: ShiftRecord): void {
    const esc = (s: string): string =>
      s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
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
          `<tr><td style="padding:6px 8px;border:1px solid #ddd;">${esc(String(label))}</td><td style="padding:6px 8px;border:1px solid #ddd;">${esc(String(value))}</td></tr>`
      )
      .join('')
    const html = `
      <html>
        <head>
          <title>Corte de turno ${esc(shift.id)}</title>
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
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const blobUrl = URL.createObjectURL(blob)
    const popup = window.open(blobUrl, '_blank', 'width=900,height=700')
    if (!popup) {
      URL.revokeObjectURL(blobUrl)
      setMessage('No se pudo abrir ventana de impresion. Verifica bloqueador de popups.')
      return
    }
    popup.onload = () => {
      popup.focus()
      popup.print()
    }
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60000)
  }

  return (
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-y-auto">
      <div className="max-w-7xl mx-auto w-full p-6 md:p-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black text-white flex items-center gap-3 tracking-tight">
              <Clock className="w-8 h-8 text-amber-500" />
              Gestión de Turnos
            </h1>
            <p className="text-zinc-500 mt-2 font-medium">
              Apertura, cuadre de caja y reconciliación de ventas.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {selectedShift && (
              <button
                onClick={() => void printShiftCut(selectedShift)}
                disabled={busy}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-zinc-300 font-bold hover:bg-zinc-800 transition-colors disabled:opacity-50"
              >
                <Printer className="w-4 h-4" /> Imprimir
              </button>
            )}
            {selectedShift && (
              <button
                onClick={() => exportShiftCutCsv(selectedShift)}
                disabled={busy}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-zinc-300 font-bold hover:bg-zinc-800 transition-colors disabled:opacity-50"
              >
                <FileText className="w-4 h-4" /> Exportar CSV
              </button>
            )}
          </div>
        </div>

        {message && message !== 'Turnos (F5): apertura y cierre operativos.' && (
          <div className="bg-blue-500/10 border border-blue-500/20 text-blue-400 px-4 py-3 rounded-xl flex items-center gap-3 text-sm font-semibold animate-fade-in-up">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p>{message}</p>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Left/Main Column: Active Shift & KPIs */}
          <div className="xl:col-span-2 space-y-8">
            {/* CURRENT SHIFT DASHBOARD */}
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500"></div>

              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${currentShift ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`}
                  ></div>
                  <h2 className="text-xl font-bold text-white">
                    {currentShift ? 'Turno en Curso' : 'Caja Cerrada'}
                  </h2>
                </div>
                {currentShift && (
                  <div className="bg-zinc-950 border border-zinc-800 px-4 py-1.5 rounded-full text-sm font-mono text-zinc-400 flex items-center gap-2 shadow-inner">
                    <User className="w-4 h-4 text-zinc-500" />
                    {currentShift.openedBy}
                  </div>
                )}
              </div>

              {currentShift ? (
                <div className="space-y-8">
                  {/* KPIs */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="bg-zinc-950 rounded-2xl p-4 border border-zinc-800/80">
                      <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                        Duración
                      </p>
                      <p className="text-2xl font-black text-white font-mono">{shiftDuration}</p>
                    </div>
                    <div className="bg-zinc-950 rounded-2xl p-4 border border-zinc-800/80">
                      <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                        Ventas
                      </p>
                      <p className="text-2xl font-black text-white font-mono">
                        {currentShift.salesCount ?? 0}
                      </p>
                    </div>
                    <div className="bg-zinc-950 rounded-2xl p-4 border border-zinc-800/80">
                      <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                        Efectivo Acum.
                      </p>
                      <p className="text-2xl font-black text-emerald-400 font-mono">
                        ${(currentShift.cashSales ?? 0).toFixed(2)}
                      </p>
                    </div>
                    <div className="bg-zinc-950 rounded-2xl p-4 border border-zinc-800/80">
                      <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                        Total Turno
                      </p>
                      <p className="text-2xl font-black text-blue-400 font-mono">
                        ${(currentShift.totalSales ?? 0).toFixed(2)}
                      </p>
                    </div>
                  </div>

                  {/* Cash Movement & Close */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 bg-zinc-950/50 p-5 rounded-2xl border border-zinc-800/50">
                    {/* Left: Close Shift Form */}
                    <div className="space-y-4">
                      <h3 className="text-sm font-bold text-rose-400 uppercase tracking-widest flex items-center gap-2">
                        <Square className="w-4 h-4" /> Cierre de Turno
                      </h3>
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-bold text-zinc-500 mb-1">
                            EFECTIVO EN CAJA (CONTEO)
                          </label>
                          <div className="relative">
                            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 font-bold">
                              $
                            </span>
                            <input
                              type="number"
                              min={0}
                              value={closingCash}
                              onChange={(e) => setClosingCash(e.target.value)}
                              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-8 pr-4 text-sm font-bold text-white focus:border-rose-500 focus:outline-none transition-colors"
                            />
                          </div>
                          {expectedCash !== null && (
                            <p className="text-xs text-emerald-400/70 mt-1">
                              Esperado por sistema:{' '}
                              <span className="font-mono font-bold">
                                ${expectedCash.toFixed(2)}
                              </span>
                            </p>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => void applySuggestedExpectedCash()}
                            disabled={busy}
                            className="flex-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 py-2 rounded-xl text-xs font-bold text-zinc-400 transition-colors"
                          >
                            Recalcular
                          </button>
                          <button
                            onClick={() => void closeShift()}
                            disabled={busy}
                            className="flex-[2] bg-rose-600 hover:bg-rose-500 text-white py-2 rounded-xl font-bold shadow-[0_0_15px_rgba(225,29,72,0.3)] transition-all"
                          >
                            CERRAR CAJA
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Right: Cash Movements */}
                    <div className="space-y-4 border-t lg:border-t-0 lg:border-l border-zinc-800/50 pt-5 lg:pt-0 lg:pl-6">
                      <h3 className="text-sm font-bold text-blue-400 uppercase tracking-widest flex items-center gap-2">
                        <ArrowRightLeft className="w-4 h-4" /> Mov. Efectivo
                      </h3>
                      <div className="grid grid-cols-2 gap-2">
                        <select
                          className="bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs font-bold focus:border-blue-500 focus:outline-none"
                          value={cashMovType}
                          onChange={(e) =>
                            setCashMovType(e.target.value as 'in' | 'out' | 'expense')
                          }
                        >
                          <option value="in">Entrada (+)</option>
                          <option value="out">Retiro (-)</option>
                          <option value="expense">Gasto (-)</option>
                        </select>
                        <input
                          type="number"
                          min={0}
                          placeholder="Monto"
                          value={cashMovAmount}
                          onChange={(e) => setCashMovAmount(e.target.value)}
                          className="bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs font-bold focus:border-blue-500 focus:outline-none"
                        />
                      </div>
                      <input
                        placeholder="Concepto (Ej. Pago proveedor)"
                        value={cashMovReason}
                        onChange={(e) => setCashMovReason(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs font-medium focus:border-blue-500 focus:outline-none"
                      />
                      {!canManage && (
                        <div className="relative">
                          <ShieldAlert className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-amber-500" />
                          <input
                            type="password"
                            placeholder="PIN de Manager"
                            value={cashMovPin}
                            onChange={(e) => setCashMovPin(e.target.value)}
                            className="w-full bg-amber-500/10 border border-amber-500/30 rounded-xl py-2 pl-9 pr-3 text-xs font-medium text-amber-100 focus:border-amber-500 focus:outline-none"
                          />
                        </div>
                      )}
                      <button
                        onClick={() => void handleCashMovement()}
                        disabled={busy || !cashMovAmount || !cashMovReason.trim()}
                        className="w-full bg-zinc-800 hover:bg-zinc-700 text-white py-2.5 rounded-xl text-xs font-bold transition-all disabled:opacity-50 border border-zinc-700"
                      >
                        REGISTRAR MOVIMIENTO
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* OPEN SHIFT FORM */
                <div className="max-w-md space-y-5">
                  <div>
                    <label className="block text-xs font-bold text-zinc-500 mb-2 uppercase tracking-wider">
                      Nombre del Operador
                    </label>
                    <input
                      value={operator}
                      onChange={(e) => setOperator(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-3 px-4 text-sm font-bold text-white focus:border-emerald-500 focus:outline-none transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-zinc-500 mb-2 uppercase tracking-wider">
                      Fondo Inicial de Caja
                    </label>
                    <div className="relative">
                      <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 font-bold">
                        $
                      </span>
                      <input
                        type="number"
                        min={0}
                        value={openingCash}
                        onChange={(e) => setOpeningCash(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-3 pl-8 pr-4 text-sm font-bold text-white focus:border-emerald-500 focus:outline-none transition-colors"
                      />
                    </div>
                    <p className="text-xs text-zinc-600 mt-2">
                      Monedas y billetes para cambio base al iniciar el día.
                    </p>
                  </div>
                  <button
                    onClick={() => void openShift()}
                    disabled={busy || !operator.trim()}
                    className="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-black tracking-widest shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-all active:scale-[0.98] mt-4 flex items-center justify-center gap-2"
                  >
                    <Play className="w-5 h-5 fill-current" /> INICIAR TURNO
                  </button>
                </div>
              )}
            </div>

            {/* RECONCILIATION & SYNC PANEL */}
            <div className="bg-zinc-900/20 border border-zinc-800/40 rounded-3xl p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" /> Conciliación Backend
                </h3>
                <select
                  className="bg-zinc-950 border border-zinc-800 rounded-xl py-2 px-4 text-xs font-bold text-zinc-300 focus:outline-none focus:border-blue-500"
                  value={selectedShiftId ?? ''}
                  onChange={(e) => setSelectedShiftId(e.target.value || null)}
                >
                  <option value="">Turno Actual / Activo</option>
                  {history.slice(0, 5).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.openedAt.slice(0, 10)} - {s.openedBy}{' '}
                      {s.status === 'open' ? '(Abierto)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col sm:flex-row gap-4 mb-6">
                <button
                  onClick={() => selectedShift && void reconcileShift(selectedShift)}
                  disabled={busy || !selectedShift}
                  className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 py-3 rounded-xl text-sm font-bold transition-colors flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Calcular
                  Diferencias Reales
                </button>
                <button
                  onClick={() => void loadBackendSummary()}
                  disabled={busy || !selectedShift?.backendTurnId}
                  className="flex-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 py-3 rounded-xl text-sm font-bold transition-colors flex items-center justify-center gap-2"
                >
                  Ver Resumen Bruto API
                </button>
              </div>

              {selectedShiftReconciliation && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-in-up">
                  <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4">
                    <p className="text-[10px] uppercase text-zinc-500 font-bold mb-1">
                      Ventas Reales Backend
                    </p>
                    <p className="text-xl font-mono text-white">
                      {selectedShiftReconciliation.salesCount}
                    </p>
                  </div>
                  <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4">
                    <p className="text-[10px] uppercase text-zinc-500 font-bold mb-1">
                      Diff. Efectivo (API vs Caja)
                    </p>
                    <p
                      className={`text-xl font-mono font-bold ${Math.abs(selectedShiftReconciliation.diffCash) > 0.1 ? 'text-amber-400' : 'text-emerald-400'}`}
                    >
                      ${selectedShiftReconciliation.diffCash.toFixed(2)}
                    </p>
                  </div>
                  <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4">
                    <p className="text-[10px] uppercase text-zinc-500 font-bold mb-1">
                      Diff. Total (Sobrante/Faltante)
                    </p>
                    <p
                      className={`text-xl font-mono font-bold ${Math.abs(selectedShiftReconciliation.diffTotal) > 0.1 ? 'text-amber-400' : 'text-emerald-400'}`}
                    >
                      ${selectedShiftReconciliation.diffTotal.toFixed(2)}
                    </p>
                  </div>
                </div>
              )}
              {backendSummary && (
                <pre className="mt-4 p-4 bg-zinc-950 border border-zinc-800 rounded-xl text-xs font-mono text-zinc-400 max-h-40 overflow-y-auto w-full">
                  {JSON.stringify(backendSummary, null, 2)}
                </pre>
              )}
            </div>
          </div>

          {/* Right Column: Mini History & Ledger */}
          <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-3xl flex flex-col overflow-hidden h-full max-h-[800px]">
            <div className="p-5 border-b border-zinc-800/80 bg-zinc-900/50">
              <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest flex items-center gap-2">
                <List className="w-4 h-4" /> Historial Reciente
              </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {history.length === 0 ? (
                <div className="text-center p-8 opacity-30">
                  <Clock className="w-12 h-12 mx-auto mb-3" />
                  <p className="text-sm">Sin registros.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {history.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => setSelectedShiftId(s.id)}
                      className={`p-4 rounded-xl cursor-pointer transition-all border ${selectedShiftId === s.id ? 'bg-zinc-800/80 border-zinc-700 shadow-md scale-[1.02]' : 'bg-transparent border-transparent hover:bg-zinc-800/40'}`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-bold text-sm text-zinc-200">{s.openedBy}</div>
                        <div
                          className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded ${s.status === 'open' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-zinc-800 text-zinc-500 border border-zinc-700'}`}
                        >
                          {s.status === 'open' ? 'EN CURSO' : 'CERRADO'}
                        </div>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-zinc-500 font-mono">
                          {s.openedAt.slice(5, 16).replace('T', ' ')}
                        </span>
                        <span className="font-mono text-white">
                          ${(s.totalSales ?? 0).toFixed(2)}
                        </span>
                      </div>
                      {s.status === 'closed' && (
                        <div className="mt-3 text-[10px] bg-zinc-950 rounded border border-zinc-800/80 flex items-center divide-x divide-zinc-800">
                          <div className="flex-1 px-2 py-1 text-zinc-400">
                            Diff:{' '}
                            <span
                              className={`font-mono ${(s.cashDifference ?? 0) < -0.1 ? 'text-rose-400' : 'text-emerald-400'}`}
                            >
                              ${(s.cashDifference ?? 0).toFixed(2)}
                            </span>
                          </div>
                          <div className="flex-1 px-2 py-1 text-zinc-400 overflow-hidden text-right">
                            Esp:{' '}
                            <span className="font-mono">${(s.expectedCash ?? 0).toFixed(2)}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
