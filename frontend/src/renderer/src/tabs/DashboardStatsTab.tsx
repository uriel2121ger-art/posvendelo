import type { ReactElement } from 'react'
import { useState, useEffect, useRef, useCallback } from 'react'
import { RefreshCw, TrendingUp, DollarSign, AlertTriangle, LayoutDashboard } from 'lucide-react'

import {
  loadRuntimeConfig,
  getDashboardQuick,
  getDashboardResico,
  getDashboardWealth,
  getDashboardAI,
  getDashboardExecutive,
  getUserRole
} from '../posApi'

interface QuickStats {
  ventas_hoy: number
  total_hoy: number
  mermas_pendientes: number
}

function DashboardPanel({
  title,
  onLoad,
  restricted
}: {
  title: string
  onLoad: () => Promise<Record<string, unknown>>
  restricted?: boolean
}): ReactElement {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [panelLoading, setPanelLoading] = useState(false)
  const [panelError, setPanelError] = useState('')
  const loadIdRef = useRef(0)

  async function load(): Promise<void> {
    const reqId = ++loadIdRef.current
    setPanelLoading(true)
    setPanelError('')
    try {
      const raw = await onLoad()
      if (loadIdRef.current !== reqId) return
      setData((raw.data ?? raw) as Record<string, unknown>)
    } catch (err) {
      if (loadIdRef.current !== reqId) return
      setPanelError(err instanceof Error ? err.message : 'Ocurrió un error inesperado.')
    } finally {
      if (loadIdRef.current === reqId) setPanelLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider">{title}</h3>
        <button
          onClick={() => void load()}
          disabled={panelLoading || restricted}
          className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium transition-colors disabled:opacity-50"
        >
          {panelLoading ? 'Cargando...' : 'Cargar'}
        </button>
      </div>
      {restricted && <p className="text-xs text-zinc-500">Solo para gerente o superior</p>}
      {panelError && <p className="text-xs text-rose-400">{panelError}</p>}
      {data && (
        <pre className="max-h-48 overflow-auto rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-xs font-mono text-zinc-300">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

function ExtendedPanels(): ReactElement {
  const role = getUserRole()
  const canManage = role === 'manager' || role === 'owner' || role === 'admin'
  return (
    <div className="mt-8 space-y-6">
      <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
        Paneles avanzados
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DashboardPanel title="RESICO" onLoad={() => getDashboardResico(loadRuntimeConfig())} />
        <DashboardPanel
          title="Patrimonio"
          onLoad={() => getDashboardWealth(loadRuntimeConfig())}
          restricted={!canManage}
        />
        <DashboardPanel title="Análisis IA" onLoad={() => getDashboardAI(loadRuntimeConfig())} />
        <DashboardPanel
          title="Ejecutivo"
          onLoad={() => getDashboardExecutive(loadRuntimeConfig())}
          restricted={!canManage}
        />
      </div>
    </div>
  )
}

export default function DashboardStatsTab(): ReactElement {
  const [stats, setStats] = useState<QuickStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdate, setLastUpdate] = useState('')
  const requestIdRef = useRef(0)

  const fetchStats = useCallback(async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    try {
      setError('')
      const cfg = loadRuntimeConfig()
      const raw = await getDashboardQuick(cfg)
      if (requestIdRef.current !== reqId) return
      const d = (raw.data ?? raw) as Record<string, unknown>
      const safeNum = (v: unknown): number => {
        const n = Number(v ?? 0)
        return Number.isFinite(n) ? n : 0
      }
      setStats({
        ventas_hoy: safeNum(d.ventas_hoy),
        total_hoy: safeNum(d.total_hoy),
        mermas_pendientes: safeNum(d.mermas_pendientes)
      })
      setLastUpdate(new Date().toLocaleTimeString('es-MX'))
    } catch (err) {
      if (requestIdRef.current !== reqId) return
      setError(err instanceof Error ? err.message : 'Error al cargar estadísticas')
    } finally {
      if (requestIdRef.current === reqId) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStats()
    const interval = setInterval(() => void fetchStats(), 30_000)
    const reqRef = requestIdRef
    return () => {
      reqRef.current++
      clearInterval(interval)
    }
  }, [fetchStats])

  const handleRefresh = (): void => {
    setLoading(true)
    void fetchStats()
  }

  const cards = stats
    ? [
        {
          label: 'Ventas hoy',
          value: String(stats.ventas_hoy),
          icon: TrendingUp,
          color: 'text-emerald-400',
          bg: 'bg-emerald-400/10'
        },
        {
          label: 'Ingreso hoy',
          value: `$${stats.total_hoy.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`,
          icon: DollarSign,
          color: 'text-blue-400',
          bg: 'bg-blue-400/10'
        },
        {
          label: 'Mermas pendientes',
          value: String(stats.mermas_pendientes),
          icon: AlertTriangle,
          color: stats.mermas_pendientes > 0 ? 'text-amber-400' : 'text-zinc-400',
          bg: stats.mermas_pendientes > 0 ? 'bg-amber-400/10' : 'bg-zinc-400/10'
        }
      ]
    : []

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full p-4 lg:p-6 space-y-6">
          <div className="flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4">
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <LayoutDashboard className="w-6 h-6 text-indigo-500 shrink-0" />
              <span>Panel en tiempo real</span>
            </h1>
            <div className="flex items-center gap-2 shrink-0">
              {lastUpdate && (
                <span className="text-xs text-zinc-500 hidden sm:inline">
                  Actualizado: {lastUpdate}
                </span>
              )}
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors border border-zinc-800 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                Actualizar
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
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
                  className="flex items-center gap-5 p-4 lg:p-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 backdrop-blur-sm"
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
            Actualización automática cada 30 segundos
          </div>

          {/* Extended Dashboard Panels */}
          <ExtendedPanels />
        </div>
      </div>
    </div>
  )
}
