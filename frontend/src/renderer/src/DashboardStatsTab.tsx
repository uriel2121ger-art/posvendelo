import type { ReactElement } from 'react'
import { useState, useEffect, useRef } from 'react'
import { RefreshCw, TrendingUp, DollarSign, AlertTriangle } from 'lucide-react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, getDashboardQuick } from './posApi'

interface QuickStats {
  ventas_hoy: number
  total_hoy: number
  mermas_pendientes: number
}

export default function DashboardStatsTab(): ReactElement {
  const [stats, setStats] = useState<QuickStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdate, setLastUpdate] = useState('')
  const requestIdRef = useRef(0)

  const fetchStats = async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    try {
      setError('')
      const cfg = loadRuntimeConfig()
      const raw = await getDashboardQuick(cfg)
      if (requestIdRef.current !== reqId) return
      const d = (raw.data ?? raw) as Record<string, unknown>
      const safeNum = (v: unknown): number => { const n = Number(v ?? 0); return Number.isFinite(n) ? n : 0 }
      setStats({
        ventas_hoy: safeNum(d.ventas_hoy),
        total_hoy: safeNum(d.total_hoy),
        mermas_pendientes: safeNum(d.mermas_pendientes)
      })
      setLastUpdate(new Date().toLocaleTimeString('es-MX'))
    } catch (err) {
      if (requestIdRef.current !== reqId) return
      setError(err instanceof Error ? err.message : 'Error cargando estadísticas')
    } finally {
      if (requestIdRef.current === reqId) setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    const interval = setInterval(() => fetchStats(), 30_000)
    return () => {
      requestIdRef.current++
      clearInterval(interval)
    }
  }, [])

  const handleRefresh = (): void => {
    setLoading(true)
    void fetchStats()
  }

  const cards = stats
    ? [
        {
          label: 'Ventas Hoy',
          value: String(stats.ventas_hoy),
          icon: TrendingUp,
          color: 'text-emerald-400',
          bg: 'bg-emerald-400/10'
        },
        {
          label: 'Ingreso Hoy',
          value: `$${stats.total_hoy.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`,
          icon: DollarSign,
          color: 'text-blue-400',
          bg: 'bg-blue-400/10'
        },
        {
          label: 'Mermas Pendientes',
          value: String(stats.mermas_pendientes),
          icon: AlertTriangle,
          color: stats.mermas_pendientes > 0 ? 'text-amber-400' : 'text-zinc-400',
          bg: stats.mermas_pendientes > 0 ? 'bg-amber-400/10' : 'bg-zinc-400/10'
        }
      ]
    : []

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-slate-200">
      <TopNavbar />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-2xl font-bold">Dashboard en Tiempo Real</h1>
            <div className="flex items-center gap-3">
              {lastUpdate && (
                <span className="text-xs text-zinc-500">Actualizado: {lastUpdate}</span>
              )}
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm font-medium transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Actualizar
              </button>
            </div>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
              {error}
            </div>
          )}

          {loading && !stats ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-8 h-8 animate-spin text-zinc-500" />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {cards.map((card) => (
                <div
                  key={card.label}
                  className="flex items-center gap-5 p-6 rounded-2xl bg-zinc-900/60 border border-zinc-800 backdrop-blur-sm"
                >
                  <div className={`p-4 rounded-xl ${card.bg}`}>
                    <card.icon className={`w-7 h-7 ${card.color}`} />
                  </div>
                  <div>
                    <div className={`text-3xl font-black ${card.color}`}>{card.value}</div>
                    <div className="text-sm text-zinc-400 font-medium mt-1">{card.label}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-8 text-center text-xs text-zinc-600">
            Auto-refresh cada 30 segundos
          </div>
        </div>
      </div>
    </div>
  )
}
