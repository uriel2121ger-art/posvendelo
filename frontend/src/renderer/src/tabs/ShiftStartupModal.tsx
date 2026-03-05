import type { ReactElement, FormEvent } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  type RuntimeConfig,
  loadRuntimeConfig,
  openTurn,
  closeTurn,
  getTurnSummary,
  getCurrentTurn,
  printShiftReport
} from '../posApi'
import {
  type ShiftRecord,
  readCurrentShift,
  saveCurrentShift,
  readShiftHistory,
  saveShiftHistory
} from '../types/shiftTypes'
import { useFocusTrap } from '../hooks/useFocusTrap'
import { Printer, Check } from 'lucide-react'

type Phase =
  | 'checking'
  | 'no_shift'
  | 'existing_shift'
  | 'closing_shift'
  | 'cut_summary'
  | 'opening_shift'

type CutData = {
  expected: number
  counted: number
  difference: number
}

export default function ShiftStartupModal({
  onComplete,
  onExit
}: {
  onComplete: () => void
  onExit: () => void
}): ReactElement | null {
  const [phase, setPhase] = useState<Phase>('checking')
  const [existingShift, setExistingShift] = useState<ShiftRecord | null>(null)
  const [initialCash, setInitialCash] = useState('')
  const [closingCash, setClosingCash] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cut, setCut] = useState<CutData | null>(null)
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null)
  const [printStatus, setPrintStatus] = useState<'idle' | 'printing' | 'ok' | 'error'>('idle')
  const [printMessage, setPrintMessage] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const modalRef = useRef<HTMLFormElement | HTMLDivElement>(null)

  useFocusTrap(modalRef as React.RefObject<HTMLElement | null>, phase !== 'checking')

  const operator = (() => {
    try {
      return localStorage.getItem('titan.user') ?? 'admin'
    } catch {
      return 'admin'
    }
  })()

  // Block F-keys while modal is open (capture phase)
  useEffect(() => {
    const block = (e: KeyboardEvent): void => {
      if (/^F\d{1,2}$/.test(e.key)) {
        e.preventDefault()
        e.stopPropagation()
        e.stopImmediatePropagation()
      }
    }
    window.addEventListener('keydown', block, true)
    return () => window.removeEventListener('keydown', block, true)
  }, [])

  // Check shift on mount — sync with backend if localStorage is empty
  useEffect(() => {
    const localShift = readCurrentShift()
    if (localShift) {
      setExistingShift(localShift)
      setPhase('existing_shift')
      return
    }
    // localStorage empty — ask backend for active turn (disaster recovery)
    const cfg = loadRuntimeConfig()
    getCurrentTurn(cfg)
      .then((result) => {
        const turn = (result?.data ?? result) as Record<string, unknown> | null
        if (turn && turn.id && turn.status === 'open') {
          const recovered: ShiftRecord = {
            id: `shift-recovered-${turn.id}`,
            backendTurnId: Number(turn.id),
            terminalId: Number(turn.terminal_id ?? turn.branch_id ?? cfg.terminalId),
            openedAt: String(turn.start_timestamp ?? new Date().toISOString()),
            openedBy: operator,
            openingCash: Number(turn.initial_cash ?? 0),
            status: 'open',
            salesCount: 0,
            totalSales: 0
          }
          saveCurrentShift(recovered)
          setExistingShift(recovered)
          setPhase('existing_shift')
          // Actualizar ventas/total en segundo plano (no bloquear la pantalla)
          getTurnSummary(cfg, Number(turn.id))
            .then((raw) => {
              const summary = (raw.data ?? raw) as Record<string, unknown>
              const updated: ShiftRecord = {
                ...recovered,
                salesCount: Number(summary.sales_count ?? 0),
                totalSales: Math.round(Number(summary.total_sales ?? 0) * 100) / 100
              }
              saveCurrentShift(updated)
              setExistingShift(updated)
            })
            .catch(() => {
              /* resumen opcional */
            })
          return
        } else {
          setPhase('no_shift')
        }
      })
      .catch(() => {
        setPhase('no_shift')
      })
  }, [operator])

  // Auto-focus input when phase changes
  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 80)
    return () => clearTimeout(t)
  }, [phase])

  const doOpenTurn = useCallback(
    async (cash: number): Promise<void> => {
      setBusy(true)
      setError('')
      try {
        const cfg: RuntimeConfig = loadRuntimeConfig()
        const result = await openTurn(cfg, { initial_cash: cash })
        const data = result.data as Record<string, unknown>
        const backendId = Number(data?.id ?? data?.turn_id ?? 0)
        if (!backendId) {
          setError('Turno abierto pero sin ID de backend. Revisa la conexion.')
          setBusy(false)
          return
        }
        const shift: ShiftRecord = {
          id: `shift-${Date.now()}`,
          backendTurnId: backendId,
          terminalId: cfg.terminalId,
          openedAt: new Date().toISOString(),
          openedBy: operator,
          openingCash: cash,
          status: 'open',
          salesCount: 0,
          totalSales: 0,
          cashSales: 0,
          cardSales: 0,
          transferSales: 0
        }
        saveCurrentShift(shift)
        onComplete()
      } catch (err) {
        const msg = (err as Error).message ?? ''
        // Backend dice que ya hay un turno abierto: resincronizar y mostrar "Turno Abierto"
        if (/ya tienes un turno abierto|turno abierto/i.test(msg)) {
          try {
            const cfgLoaded = loadRuntimeConfig()
            const turn = await getCurrentTurn(cfgLoaded)
            const data = (turn?.data ?? turn) as Record<string, unknown> | null
            if (data?.id != null && data?.status === 'open') {
              const recovered: ShiftRecord = {
                id: `shift-recovered-${data.id}`,
                backendTurnId: Number(data.id),
                terminalId: Number(data.terminal_id ?? data.branch_id ?? cfgLoaded.terminalId),
                openedAt: String(data.start_timestamp ?? new Date().toISOString()),
                openedBy: operator,
                openingCash: Number(data.initial_cash ?? 0),
                status: 'open',
                salesCount: 0,
                totalSales: 0
              }
              try {
                const raw = await getTurnSummary(cfgLoaded, Number(data.id))
                const summary = (raw.data ?? raw) as Record<string, unknown>
                recovered.salesCount = Number(summary.sales_count ?? 0)
                recovered.totalSales = Math.round(Number(summary.total_sales ?? 0) * 100) / 100
              } catch {
                /* resumen opcional */
              }
              saveCurrentShift(recovered)
              setExistingShift(recovered)
              setPhase('existing_shift')
              setError('')
              return
            }
          } catch {
            /* fallback: mostrar error tal cual */
          }
          setError('Ya tienes un turno abierto. Elige continuar o cerrarlo primero.')
        } else {
          setError(msg)
        }
      } finally {
        setBusy(false)
      }
    },
    [operator, onComplete]
  )

  const handleOpenSubmit = useCallback(
    (e: FormEvent): void => {
      e.preventDefault()
      const cash = parseFloat(initialCash)
      if (!Number.isFinite(cash) || cash < 0) {
        setError('Ingresa un monto valido')
        return
      }
      void doOpenTurn(cash)
    },
    [initialCash, doOpenTurn]
  )

  const handleContinue = useCallback((): void => {
    onComplete()
  }, [onComplete])

  const handleCloseAndOpen = useCallback((): void => {
    setError('')
    // Pre-fill closing cash with expected amount from backend
    if (existingShift?.backendTurnId) {
      const cfg = loadRuntimeConfig()
      setClosingCash('0')
      setPhase('closing_shift')
      getTurnSummary(cfg, existingShift.backendTurnId)
        .then((raw) => {
          const data = (raw.data ?? raw) as Record<string, unknown>
          const exp = Number(data.expected_cash ?? 0)
          if (Number.isFinite(exp)) {
            setClosingCash(exp.toFixed(2))
          }
        })
        .catch(() => {
          /* keep 0 — user can type manually */
        })
    } else {
      setClosingCash('0')
      setPhase('closing_shift')
    }
  }, [existingShift])

  const handleCloseSubmit = useCallback(
    async (e: FormEvent): Promise<void> => {
      e.preventDefault()
      if (!existingShift?.backendTurnId) {
        setError('Turno sin ID de backend.')
        return
      }
      const cash = parseFloat(closingCash)
      if (!Number.isFinite(cash) || cash < 0) {
        setError('Ingresa un monto valido')
        return
      }
      setBusy(true)
      setError('')
      try {
        const cfg = loadRuntimeConfig()
        const result = await closeTurn(cfg, existingShift.backendTurnId, { final_cash: cash })
        const data = result.data as Record<string, unknown>
        const expectedFromBackend = Number(data?.expected_cash ?? 0)
        const differenceFromBackend = Number(data?.difference ?? 0)

        // Save closed shift to history
        const closed: ShiftRecord = {
          ...existingShift,
          status: 'closed',
          closedAt: new Date().toISOString(),
          closingCash: cash,
          expectedCash: expectedFromBackend,
          cashDifference: differenceFromBackend
        }
        const history = readShiftHistory()
        saveShiftHistory([closed, ...history])
        saveCurrentShift(null)

        setCut({ expected: expectedFromBackend, counted: cash, difference: differenceFromBackend })

        // Try to load summary (non-blocking)
        try {
          const raw = await getTurnSummary(cfg, existingShift.backendTurnId)
          setSummary((raw.data ?? raw) as Record<string, unknown>)
        } catch {
          /* summary is optional */
        }

        setPhase('cut_summary')
      } catch (err) {
        const msg = (err as Error).message ?? ''
        // Si el backend dice que el turno ya estaba cerrado, limpiar estado local
        // para no permitir "Volver" a un turno fantasma
        if (msg.toLowerCase().includes('cerrado')) {
          saveCurrentShift(null)
          setExistingShift(null)
          setPhase('no_shift')
          setError('Ese turno ya estaba cerrado. Puedes abrir uno nuevo.')
        } else {
          setError(msg)
        }
      } finally {
        setBusy(false)
      }
    },
    [existingShift, closingCash]
  )

  const handleAfterCut = useCallback((): void => {
    setExistingShift(null)
    setInitialCash('')
    setError('')
    setPrintStatus('idle')
    setPrintMessage('')
    setPhase('opening_shift')
  }, [])

  const handlePrintCut = useCallback(async (): Promise<void> => {
    if (!existingShift?.backendTurnId) {
      setPrintMessage('No hay turno para imprimir.')
      setPrintStatus('error')
      return
    }
    setPrintStatus('printing')
    setPrintMessage('')
    try {
      const cfg = loadRuntimeConfig()
      await printShiftReport(cfg, existingShift.backendTurnId)
      setPrintMessage('Corte enviado a impresora.')
      setPrintStatus('ok')
    } catch (err) {
      const msg = (err as Error).message ?? 'Error al imprimir'
      setPrintMessage(msg)
      setPrintStatus('error')
    }
  }, [existingShift?.backendTurnId])

  const handleNewShiftSubmit = useCallback(
    (e: FormEvent): void => {
      e.preventDefault()
      const cash = parseFloat(initialCash)
      if (!Number.isFinite(cash) || cash < 0) {
        setError('Ingresa un monto valido')
        return
      }
      void doOpenTurn(cash)
    },
    [initialCash, doOpenTurn]
  )

  // --- Shared styles ---
  const backdrop =
    'fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm'
  const card = 'w-full max-w-sm rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl'
  const inputCls =
    'w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2.5 px-3 text-sm font-semibold mb-3 focus:border-blue-500 focus:outline-none'
  const btnPrimary =
    'w-full rounded-xl bg-blue-600 py-2.5 font-bold text-white hover:bg-blue-500 transition-colors disabled:opacity-40'
  const btnSecondary =
    'w-full rounded-xl border border-zinc-700 bg-zinc-800 py-2.5 font-bold text-zinc-300 hover:bg-zinc-700 transition-colors'
  const btnDanger =
    'w-full rounded-xl bg-rose-600/20 border border-rose-500/30 py-2.5 font-bold text-rose-400 hover:bg-rose-600/40 transition-colors'

  // --- Phase: checking ---
  if (phase === 'checking') {
    return (
      <div className={backdrop}>
        <div className={card + ' text-center'}>
          <p className="text-zinc-400 text-sm">Verificando turno...</p>
        </div>
      </div>
    )
  }

  // --- Phase: no_shift ---
  if (phase === 'no_shift') {
    return (
      <div className={backdrop}>
        <form
          ref={modalRef as React.RefObject<HTMLFormElement>}
          onSubmit={handleOpenSubmit}
          onClick={(e) => e.stopPropagation()}
          className={card}
        >
          <h2 className="text-lg font-bold text-blue-400 mb-4">Abrir Nuevo Turno</h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 mb-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wider font-bold">Operador</p>
            <p className="text-sm font-semibold text-zinc-200 mt-0.5">{operator}</p>
          </div>
          <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">
            Fondo inicial ($)
          </label>
          <input
            ref={inputRef}
            className={inputCls}
            type="number"
            min={0}
            step="0.01"
            value={initialCash}
            onChange={(e) => setInitialCash(e.target.value)}
            placeholder="0.00"
          />
          {error && <p className="text-rose-400 text-sm mb-3">{error}</p>}
          <button type="submit" disabled={busy} className={btnPrimary}>
            {busy ? 'Abriendo turno...' : 'Abrir turno'}
          </button>
        </form>
      </div>
    )
  }

  // --- Phase: existing_shift ---
  if (phase === 'existing_shift' && existingShift) {
    const openDate = new Date(existingShift.openedAt)
    const dateStr = openDate.toLocaleDateString('es-MX', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    })
    const timeStr = openDate.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
    return (
      <div className={backdrop}>
        <div
          ref={modalRef as React.RefObject<HTMLDivElement>}
          onClick={(e) => e.stopPropagation()}
          className={`${card} text-center`}
        >
          <h2 className="text-lg font-bold text-amber-400 mb-4">Turno Abierto</h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 mb-4 space-y-1 text-left">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Turno por:</span>
              <span className="font-semibold text-zinc-200">{existingShift.openedBy}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Desde:</span>
              <span className="font-semibold text-zinc-200">
                {dateStr} {timeStr}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Ventas:</span>
              <span className="font-semibold text-zinc-200">
                {existingShift.salesCount ?? 0} — ${(existingShift.totalSales ?? 0).toFixed(2)}
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <button onClick={handleContinue} className={btnPrimary}>
              Continuar turno
            </button>
            <button onClick={handleCloseAndOpen} className={btnSecondary}>
              Cerrar turno y abrir nuevo
            </button>
            <button onClick={onExit} className={btnDanger}>
              Cerrar programa
            </button>
          </div>
        </div>
      </div>
    )
  }

  // --- Phase: closing_shift ---
  if (phase === 'closing_shift') {
    return (
      <div className={backdrop}>
        <form
          ref={modalRef as React.RefObject<HTMLFormElement>}
          onSubmit={(e) => void handleCloseSubmit(e)}
          onClick={(e) => e.stopPropagation()}
          className={card}
        >
          <h2 className="text-lg font-bold text-rose-400 mb-4">Cerrar Turno</h2>
          <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">
            Efectivo en caja ($)
          </label>
          <input
            ref={inputRef}
            className={inputCls}
            type="number"
            min={0}
            step="0.01"
            value={closingCash}
            onChange={(e) => setClosingCash(e.target.value)}
            placeholder="0.00"
          />
          <p className="text-xs text-zinc-500 mb-3 -mt-1">
            Pre-llenado con el efectivo esperado. Ajusta solo si el conteo fisico difiere.
          </p>
          {error && <p className="text-rose-400 text-sm mb-3">{error}</p>}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setPhase('existing_shift')}
              className={btnSecondary}
              disabled={busy}
            >
              Volver
            </button>
            <button
              type="submit"
              disabled={busy}
              className="flex flex-1 flex-col justify-start items-start rounded-xl bg-rose-600 py-2.5 font-bold text-white hover:bg-rose-500 transition-colors disabled:opacity-40"
            >
              {busy ? 'Cerrando...' : 'Cerrar turno'}
            </button>
          </div>
        </form>
      </div>
    )
  }

  // --- Phase: cut_summary ---
  if (phase === 'cut_summary' && cut) {
    const diffColor =
      cut.difference < 0
        ? 'text-rose-400'
        : cut.difference > 0
          ? 'text-amber-400'
          : 'text-emerald-400'
    return (
      <div className={backdrop}>
        <div
          ref={modalRef as React.RefObject<HTMLDivElement>}
          onClick={(e) => e.stopPropagation()}
          className={card}
        >
          <h2 className="text-lg font-bold text-emerald-400 mb-4">Corte de Turno</h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 mb-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Esperado:</span>
              <span className="font-semibold text-zinc-200">${cut.expected.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Contado:</span>
              <span className="font-semibold text-zinc-200">${cut.counted.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Diferencia:</span>
              <span className={`font-semibold ${diffColor}`}>
                {cut.difference >= 0 ? '+' : ''}${cut.difference.toFixed(2)}
              </span>
            </div>
            {summary && (
              <div className="border-t border-zinc-800 pt-2 mt-2">
                <p className="text-xs text-zinc-500 uppercase tracking-wider font-bold mb-1">
                  Resumen backend
                </p>
                <div className="text-xs text-zinc-400 space-y-0.5">
                  {summary.total_sales != null && (
                    <div className="flex justify-between">
                      <span>Total ventas:</span>
                      <span>${Number(summary.total_sales).toFixed(2)}</span>
                    </div>
                  )}
                  {summary.sales_count != null && (
                    <div className="flex justify-between">
                      <span>Num. ventas:</span>
                      <span>{String(summary.sales_count)}</span>
                    </div>
                  )}
                  {summary.cash_in != null && (
                    <div className="flex justify-between">
                      <span>Entradas:</span>
                      <span>${Number(summary.cash_in).toFixed(2)}</span>
                    </div>
                  )}
                  {summary.cash_out != null && (
                    <div className="flex justify-between">
                      <span>Retiros:</span>
                      <span>${Number(summary.cash_out).toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          <p className="text-emerald-400 text-sm mb-4 flex items-center justify-center gap-1">
            <Check className="w-4 h-4" /> Turno cerrado
          </p>
          {printMessage && (
            <p
              className={`text-sm mb-3 ${
                printStatus === 'error'
                  ? 'text-rose-400'
                  : printStatus === 'ok'
                    ? 'text-emerald-400'
                    : 'text-zinc-400'
              }`}
            >
              {printMessage}
            </p>
          )}
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => void handlePrintCut()}
              disabled={printStatus === 'printing'}
              className={btnSecondary}
            >
              <span className="flex items-center justify-center gap-2">
                <Printer className="w-4 h-4" />
                {printStatus === 'printing' ? 'Imprimiendo...' : 'Imprimir corte de caja'}
              </span>
            </button>
            <button onClick={handleAfterCut} className={btnPrimary}>
              Abrir nuevo turno
            </button>
          </div>
        </div>
      </div>
    )
  }

  // --- Phase: opening_shift ---
  if (phase === 'opening_shift') {
    return (
      <div className={backdrop}>
        <form
          ref={modalRef as React.RefObject<HTMLFormElement>}
          onSubmit={handleNewShiftSubmit}
          onClick={(e) => e.stopPropagation()}
          className={card}
        >
          <h2 className="text-lg font-bold text-blue-400 mb-4">Abrir Nuevo Turno</h2>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 mb-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wider font-bold">Operador</p>
            <p className="text-sm font-semibold text-zinc-200 mt-0.5">{operator}</p>
          </div>
          <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">
            Fondo inicial ($)
          </label>
          <input
            ref={inputRef}
            className={inputCls}
            type="number"
            min={0}
            step="0.01"
            value={initialCash}
            onChange={(e) => setInitialCash(e.target.value)}
            placeholder="0.00"
          />
          {error && <p className="text-rose-400 text-sm mb-3">{error}</p>}
          <button type="submit" disabled={busy} className={btnPrimary}>
            {busy ? 'Abriendo turno...' : 'Abrir turno'}
          </button>
        </form>
      </div>
    )
  }

  return null
}
