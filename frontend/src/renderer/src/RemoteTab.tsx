import type { ReactElement } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
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
  const role = (() => { try { return localStorage.getItem('titan.role') ?? 'cashier' } catch { return 'cashier' } })()
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
    return () => {
      liveRef.current++
      clearInterval(interval)
    }
  }, [loadTurnStatus, loadLiveSales, loadNotifications])

  async function handleOpenDrawer(): Promise<void> {
    if (!canAdmin) { setMessage('Sin permisos para esta acción.'); return }
    if (!await confirm('¿Abrir cajon de dinero remotamente?', { variant: 'warning', title: 'Abrir cajon remoto' })) return
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
    if (!canAdmin) { setMessage('Sin permisos para cambiar precios.'); return }
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
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Turn Status */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Estado del Turno</h2>
            <button
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm font-medium transition-colors"
              onClick={() => void loadTurnStatus()}
            >
              Recargar
            </button>
          </div>
          {turnStatus ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-zinc-400">Estado</p>
                <p className="font-semibold">{String(turnStatus.status ?? turnStatus.state ?? '-')}</p>
              </div>
              <div>
                <p className="text-zinc-400">Operador</p>
                <p className="font-semibold">{String(turnStatus.operator ?? turnStatus.opened_by ?? '-')}</p>
              </div>
              <div>
                <p className="text-zinc-400">Ventas</p>
                <p className="font-semibold">{String(turnStatus.sales_count ?? 0)}</p>
              </div>
              <div>
                <p className="text-zinc-400">Total</p>
                <p className="font-semibold">${toNumber(turnStatus.total_sales).toFixed(2)}</p>
              </div>
            </div>
          ) : (
            <p className="text-zinc-500">Cargando...</p>
          )}
        </div>

        {/* Live Sales */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Ventas en Vivo</h2>
            <span className="text-xs text-zinc-500">Auto-refresh cada 10s</span>
          </div>
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs font-bold uppercase tracking-wider text-zinc-500">
                  <th className="py-2 px-4">Folio</th>
                  <th className="py-2 px-4">Hora</th>
                  <th className="py-2 px-4">Metodo</th>
                  <th className="py-2 px-4 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {liveSales.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-zinc-600">
                      Sin ventas recientes.
                    </td>
                  </tr>
                )}
                {liveSales.map((sale, i) => (
                  <tr key={String(sale.id ?? i)} className="border-b border-zinc-800/50">
                    <td className="py-2 px-4 font-mono">{String(sale.folio ?? sale.id ?? '-')}</td>
                    <td className="py-2 px-4">
                      {String(sale.timestamp ?? sale.created_at ?? '-').slice(11, 19)}
                    </td>
                    <td className="py-2 px-4">{String(sale.payment_method ?? '-')}</td>
                    <td className="py-2 px-4 text-right">${toNumber(sale.total).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Remote Actions */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
          <h2 className="text-lg font-bold mb-4">Acciones Remotas</h2>
          <div className="space-y-4">
            <button
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50"
              onClick={() => void handleOpenDrawer()}
              disabled={busy}
            >
              Abrir Cajon
            </button>

            <div className="border-t border-zinc-800 pt-4">
              <h3 className="text-sm font-semibold mb-2 text-zinc-400">Cambiar Precio</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <input
                  className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
                  placeholder="SKU"
                  value={cpSku}
                  onChange={(e) => setCpSku(e.target.value)}
                />
                <input
                  className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
                  placeholder="Nuevo precio"
                  type="number"
                  min={0}
                  value={cpPrice}
                  onChange={(e) => setCpPrice(e.target.value)}
                />
                <input
                  className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
                  placeholder="Razon"
                  value={cpReason}
                  onChange={(e) => setCpReason(e.target.value)}
                />
                <button
                  className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50"
                  onClick={() => void handleChangePrice()}
                  disabled={busy}
                >
                  Aplicar
                </button>
              </div>
            </div>

            <div className="border-t border-zinc-800 pt-4">
              <h3 className="text-sm font-semibold mb-2 text-zinc-400">Enviar Notificacion</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <input
                  className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
                  placeholder="Titulo"
                  value={ntTitle}
                  onChange={(e) => setNtTitle(e.target.value)}
                />
                <input
                  className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
                  placeholder="Mensaje"
                  value={ntBody}
                  onChange={(e) => setNtBody(e.target.value)}
                />
                <select
                  className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all"
                  value={ntType}
                  onChange={(e) => setNtType(e.target.value)}
                >
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="alert">Alerta</option>
                </select>
                <button
                  className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50"
                  onClick={() => void handleSendNotification()}
                  disabled={busy}
                >
                  Enviar
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Pending Notifications */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Notificaciones Pendientes</h2>
            <button
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm font-medium transition-colors"
              onClick={() => void loadNotifications()}
            >
              Recargar
            </button>
          </div>
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs font-bold uppercase tracking-wider text-zinc-500">
                  <th className="py-2 px-4">Titulo</th>
                  <th className="py-2 px-4">Tipo</th>
                  <th className="py-2 px-4">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {notifications.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-4 text-center text-zinc-600">
                      Sin notificaciones pendientes.
                    </td>
                  </tr>
                )}
                {notifications.map((n, i) => (
                  <tr key={String(n.id ?? i)} className="border-b border-zinc-800/50">
                    <td className="py-2 px-4">{String(n.title ?? '-')}</td>
                    <td className="py-2 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-bold ${
                          String(n.notification_type ?? n.type) === 'alert'
                            ? 'bg-rose-500/20 text-rose-400'
                            : String(n.notification_type ?? n.type) === 'warning'
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-blue-500/20 text-blue-400'
                        }`}
                      >
                        {String(n.notification_type ?? n.type ?? 'info')}
                      </span>
                    </td>
                    <td className="py-2 px-4 text-zinc-400">
                      {String(n.created_at ?? n.timestamp ?? '-').slice(0, 19)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
