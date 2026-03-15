import type { ReactElement } from 'react'
import { useEffect, useState } from 'react'
import { BellRing, Building2, RefreshCw, ShieldAlert, Store } from 'lucide-react'

type OwnerPortfolioStatus = {
  controlPlaneUrl: string | null
  tenantName: string | null
  tenantSlug: string | null
  branchesTotal: number
  online: number
  offline: number
  salesTodayTotal: number
  alertsTotal: number
  branches: Array<Record<string, unknown>>
  alerts: Array<Record<string, unknown>>
  lastError: string | null
}

type OwnerCommercialStatus = {
  license: Record<string, unknown> | null
  health: Record<string, unknown> | null
  events: Array<Record<string, unknown>>
  lastError: string | null
}

type OwnerHealthSummaryStatus = {
  summary: Record<string, unknown> | null
  lastError: string | null
}

type OwnerAuditStatus = {
  audit: Array<Record<string, unknown>>
  lastError: string | null
}

export default function OwnerPortfolioTab(): ReactElement {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<OwnerPortfolioStatus | null>(null)
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([])
  const [timeline, setTimeline] = useState<Array<Record<string, unknown>>>([])
  const [timelineError, setTimelineError] = useState<string | null>(null)
  const [selectedBranchId, setSelectedBranchId] = useState<number | null>(null)
  const [commercial, setCommercial] = useState<OwnerCommercialStatus | null>(null)
  const [healthSummary, setHealthSummary] = useState<OwnerHealthSummaryStatus | null>(null)
  const [auditFeed, setAuditFeed] = useState<OwnerAuditStatus | null>(null)

  async function load(): Promise<void> {
    setLoading(true)
    try {
      const agent = window.api?.agent
      if (!agent?.getOwnerPortfolio) {
        setData({
          controlPlaneUrl: null,
          tenantName: null,
          tenantSlug: null,
          branchesTotal: 0,
          online: 0,
          offline: 0,
          salesTodayTotal: 0,
          alertsTotal: 0,
          branches: [],
          alerts: [],
          lastError:
            'El portfolio remoto requiere el agente local del escritorio. En navegador puro solo está disponible el companion conectado al servidor local.'
        })
        return
      }
      const result = await agent.getOwnerPortfolio()
      setData(result)
      if (agent.getOwnerEvents) {
        const ownerEvents = await agent.getOwnerEvents()
        setEvents(ownerEvents.events ?? [])
      } else {
        setEvents([])
      }
      if (agent.getOwnerCommercial) {
        const commercialState = await agent.getOwnerCommercial()
        setCommercial(commercialState)
      } else {
        setCommercial(null)
      }
      if (agent.getOwnerHealthSummary) {
        const healthState = await agent.getOwnerHealthSummary()
        setHealthSummary(healthState)
      } else {
        setHealthSummary(null)
      }
      if (agent.getOwnerAudit) {
        const auditState = await agent.getOwnerAudit()
        setAuditFeed(auditState)
      } else {
        setAuditFeed(null)
      }
      const firstBranchId =
        typeof result.branches?.[0]?.id === 'number'
          ? (result.branches[0].id as number)
          : Number(result.branches?.[0]?.id ?? 0) || null
      if (firstBranchId && agent.getOwnerBranchTimeline) {
        setSelectedBranchId(firstBranchId)
        const ownerTimeline = await agent.getOwnerBranchTimeline(firstBranchId)
        setTimeline(ownerTimeline.timeline ?? [])
        setTimelineError(ownerTimeline.lastError)
      } else {
        setTimeline([])
        setTimelineError(null)
      }
    } catch (err) {
      setData((prev) => prev ? { ...prev, lastError: err instanceof Error ? err.message : String(err) } : null)
    } finally {
      setLoading(false)
    }
  }

  async function loadTimeline(branchId: number): Promise<void> {
    setSelectedBranchId(branchId)
    const agent = window.api?.agent
    if (!agent?.getOwnerBranchTimeline) {
      setTimeline([])
      setTimelineError('El agente local no expone timeline por sucursal.')
      return
    }
    try {
      const result = await agent.getOwnerBranchTimeline(branchId)
      setTimeline(result.timeline ?? [])
      setTimelineError(result.lastError)
    } catch (err) {
      setTimeline([])
      setTimelineError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const branches = data?.branches ?? []
  const alerts = data?.alerts ?? []
  const reminderTypes = Array.isArray(commercial?.health?.reminder_types)
    ? (commercial?.health?.reminder_types as string[])
    : []

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto w-full p-4 lg:p-6 space-y-6 pb-24">
          <div className="flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4">
            <div className="flex items-center gap-2 min-w-0">
              <Building2 className="w-6 h-6 text-cyan-400 shrink-0" />
              <div className="min-w-0">
                <h1 className="text-xl font-bold text-white truncate">Portfolio del dueño</h1>
                <p className="text-xs text-zinc-500 truncate">
                  {data?.tenantName ?? 'Tenant sin resolver'}{' '}
                  {data?.tenantSlug ? `• ${data.tenantSlug}` : ''}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors border border-zinc-800 px-3 py-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Actualizar
            </button>
          </div>

          {data?.lastError && (
            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
              {data.lastError}
            </div>
          )}
          {commercial?.lastError && (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
              {commercial.lastError}
            </div>
          )}
          {healthSummary?.lastError && (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
              {healthSummary.lastError}
            </div>
          )}
          {auditFeed?.lastError && (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
              {auditFeed.lastError}
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
              <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                Estado comercial del tenant
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">Plan</div>
                  <div className="mt-1 text-lg font-bold text-white">
                    {String(commercial?.license?.license_type ?? 'sin-licencia')}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">Estado</div>
                  <div className="mt-1 text-lg font-bold text-white">
                    {String(commercial?.license?.status ?? 'desconocido')}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">
                    Días vigencia
                  </div>
                  <div className="mt-1 font-mono text-cyan-300">
                    {String(commercial?.health?.days_until_valid ?? 'sin límite')}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">Días soporte</div>
                  <div className="mt-1 font-mono text-cyan-300">
                    {String(commercial?.health?.days_until_support ?? 'sin límite')}
                  </div>
                </div>
              </div>
              {reminderTypes.length > 0 && (
                <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                  Atención requerida: {reminderTypes.join(', ')}.
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
              <div className="border-b border-zinc-800 px-4 py-3">
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                  Bitácora comercial
                </h2>
              </div>
              <div className="divide-y divide-zinc-800/50 max-h-64 overflow-auto">
                {(commercial?.events ?? []).length === 0 && (
                  <div className="px-4 py-8 text-sm text-zinc-500">
                    Sin eventos comerciales recientes.
                  </div>
                )}
                {(commercial?.events ?? []).map((event, index) => (
                  <div key={`${String(event.id ?? index)}`} className="px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-semibold text-white">
                        {String(event.event_type ?? 'evento')}
                      </div>
                      <div className="text-[11px] font-mono text-zinc-500">
                        {String(event.created_at ?? '-')
                          .slice(0, 19)
                          .replace('T', ' ')}
                      </div>
                    </div>
                    <div className="mt-1 text-zinc-400">
                      Actor: {String(event.actor ?? 'sistema')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              ['Sucursales', String(data?.branchesTotal ?? 0)],
              ['En línea', String(data?.online ?? 0)],
              ['Sin conexión', String(data?.offline ?? 0)],
              [
                'Ventas hoy',
                `$${(data?.salesTodayTotal ?? 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
              ]
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
                <div className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                  {label}
                </div>
                <div className="mt-2 text-2xl font-black text-white">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
              <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                Salud de flota
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">Healthy</div>
                  <div className="mt-1 text-lg font-bold text-emerald-400">
                    {String(healthSummary?.summary?.healthy ?? 0)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">Critical</div>
                  <div className="mt-1 text-lg font-bold text-rose-400">
                    {String(healthSummary?.summary?.critical ?? 0)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">
                    Backups vencidos
                  </div>
                  <div className="mt-1 font-mono text-cyan-300">
                    {String(healthSummary?.summary?.stale_backups ?? 0)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">
                    Deriva versión
                  </div>
                  <div className="mt-1 font-mono text-cyan-300">
                    {String(healthSummary?.summary?.version_drift ?? 0)}
                  </div>
                </div>
              </div>
              <div className="mt-4 text-xs text-zinc-500">
                POS esperado:{' '}
                {String(healthSummary?.summary?.expected_pos_version ?? 'sin referencia')}
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
              <div className="border-b border-zinc-800 px-4 py-3">
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                  Auditoría central
                </h2>
              </div>
              <div className="divide-y divide-zinc-800/50 max-h-64 overflow-auto">
                {(auditFeed?.audit ?? []).length === 0 && (
                  <div className="px-4 py-8 text-sm text-zinc-500">
                    Sin movimientos auditados recientes.
                  </div>
                )}
                {(auditFeed?.audit ?? []).map((entry, index) => (
                  <div key={`${String(entry.id ?? index)}`} className="px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-white">
                        {String(entry.action ?? 'acción')}
                      </div>
                      <div className="text-[11px] font-mono text-zinc-500">
                        {String(entry.created_at ?? '-')
                          .slice(0, 19)
                          .replace('T', ' ')}
                      </div>
                    </div>
                    <div className="mt-1 text-zinc-300">
                      {String(entry.branch_name ?? 'Sucursal desconocida')} •{' '}
                      {String(entry.actor ?? 'sistema')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
            <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
              <Store className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                Sucursales del tenant
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-zinc-900/80 text-xs uppercase tracking-wider text-zinc-500 font-bold">
                  <tr>
                    <th className="px-4 py-2">Sucursal</th>
                    <th className="px-4 py-2">Estado</th>
                    <th className="px-4 py-2">Canal</th>
                    <th className="px-4 py-2">Versión POS</th>
                    <th className="px-4 py-2 text-right">Ventas hoy</th>
                    <th className="px-4 py-2">Último backup</th>
                    <th className="px-4 py-2 text-right">Detalle</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50 text-sm">
                  {branches.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-10 text-center text-zinc-500">
                        {loading ? 'Cargando portfolio...' : 'No hay sucursales disponibles.'}
                      </td>
                    </tr>
                  )}
                  {branches.map((branch, index) => {
                    const online = Boolean(branch.is_online)
                    return (
                      <tr
                        key={String(branch.id ?? index)}
                        className="hover:bg-zinc-800/30 transition-colors"
                      >
                        <td className="px-4 py-2">
                          <div className="font-semibold text-white">
                            {String(branch.branch_name ?? branch.branch_slug ?? '-')}
                          </div>
                          <div className="text-xs text-zinc-500">
                            {String(branch.branch_slug ?? '')}
                          </div>
                        </td>
                        <td
                          className={`px-4 py-2 font-semibold ${online ? 'text-emerald-400' : 'text-rose-400'}`}
                        >
                          {online ? 'En línea' : 'Sin conexión'}
                        </td>
                        <td className="px-4 py-2 text-zinc-300">
                          {String(branch.release_channel ?? '-')}
                        </td>
                        <td className="px-4 py-2 text-zinc-300">
                          {String(branch.pos_version ?? '-')}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-cyan-300">
                          ${Number(branch.sales_today ?? 0).toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-zinc-400">
                          {branch.last_backup
                            ? String(branch.last_backup).slice(0, 19).replace('T', ' ')
                            : 'Sin respaldo'}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => void loadTimeline(Number(branch.id))}
                            className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs font-semibold text-zinc-300"
                          >
                            Timeline
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
            <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">Alertas</h2>
            </div>
            <div className="divide-y divide-zinc-800/50">
              {alerts.length === 0 && (
                <div className="px-4 py-8 text-sm text-zinc-500">
                  Sin alertas activas para este tenant.
                </div>
              )}
              {alerts.map((alert, index) => (
                <div key={String(alert.branch_id ?? index)} className="px-4 py-3 text-sm">
                  <div className="font-semibold text-white">{String(alert.kind ?? 'alerta')}</div>
                  <div className="text-zinc-400">{String(alert.message ?? '')}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
              <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
                <BellRing className="w-4 h-4 text-blue-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                  Centro de eventos
                </h2>
              </div>
              <div className="divide-y divide-zinc-800/50 max-h-[28rem] overflow-auto">
                {events.length === 0 && (
                  <div className="px-4 py-8 text-sm text-zinc-500">
                    Sin eventos recientes para este tenant.
                  </div>
                )}
                {events.map((event, index) => (
                  <div key={`${String(event.event_type)}-${index}`} className="px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-white">
                        {String(event.event_type ?? 'evento')}
                      </div>
                      <div className="text-[11px] font-mono text-zinc-500">
                        {String(event.occurred_at ?? '-')
                          .slice(0, 19)
                          .replace('T', ' ')}
                      </div>
                    </div>
                    <div className="mt-1 text-zinc-300">{String(event.message ?? '')}</div>
                    <div className="mt-1 text-[11px] text-zinc-500">
                      {String(event.branch_name ?? 'Sucursal desconocida')} •{' '}
                      {String(event.source ?? 'sistema')}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
              <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-4 py-3">
                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                  Timeline de sucursal
                </h2>
                <div className="text-xs text-zinc-500">
                  {selectedBranchId ? `Sucursal #${selectedBranchId}` : 'Sin sucursal seleccionada'}
                </div>
              </div>
              {timelineError && (
                <div className="border-b border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                  {timelineError}
                </div>
              )}
              <div className="divide-y divide-zinc-800/50 max-h-[28rem] overflow-auto">
                {timeline.length === 0 && (
                  <div className="px-4 py-8 text-sm text-zinc-500">
                    Selecciona una sucursal para revisar heartbeats recientes.
                  </div>
                )}
                {timeline.map((item, index) => (
                  <div key={`${String(item.heartbeat_id)}-${index}`} className="px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-white">
                        {String(item.status ?? 'unknown')}
                      </div>
                      <div className="text-[11px] font-mono text-zinc-500">
                        {String(item.received_at ?? '-')
                          .slice(0, 19)
                          .replace('T', ' ')}
                      </div>
                    </div>
                    <div className="mt-1 text-zinc-400">
                      Ventas hoy: ${Number(item.sales_today ?? 0).toFixed(2)} • Disco:{' '}
                      {String(item.disk_used_pct ?? '-')}%
                    </div>
                    <div className="mt-1 text-[11px] text-zinc-500">
                      POS {String(item.pos_version ?? '-')} • App {String(item.app_version ?? '-')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
