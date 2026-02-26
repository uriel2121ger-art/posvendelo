import type { ReactElement } from 'react'
import { useState, useEffect, useRef } from 'react'
import { RefreshCw, Check, X, AlertTriangle } from 'lucide-react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, getMermasPending, approveMerma } from './posApi'

interface MermaRecord {
  id: number
  product: string
  sku: string | null
  quantity: number
  unit_cost: number
  total_value: number
  loss_type: string
  reason: string
  category: string
  has_photo: boolean
  witness: string
  created_at: string | null
}

export default function MermasTab(): ReactElement {
  const [mermas, setMermas] = useState<MermaRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionId, setActionId] = useState<number | null>(null)
  const [notesMap, setNotesMap] = useState<Record<number, string>>({})
  const requestIdRef = useRef(0)

  const fetchMermas = async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    try {
      setError('')
      const cfg = loadRuntimeConfig()
      const body = await getMermasPending(cfg)
      if (requestIdRef.current !== reqId) return
      const inner = (body.data ?? body) as Record<string, unknown>
      const raw = inner.mermas
      const data = Array.isArray(raw) ? (raw as MermaRecord[]) : []
      setMermas(data)
      setNotesMap({})
    } catch (err) {
      if (requestIdRef.current !== reqId) return
      setError(err instanceof Error ? err.message : 'Error cargando mermas')
    } finally {
      if (requestIdRef.current === reqId) setLoading(false)
    }
  }

  useEffect(() => {
    fetchMermas()
    return () => {
      requestIdRef.current++
    }
  }, [])

  const handleAction = async (id: number, approved: boolean): Promise<void> => {
    const target = mermas.find((m) => m.id === id)
    if (!target) {
      setError('Merma no encontrada. Recarga la lista.')
      return
    }
    if (
      !window.confirm(
        `¿${approved ? 'Aprobar' : 'Rechazar'} merma de "${target.product}" (${target.quantity} uds)?`
      )
    )
      return
    setActionId(id)
    try {
      const cfg = loadRuntimeConfig()
      await approveMerma(cfg, id, approved, notesMap[id])
      setMermas((prev) => prev.filter((m) => m.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error procesando merma')
    } finally {
      setActionId(null)
    }
  }

  const pendingCount = mermas.length

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-slate-200">
      <TopNavbar />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">Mermas</h1>
              {pendingCount > 0 && (
                <span className="px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold">
                  {pendingCount} pendiente{pendingCount !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            <button
              onClick={() => {
                setLoading(true)
                void fetchMermas()
              }}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Recargar
            </button>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-8 h-8 animate-spin text-zinc-500" />
            </div>
          ) : mermas.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
              <AlertTriangle className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">Sin mermas pendientes</p>
              <p className="text-sm mt-1">Todas las mermas han sido procesadas</p>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-zinc-900/80 text-zinc-400 text-left">
                    <th className="px-4 py-3 font-medium">Producto</th>
                    <th className="px-4 py-3 font-medium text-right">Cantidad</th>
                    <th className="px-4 py-3 font-medium text-right">Valor</th>
                    <th className="px-4 py-3 font-medium">Tipo</th>
                    <th className="px-4 py-3 font-medium">Razon</th>
                    <th className="px-4 py-3 font-medium">Fecha</th>
                    <th className="px-4 py-3 font-medium">Notas</th>
                    <th className="px-4 py-3 font-medium text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {mermas.map((m) => (
                    <tr key={m.id} className="border-t border-zinc-800/60 hover:bg-zinc-900/40">
                      <td className="px-4 py-3 font-medium text-zinc-200">
                        {m.product}
                        {m.sku && <span className="ml-2 text-xs text-zinc-500">{m.sku}</span>}
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-300">{m.quantity}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">
                        $
                        {Number(m.total_value).toLocaleString('es-MX', {
                          minimumFractionDigits: 2
                        })}
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{m.loss_type}</td>
                      <td className="px-4 py-3 text-zinc-400 max-w-[200px] truncate">{m.reason}</td>
                      <td className="px-4 py-3 text-zinc-500 text-xs">
                        {m.created_at ? new Date(m.created_at).toLocaleDateString('es-MX') : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="text"
                          placeholder="Notas..."
                          value={notesMap[m.id] || ''}
                          onChange={(e) =>
                            setNotesMap((prev) => ({ ...prev, [m.id]: e.target.value }))
                          }
                          className="w-full px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => handleAction(m.id, true)}
                            disabled={actionId !== null}
                            className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                            title="Aprobar"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleAction(m.id, false)}
                            disabled={actionId !== null}
                            className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-colors disabled:opacity-50"
                            title="Rechazar"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
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
