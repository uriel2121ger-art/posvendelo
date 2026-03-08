import type { ReactElement } from 'react'
import { useState, useEffect, useRef } from 'react'
import { RefreshCw, Check, X, AlertTriangle, PackageX } from 'lucide-react'

import { useConfirm } from '../components/ConfirmDialog'
import { loadRuntimeConfig, getMermasPending, approveMerma } from '../posApi'

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
  const confirm = useConfirm()
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
      // Preserve notes for IDs still in the refreshed list
      const refreshedIds = new Set(data.map((m) => m.id))
      setNotesMap((prev) => {
        const kept: Record<number, string> = {}
        for (const [k, v] of Object.entries(prev)) {
          if (refreshedIds.has(Number(k))) kept[Number(k)] = v
        }
        return kept
      })
    } catch (err) {
      if (requestIdRef.current !== reqId) return
      setError(err instanceof Error ? err.message : 'Error al cargar mermas.')
    } finally {
      if (requestIdRef.current === reqId) setLoading(false)
    }
  }

  useEffect(() => {
    fetchMermas()
    const reqRef = requestIdRef
    return () => {
      reqRef.current++
    }
  }, [])

  const handleAction = async (id: number, approved: boolean): Promise<void> => {
    const target = mermas.find((m) => m.id === id)
    if (!target) {
      setError('Merma no encontrada. Recarga la lista.')
      return
    }
    if (
      !(await confirm(
        `¿${approved ? 'Aprobar' : 'Rechazar'} merma de "${target.product}" (${target.quantity} uds)?`,
        {
          variant: approved ? 'warning' : 'danger',
          title: approved ? 'Aprobar merma' : 'Rechazar merma'
        }
      ))
    )
      return
    setActionId(id)
    try {
      const cfg = loadRuntimeConfig()
      await approveMerma(cfg, id, approved, notesMap[id])
      setMermas((prev) => prev.filter((m) => m.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al procesar la merma.')
    } finally {
      setActionId(null)
    }
  }

  const pendingCount = mermas.length

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-5xl mx-auto w-full p-4 lg:p-6 space-y-6">
          <div className="flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4">
            <div className="flex items-center gap-2 min-w-0">
              <h1 className="text-xl font-bold text-white flex items-center gap-2 truncate">
                <PackageX className="w-6 h-6 text-amber-500 shrink-0" />
                <span className="truncate">Mermas</span>
              </h1>
              {pendingCount > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold shrink-0">
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
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors border border-zinc-800 disabled:opacity-50 shrink-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Recargar
            </button>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
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
              <p className="text-sm mt-1">Todas las mermas han sido procesadas.</p>
            </div>
          ) : (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold z-10">
                  <tr>
                    <th className="px-4 py-2">Producto</th>
                    <th className="px-4 py-2 text-right">Cantidad</th>
                    <th className="px-4 py-2 text-right">Valor</th>
                    <th className="px-4 py-2">Tipo</th>
                    <th className="px-4 py-2">Razón</th>
                    <th className="px-4 py-2">Fecha</th>
                    <th className="px-4 py-2">Notas</th>
                    <th className="px-4 py-2 text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {mermas.map((m) => (
                    <tr key={m.id} className="hover:bg-zinc-800/40 transition-colors">
                      <td className="px-4 py-2 text-sm font-medium text-zinc-200">
                        {m.product}
                        {m.sku && <span className="ml-2 text-xs text-zinc-500">{m.sku}</span>}
                      </td>
                      <td className="px-4 py-2 text-sm text-right text-zinc-300">{m.quantity}</td>
                      <td className="px-4 py-2 text-sm text-right text-zinc-300">
                        $
                        {Number(m.total_value).toLocaleString('es-MX', {
                          minimumFractionDigits: 2
                        })}
                      </td>
                      <td className="px-4 py-2 text-sm text-zinc-400">{m.loss_type}</td>
                      <td className="px-4 py-2 text-sm text-zinc-400 max-w-[200px] truncate">
                        {m.reason}
                      </td>
                      <td className="px-4 py-2 text-sm text-zinc-500">
                        {m.created_at ? new Date(m.created_at).toLocaleDateString('es-MX') : '—'}
                      </td>
                      <td className="px-4 py-2">
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
                      <td className="px-4 py-2">
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
