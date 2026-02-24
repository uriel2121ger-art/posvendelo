import type { ReactElement } from 'react'
import { useState, useEffect } from 'react'
import { RefreshCw, Plus, Receipt } from 'lucide-react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, getExpensesSummary, registerExpense } from './posApi'

interface ExpenseRecord {
  id: number
  amount: number
  reason: string
  description: string
  created_at: string
}

export default function ExpensesTab(): ReactElement {
  const [expenses, setExpenses] = useState<ExpenseRecord[]>([])
  const [monthTotal, setMonthTotal] = useState(0)
  const [yearTotal, setYearTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState('')

  // Form
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [description, setDescription] = useState('')

  const fetchExpenses = async (cancelled: { current: boolean }): Promise<void> => {
    try {
      setError('')
      const cfg = loadRuntimeConfig()
      const body = await getExpensesSummary(cfg)
      if (cancelled.current) return
      const data = body.data as Record<string, unknown> | undefined
      const src = data ?? body
      setMonthTotal(Number(src.month_total ?? 0))
      setYearTotal(Number(src.year_total ?? 0))
      setExpenses((src.expenses ?? []) as ExpenseRecord[])
    } catch (err) {
      if (cancelled.current) return
      setError(err instanceof Error ? err.message : 'Error cargando gastos')
    } finally {
      if (!cancelled.current) setLoading(false)
    }
  }

  useEffect(() => {
    const cancelled = { current: false }
    fetchExpenses(cancelled)
    return () => { cancelled.current = true }
  }, [])

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    const numAmount = parseFloat(amount)
    if (!numAmount || numAmount <= 0) {
      setError('Ingresa un monto válido mayor a 0')
      return
    }
    if (!reason.trim()) {
      setError('La razón es obligatoria')
      return
    }

    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const cfg = loadRuntimeConfig()
      await registerExpense(cfg, {
        amount: numAmount,
        reason: reason.trim(),
        description: description.trim() || undefined
      })
      setSuccess('Gasto registrado correctamente')
      setAmount('')
      setReason('')
      setDescription('')
      // Refresh list
      setLoading(true)
      fetchExpenses({ current: false })
      setTimeout(() => setSuccess(''), 3000)
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
                fetchExpenses({ current: false })
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
                  className="w-full px-3 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                  Razon
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Ej: Luz, Agua, Insumos..."
                  className="w-full px-3 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                  Descripcion (opcional)
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Detalles adicionales..."
                  className="w-full px-3 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
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

          {/* Expenses table */}
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="w-6 h-6 animate-spin text-zinc-500" />
            </div>
          ) : expenses.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-zinc-500">
              <Receipt className="w-10 h-10 mb-3 opacity-50" />
              <p className="text-sm font-medium">Sin gastos registrados este mes</p>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-zinc-900/80 text-zinc-400 text-left">
                    <th className="px-4 py-3 font-medium">Fecha</th>
                    <th className="px-4 py-3 font-medium">Razon</th>
                    <th className="px-4 py-3 font-medium">Descripcion</th>
                    <th className="px-4 py-3 font-medium text-right">Monto</th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.map((exp) => (
                    <tr key={exp.id} className="border-t border-zinc-800/60 hover:bg-zinc-900/40">
                      <td className="px-4 py-3 text-zinc-500 text-xs">
                        {exp.created_at
                          ? new Date(exp.created_at).toLocaleDateString('es-MX')
                          : '—'}
                      </td>
                      <td className="px-4 py-3 font-medium text-zinc-200">{exp.reason}</td>
                      <td className="px-4 py-3 text-zinc-400 max-w-[300px] truncate">
                        {exp.description || '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-rose-400">
                        -${Number(exp.amount).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
