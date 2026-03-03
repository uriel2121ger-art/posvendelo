import type { ReactElement } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useConfirm } from './components/ConfirmDialog'
import {
  loadRuntimeConfig,
  getLiveSales,
  getTurnStatusRemote,
  remoteOpenDrawer,
  remoteChangePrice,
  sendNotification,
  getPendingNotifications
} from './posApi'
import { Radio, Activity, RefreshCw, DoorOpen, Tag, Send, BellRing, Target } from 'lucide-react'

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export default function RemoteTab(): ReactElement {
  const confirm = useConfirm()
  const [turnStatus, setTurnStatus] = useState<Record<string, unknown> | null>(null)
  const [liveSales, setLiveSales] = useState<Record<string, unknown>[]>([])
  const [notifications, setNotifications] = useState<Record<string, unknown>[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Panel remoto: control y monitoreo en tiempo real.')
  const liveRef = useRef(0)
  const role = (() => {
    try {
      return localStorage.getItem('titan.role') ?? 'cashier'
    } catch {
      return 'cashier'
    }
  })()
  const canAdmin = role === 'owner' || role === 'admin' || role === 'manager'

  // Change price form
  const [cpSku, setCpSku] = useState('')
  const [cpPrice, setCpPrice] = useState('')
  const [cpReason, setCpReason] = useState('')

  // Notification form
  const [ntTitle, setNtTitle] = useState('')
  const [ntBody, setNtBody] = useState('')
  const [ntType, setNtType] = useState('info')

  const loadTurnStatus = useCallback(async (): Promise<void> => {
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getTurnStatusRemote(cfg)
      setTurnStatus((raw.data ?? raw) as Record<string, unknown>)
    } catch (error) {
      setMessage((error as Error).message)
    }
  }, [])

  const loadLiveSales = useCallback(async (): Promise<void> => {
    const reqId = ++liveRef.current
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getLiveSales(cfg, 20)
      if (liveRef.current !== reqId) return
      const envelope = (raw.data ?? raw) as Record<string, unknown>
      const sales = (envelope.sales ?? raw.sales ?? []) as Record<string, unknown>[]
      setLiveSales(Array.isArray(sales) ? sales : [])
    } catch {
      // Silent fail for auto-refresh
    }
  }, [])

  const loadNotifications = useCallback(async (): Promise<void> => {
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getPendingNotifications(cfg)
      const data = (raw.data ?? raw.notifications ?? []) as Record<string, unknown>[]
      setNotifications(Array.isArray(data) ? data : [])
    } catch (error) {
      setMessage((error as Error).message)
    }
  }, [])

  useEffect(() => {
    void loadTurnStatus()
    void loadLiveSales()
    void loadNotifications()
    const interval = setInterval(() => void loadLiveSales(), 10_000)
    const currentLiveRef = liveRef
    return () => {
      currentLiveRef.current++
      clearInterval(interval)
    }
  }, [loadTurnStatus, loadLiveSales, loadNotifications])

  async function handleOpenDrawer(): Promise<void> {
    if (!canAdmin) {
      setMessage('Sin permisos para esta acción.')
      return
    }
    if (
      !(await confirm('¿Abrir cajon de dinero remotamente?', {
        variant: 'warning',
        title: 'Abrir cajon remoto'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await remoteOpenDrawer(cfg)
      setMessage('Cajon abierto remotamente.')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleChangePrice(): Promise<void> {
    if (!canAdmin) {
      setMessage('Sin permisos para cambiar precios.')
      return
    }
    if (!cpSku.trim() || !cpPrice.trim() || !cpReason.trim()) {
      setMessage('SKU, precio y razon son obligatorios.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await remoteChangePrice(cfg, {
        sku: cpSku.trim(),
        new_price: toNumber(cpPrice),
        reason: cpReason.trim()
      })
      setMessage(`Precio de ${cpSku.trim()} actualizado.`)
      setCpSku('')
      setCpPrice('')
      setCpReason('')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleSendNotification(): Promise<void> {
    if (!ntTitle.trim() || !ntBody.trim()) {
      setMessage('Titulo y cuerpo son obligatorios.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await sendNotification(cfg, {
        title: ntTitle.trim(),
        body: ntBody.trim(),
        notification_type: ntType
      })
      setMessage('Notificacion enviada.')
      setNtTitle('')
      setNtBody('')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-y-auto">
      <div className="max-w-6xl mx-auto w-full p-6 md:p-8 space-y-8 pb-32">
        {/* Header - Command Center Style */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-800 pb-6 relative">
          <div className="absolute right-0 top-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[100px] pointer-events-none"></div>
          <div>
            <div className="flex items-center gap-3">
              <div className="relative flex h-8 w-8 items-center justify-center">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-20"></span>
                <Radio className="w-8 h-8 text-emerald-500 relative z-10" />
              </div>
              <h1 className="text-3xl font-black text-white tracking-tight">
                Monitoreo y Control Satelital
              </h1>
            </div>
            <p className="text-zinc-500 mt-2 font-medium flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-500/70" />
              Sincronización en tiempo real. Polling activo (10s).
            </p>
          </div>
          <div className="flex items-center gap-3 relative z-10">
            <div className="bg-zinc-900 border border-zinc-800 px-4 py-2 rounded-xl text-xs font-bold font-mono tracking-widest text-zinc-400">
              PULSO DE RED:{' '}
              <span className={busy ? 'text-amber-500' : 'text-emerald-500'}>
                {busy ? 'TRABAJANDO' : 'ESTABLE'}
              </span>
            </div>
            <button
              onClick={() => {
                loadTurnStatus()
                loadLiveSales()
                loadNotifications()
              }}
              disabled={busy}
              className="flex items-center gap-2 bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-500 border border-emerald-500/20 px-5 py-2.5 rounded-xl font-bold transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Refresh Manual
            </button>
          </div>
        </div>

        {/* Global Notifications */}
        {!canAdmin && (
          <div className="bg-amber-500/10 border border-amber-500/20 text-amber-500 px-5 py-4 rounded-2xl flex items-start gap-3 text-sm font-semibold max-w-2xl">
            <Radio className="w-5 h-5 shrink-0 mt-0.5" />
            <p>
              Atención: Cuentas con rol de solo lectura. Modificación remota, apertura de cajón y
              control de sucursales están deshabilitadas.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Col: Turn & Live Sales */}
          <div className="lg:col-span-2 space-y-8">
            {/* Turn Status KPI */}
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6 relative overflow-hidden flex flex-col justify-center">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-6">
                <Target className="w-4 h-4 text-emerald-500" /> Operador Actual (Terminal Principal)
              </h2>
              {turnStatus ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                      Estado
                    </p>
                    <p className="text-lg font-black text-emerald-400">
                      {String(turnStatus.status ?? turnStatus.state ?? '-')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                      Operador
                    </p>
                    <p className="text-lg font-bold text-white uppercase">
                      {String(turnStatus.operator ?? turnStatus.opened_by ?? '-')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                      Volumen
                    </p>
                    <p className="text-lg font-mono text-zinc-300">
                      {String(turnStatus.sales_count ?? 0)} tx
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-zinc-500 font-bold mb-1">
                      Arqueo Local
                    </p>
                    <p className="text-lg font-mono font-bold text-blue-400">
                      ${toNumber(turnStatus.total_sales).toFixed(2)}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="animate-pulse flex space-x-4">
                  <div className="h-10 bg-zinc-800 rounded w-full"></div>
                </div>
              )}
            </div>

            {/* Live Data Grid */}
            <div className="bg-zinc-900/20 border border-zinc-800/50 rounded-3xl p-6 flex flex-col">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-500" /> Stream de Transacciones Acoplado
                </h2>
                <div className="flex gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse delay-75"></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse delay-150"></span>
                </div>
              </div>

              <div className="overflow-x-auto rounded-xl border border-zinc-800/80 bg-zinc-950 max-h-[400px]">
                <table className="w-full text-left">
                  <thead className="bg-zinc-900 border-b border-zinc-800/80 sticky top-0 z-10">
                    <tr className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                      <th className="py-3 px-4">TX Folio</th>
                      <th className="py-3 px-4">Timestamp L.</th>
                      <th className="py-3 px-4">Modo Pago</th>
                      <th className="py-3 px-4 text-right">Monto</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {liveSales.length === 0 && (
                      <tr>
                        <td
                          colSpan={4}
                          className="py-8 text-center text-zinc-600 font-mono text-xs"
                        >
                          Esperando primera transmisión...
                        </td>
                      </tr>
                    )}
                    {liveSales.map((sale, i) => (
                      <tr
                        key={String(sale.id ?? i)}
                        className="hover:bg-zinc-900/50 transition-colors group"
                      >
                        <td className="py-3 px-4 font-mono font-bold text-zinc-300 text-xs">
                          {String(sale.folio ?? sale.id ?? '-')}
                        </td>
                        <td className="py-3 px-4 text-xs font-mono text-zinc-500">
                          {String(sale.timestamp ?? sale.created_at ?? '-').slice(11, 19)}
                        </td>
                        <td className="py-3 px-4 text-xs font-bold uppercase text-zinc-400">
                          {String(sale.payment_method ?? '-')}
                        </td>
                        <td className="py-3 px-4 font-mono font-bold text-emerald-400 text-right text-xs group-hover:scale-110 transition-transform origin-right">
                          ${toNumber(sale.total).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right Col: Actions & Comms */}
          <div className="space-y-6">
            {/* Trigger Override */}
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-6">
                <DoorOpen className="w-4 h-4 text-amber-500" /> Override Remoto
              </h2>
              <button
                className="w-full flex items-center justify-center gap-3 bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 rounded-xl p-4 transition-colors disabled:opacity-50 group"
                onClick={() => void handleOpenDrawer()}
                disabled={busy || !canAdmin}
              >
                <DoorOpen className="w-6 h-6 text-zinc-400 group-hover:text-amber-500 transition-colors" />
                <div className="text-left flex-1">
                  <p className="text-sm font-bold text-white">Apertura Forzada</p>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
                    Discutir pulso 24V al cajón
                  </p>
                </div>
              </button>
            </div>

            {/* Price Change Component */}
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-6">
                <Tag className="w-4 h-4 text-blue-500" /> Despliegue de Precios
              </h2>
              <div className="space-y-3">
                <input
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm text-zinc-200 focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                  placeholder="SKU o Código de Barras"
                  value={cpSku}
                  onChange={(e) => setCpSku(e.target.value)}
                />
                <div className="flex gap-3">
                  <input
                    className="w-1/2 bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-mono font-bold text-emerald-400 text-sm focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                    placeholder="$ Nuevo"
                    type="number"
                    min={0}
                    value={cpPrice}
                    onChange={(e) => setCpPrice(e.target.value)}
                  />
                  <input
                    className="w-1/2 bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                    placeholder="Justificación"
                    value={cpReason}
                    onChange={(e) => setCpReason(e.target.value)}
                  />
                </div>
                <button
                  className="w-full mt-2 bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all shadow-[0_0_15px_rgba(37,99,235,0.2)] disabled:opacity-50"
                  onClick={() => void handleChangePrice()}
                  disabled={busy || !canAdmin}
                >
                  Push Actualización
                </button>
              </div>
            </div>

            {/* Operations Broadcast */}
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-6">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-6">
                <Send className="w-4 h-4 text-purple-500" /> Mensajería a Caja
              </h2>
              <div className="space-y-3">
                <input
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-bold text-sm text-zinc-200 focus:border-purple-500 focus:outline-none transition-all placeholder:text-zinc-600"
                  placeholder="Asunto"
                  value={ntTitle}
                  onChange={(e) => setNtTitle(e.target.value)}
                />
                <input
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:border-purple-500 focus:outline-none transition-all placeholder:text-zinc-600"
                  placeholder="Cuerpo del mensaje..."
                  value={ntBody}
                  onChange={(e) => setNtBody(e.target.value)}
                />
                <div className="flex gap-3">
                  <select
                    className="w-1/2 bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-bold text-xs uppercase tracking-wider focus:border-purple-500 focus:outline-none transition-all"
                    value={ntType}
                    onChange={(e) => setNtType(e.target.value)}
                  >
                    <option value="info" className="text-blue-500">
                      Informativo
                    </option>
                    <option value="warning" className="text-amber-500">
                      Advertencia
                    </option>
                    <option value="alert" className="text-rose-500">
                      Urgencia
                    </option>
                  </select>
                  <button
                    className="w-1/2 bg-purple-600 hover:bg-purple-500 text-white font-bold py-3 rounded-xl transition-all shadow-[0_0_15px_rgba(147,51,234,0.2)] disabled:opacity-50"
                    onClick={() => void handleSendNotification()}
                    disabled={busy || !canAdmin}
                  >
                    Transmitir
                  </button>
                </div>
              </div>

              {/* Mini notification history */}
              {notifications.length > 0 && (
                <div className="mt-6 pt-6 border-t border-zinc-800/80">
                  <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <BellRing className="w-3 h-3" /> Entregas Pendientes
                  </h3>
                  <div className="space-y-2 max-h-32 overflow-y-auto pr-1">
                    {notifications.map((n, i) => (
                      <div
                        key={String(n.id ?? i)}
                        className="bg-zinc-950 rounded-lg p-3 border border-zinc-800/50 flex items-start gap-3"
                      >
                        <div
                          className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                            String(n.notification_type ?? n.type) === 'alert'
                              ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]'
                              : String(n.notification_type ?? n.type) === 'warning'
                                ? 'bg-amber-500'
                                : 'bg-blue-500'
                          }`}
                        ></div>
                        <div>
                          <p className="text-xs font-bold text-zinc-300">
                            {String(n.title ?? '-')}
                          </p>
                          <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
                            {String(n.created_at ?? n.timestamp ?? '-').slice(0, 19)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Persistent Status Bar */}
      {message && message !== 'Panel remoto: control y monitoreo en tiempo real.' && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-zinc-900 border border-zinc-700 text-white px-6 py-3 rounded-2xl shadow-2xl flex items-center gap-3 animate-fade-in-up">
          <span className="text-sm font-semibold truncate">{message}</span>
        </div>
      )}
    </div>
  )
}
