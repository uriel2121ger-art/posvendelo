import type { ReactElement } from 'react'
import { useState, useEffect, useRef } from 'react'
import { RefreshCw, Plus, Receipt } from 'lucide-react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, getExpensesSummary, registerExpense } from './posApi'

export default function ExpensesTab(): ReactElement {
  const [monthTotal, setMonthTotal] = useState(0)
  const [yearTotal, setYearTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState('')

  // Form
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [reason, setReason] = useState('')
  const requestIdRef = useRef(0)
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchExpenses = async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    try {
      setError('')
      const cfg = loadRuntimeConfig()
      const body = await getExpensesSummary(cfg)
      if (requestIdRef.current !== reqId) return
      const data = (body.data ?? body) as Record<string, unknown>
      setMonthTotal(Number(data.month ?? 0))
      setYearTotal(Number(data.year ?? 0))
    } catch (err) {
      if (requestIdRef.current !== reqId) return
      setError(err instanceof Error ? err.message : 'Error cargando gastos')
    } finally {
      if (requestIdRef.current === reqId) setLoading(false)
    }
  }

  useEffect(() => {
    fetchExpenses()
    return () => {
      requestIdRef.current++
      if (successTimerRef.current) clearTimeout(successTimerRef.current)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    const numAmount = parseFloat(amount)
    if (!Number.isFinite(numAmount) || numAmount <= 0) {
      setError('Ingresa un monto válido mayor a 0')
      return
    }
    if (!description.trim()) {
      setError('La descripción es obligatoria')
      return
    }

    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const cfg = loadRuntimeConfig()
      await registerExpense(cfg, {
        amount: numAmount,
        description: description.trim(),
        reason: reason.trim() || undefined
      })
      setSuccess('Gasto registrado correctamente')
      setAmount('')
      setDescription('')
      setReason('')
      // Refresh list
      setLoading(true)
      void fetchExpenses()
      if (successTimerRef.current) clearTimeout(successTimerRef.current)
      successTimerRef.current = setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error registrando gasto')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-slate-200">
      <TopNavbar />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-2xl font-bold">Gastos</h1>
            <button
              onClick={() => {
                setLoading(true)
                void fetchExpenses()
              }}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Recargar
            </button>
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
            <div className="flex items-center gap-4 p-5 rounded-xl bg-zinc-900/60 border border-zinc-800">
              <div className="p-3 rounded-lg bg-blue-400/10">
                <Receipt className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <div className="text-2xl font-bold text-blue-400">
                  ${monthTotal.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-zinc-500 font-medium">Total este mes</div>
              </div>
            </div>
            <div className="flex items-center gap-4 p-5 rounded-xl bg-zinc-900/60 border border-zinc-800">
              <div className="p-3 rounded-lg bg-purple-400/10">
                <Receipt className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-400">
                  ${yearTotal.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-zinc-500 font-medium">Total este año</div>
              </div>
            </div>
          </div>

          {/* Register form */}
          <form
            onSubmit={handleSubmit}
            className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800 mb-8"
          >
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Plus className="w-5 h-5 text-emerald-400" /> Registrar Gasto
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                  Monto ($)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  disabled={submitting}
                  className="w-full px-3 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                  Descripcion
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Ej: Luz, Agua, Insumos..."
                  disabled={submitting}
                  className="w-full px-3 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                  Razon (opcional)
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Detalles adicionales..."
                  disabled={submitting}
                  className="w-full px-3 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="mt-4 flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm transition-colors disabled:opacity-50"
            >
              {submitting ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Registrar
            </button>
          </form>

          {error && (
            <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="mb-6 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
              {success}
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="w-6 h-6 animate-spin text-zinc-500" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
