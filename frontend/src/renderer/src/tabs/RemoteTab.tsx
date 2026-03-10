import type { ReactElement } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useConfirm, usePrompt } from '../components/ConfirmDialog'
import {
  loadRuntimeConfig,
  getLiveSales,
  getTurnStatusRemote,
  remoteOpenDrawer,
  remoteCancelSale,
  remoteChangePrice,
  remoteStockUpdate,
  sendNotification,
  getPendingNotifications,
  getPendingRemoteRequests,
  resolvePendingRemoteRequest,
  getUserRole
} from '../posApi'
import {
  Radio,
  Activity,
  RefreshCw,
  DoorOpen,
  Tag,
  Send,
  BellRing,
  Target,
  Ban,
  Check,
  X
} from 'lucide-react'
import { toNumber } from '../utils/numbers'
import {
  enqueueRemoteAction,
  loadQueuedRemoteActions,
  removeQueuedRemoteAction,
  type QueuedRemoteAction
} from '../utils/offlineQueue'

export default function RemoteTab(): ReactElement {
  const confirm = useConfirm()
  const prompt = usePrompt()
  const [turnStatus, setTurnStatus] = useState<Record<string, unknown> | null>(null)
  const [liveSales, setLiveSales] = useState<Record<string, unknown>[]>([])
  const [notifications, setNotifications] = useState<Record<string, unknown>[]>([])
  const [pendingRequests, setPendingRequests] = useState<Record<string, unknown>[]>([])
  const [pendingRequestsStatus, setPendingRequestsStatus] = useState<
    'idle' | 'loading' | 'ready' | 'unsupported'
  >('idle')
  const [queuedActions, setQueuedActions] = useState<QueuedRemoteAction[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Panel remoto: control y monitoreo en tiempo real.')
  const liveRef = useRef(0)
  const role = getUserRole()
  const canAdmin = role === 'owner' || role === 'admin' || role === 'manager'

  // Change price form
  const [cpSku, setCpSku] = useState('')
  const [cpPrice, setCpPrice] = useState('')
  const [cpReason, setCpReason] = useState('')
  const [cancelSaleId, setCancelSaleId] = useState('')
  const [cancelReason, setCancelReason] = useState('')
  const [stockSku, setStockSku] = useState('')
  const [stockQty, setStockQty] = useState('')
  const [stockOperation, setStockOperation] = useState('add')
  const [stockReason, setStockReason] = useState('')

  // Notification form
  const [ntTitle, setNtTitle] = useState('')
  const [ntBody, setNtBody] = useState('')
  const [ntType, setNtType] = useState('info')
  const [requestNotes, setRequestNotes] = useState<Record<number, string>>({})

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

  const loadPendingRequests = useCallback(async (): Promise<void> => {
    setPendingRequestsStatus('loading')
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getPendingRemoteRequests(cfg)
      const envelope = (raw.data ?? raw) as Record<string, unknown>
      const data = (envelope.requests ?? []) as Record<string, unknown>[]
      setPendingRequests(Array.isArray(data) ? data : [])
      setPendingRequestsStatus('ready')
    } catch (error) {
      const nextMessage = (error as Error).message
      if (/404|not found/i.test(nextMessage)) {
        setPendingRequests([])
        setPendingRequestsStatus('unsupported')
        setMessage('Este nodo todavía no expone solicitudes remotas pendientes.')
        return
      }
      setPendingRequestsStatus('idle')
      setMessage(nextMessage)
    }
  }, [])

  useEffect(() => {
    setQueuedActions(loadQueuedRemoteActions())
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

  function isConnectivityError(error: unknown): boolean {
    const message =
      error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase()
    return (
      message.includes('no se pudo conectar') ||
      message.includes('failed to fetch') ||
      message.includes('network') ||
      message.includes('load failed') ||
      message.includes('tiempo de espera')
    )
  }

  function queueAction(
    kind: QueuedRemoteAction['kind'],
    summary: string,
    payload: Record<string, unknown>
  ): void {
    setQueuedActions(
      enqueueRemoteAction({
        kind,
        summary,
        payload
      })
    )
  }

  async function handleFlushQueue(): Promise<void> {
    const currentQueue = loadQueuedRemoteActions()
    if (currentQueue.length === 0) {
      setMessage('No hay acciones pendientes por sincronizar.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      for (const action of currentQueue) {
        if (action.kind === 'price_change') {
          await remoteChangePrice(
            cfg,
            action.payload as { sku: string; new_price: number; reason: string }
          )
        } else if (action.kind === 'stock_update') {
          await remoteStockUpdate(
            cfg,
            action.payload as { sku: string; quantity: number; operation: string; reason: string }
          )
        } else if (action.kind === 'notification') {
          await sendNotification(
            cfg,
            action.payload as { title: string; body: string; notification_type: string }
          )
        }
        setQueuedActions(removeQueuedRemoteAction(action.id))
      }
      setMessage('Cola offline sincronizada correctamente.')
      void loadNotifications()
    } catch (error) {
      setQueuedActions(loadQueuedRemoteActions())
      setMessage(
        isConnectivityError(error)
          ? 'La sincronización sigue pendiente por falta de conectividad.'
          : (error as Error).message
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleOpenDrawer(): Promise<void> {
    if (!canAdmin) {
      setMessage('Sin permisos para esta acción.')
      return
    }
    if (
      !(await confirm('¿Abrir cajón de dinero remotamente?', {
        variant: 'warning',
        title: 'Abrir cajón remoto'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await remoteOpenDrawer(cfg)
      setMessage('Cajón abierto remotamente.')
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
      setMessage('SKU, precio y razón son obligatorios.')
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
      if (isConnectivityError(error)) {
        queueAction('price_change', `Cambio de precio ${cpSku.trim()}`, {
          sku: cpSku.trim(),
          new_price: toNumber(cpPrice),
          reason: cpReason.trim()
        })
        setMessage('Sin conexión: cambio de precio encolado para sincronización.')
      } else {
        setMessage((error as Error).message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function handleStockUpdate(): Promise<void> {
    if (!canAdmin) {
      setMessage('Sin permisos para actualizar stock.')
      return
    }
    if (!stockSku.trim() || !stockQty.trim() || !stockReason.trim()) {
      setMessage('SKU, cantidad y motivo son obligatorios.')
      return
    }
    const payload = {
      sku: stockSku.trim(),
      quantity: toNumber(stockQty),
      operation: stockOperation,
      reason: stockReason.trim()
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await remoteStockUpdate(cfg, payload)
      setMessage(`Stock de ${stockSku.trim()} actualizado.`)
      setStockSku('')
      setStockQty('')
      setStockReason('')
    } catch (error) {
      if (isConnectivityError(error)) {
        queueAction('stock_update', `Ajuste de stock ${stockSku.trim()}`, payload)
        setMessage('Sin conexión: ajuste de stock encolado para sincronización.')
      } else {
        setMessage((error as Error).message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function handleSendNotification(): Promise<void> {
    if (!ntTitle.trim() || !ntBody.trim()) {
      setMessage('Título y cuerpo son obligatorios.')
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
      setMessage('Notificación enviada.')
      setNtTitle('')
      setNtBody('')
    } catch (error) {
      if (isConnectivityError(error)) {
        queueAction('notification', `Mensaje ${ntTitle.trim()}`, {
          title: ntTitle.trim(),
          body: ntBody.trim(),
          notification_type: ntType
        })
        setMessage('Sin conexión: mensaje encolado para sincronización.')
      } else {
        setMessage((error as Error).message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function handleCancelRemoteSale(): Promise<void> {
    if (!canAdmin) {
      setMessage('Sin permisos para cancelar ventas.')
      return
    }
    if (!cancelSaleId.trim()) {
      setMessage('Captura el ID o folio de la venta a cancelar.')
      return
    }
    const saleIdNumber = Number(cancelSaleId.trim())
    if (!Number.isInteger(saleIdNumber) || saleIdNumber <= 0) {
      setMessage('La cancelación remota requiere un ID numérico de venta.')
      return
    }
    if (
      !(await confirm(
        `¿Autorizar cancelación remota de la venta ${cancelSaleId.trim()}? Esta acción revierte stock y pagos asociados.`,
        {
          variant: 'danger',
          title: 'Cancelación supervisada'
        }
      ))
    ) {
      return
    }
    const managerPin = await prompt(
      'Ingresa el PIN de gerente/autorización para confirmar la cancelación.',
      {
        title: 'PIN de autorización',
        placeholder: 'PIN de gerente',
        confirmText: 'Cancelar venta',
        variant: 'warning'
      }
    )
    if (managerPin == null) return

    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await remoteCancelSale(cfg, {
        sale_id: saleIdNumber,
        manager_pin: managerPin.trim(),
        reason: cancelReason.trim() || 'Cancelación remota supervisada'
      })
      setMessage(`Venta ${cancelSaleId.trim()} cancelada remotamente.`)
      setCancelSaleId('')
      setCancelReason('')
      void loadLiveSales()
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleResolvePendingRequest(requestId: number, approved: boolean): Promise<void> {
    const request = pendingRequests.find((item) => Number(item.id) === requestId)
    if (!request) {
      setMessage('Solicitud remota no encontrada.')
      return
    }
    if (
      !(await confirm(
        `¿${approved ? 'Aprobar' : 'Rechazar'} la solicitud ${String(
          request.request_type ?? 'remota'
        )}?`,
        {
          variant: approved ? 'warning' : 'danger',
          title: approved ? 'Aprobar solicitud remota' : 'Rechazar solicitud remota'
        }
      ))
    )
      return

    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await resolvePendingRemoteRequest(cfg, requestId, approved, requestNotes[requestId])
      setPendingRequests((prev) => prev.filter((item) => Number(item.id) !== requestId))
      setMessage(approved ? 'Solicitud remota aplicada.' : 'Solicitud remota rechazada.')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto w-full p-4 lg:p-6 space-y-6 pb-32">
          {/* Header — mismo patrón que Productos/Clientes */}
          <div className="flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4 relative">
            <div
              className="absolute right-0 top-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[100px] pointer-events-none"
              aria-hidden
            />
            <div className="min-w-0 shrink flex items-center gap-2">
              <Radio className="w-6 h-6 text-emerald-500 shrink-0" />
              <h1 className="text-xl font-bold text-white truncate">
                Monitoreo y Control Satelital
              </h1>
            </div>
            <div className="flex items-center gap-2 shrink-0 flex-nowrap relative z-10">
              <div className="bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-lg text-xs font-bold font-mono tracking-wider text-zinc-400">
                <span className={busy ? 'text-amber-500' : 'text-emerald-500'}>
                  {busy ? 'TRABAJANDO' : 'ESTABLE'}
                </span>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-6">
                  <Target className="w-4 h-4 text-emerald-500" /> Ajuste remoto de stock
                </h2>
                <div className="space-y-3">
                  <input
                    className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm text-zinc-200 focus:border-emerald-500 focus:outline-none transition-all placeholder:text-zinc-600"
                    placeholder="SKU o código"
                    value={stockSku}
                    onChange={(e) => setStockSku(e.target.value)}
                  />
                  <div className="flex gap-3">
                    <input
                      className="w-1/3 bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm text-zinc-200 focus:border-emerald-500 focus:outline-none transition-all placeholder:text-zinc-600"
                      placeholder="Cantidad"
                      type="number"
                      value={stockQty}
                      onChange={(e) => setStockQty(e.target.value)}
                    />
                    <select
                      className="w-1/3 bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-xs font-bold uppercase tracking-wider focus:border-emerald-500 focus:outline-none transition-all"
                      value={stockOperation}
                      onChange={(e) => setStockOperation(e.target.value)}
                    >
                      <option value="add">Agregar</option>
                      <option value="subtract">Restar</option>
                      <option value="set">Fijar</option>
                    </select>
                    <input
                      className="w-1/3 bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:border-emerald-500 focus:outline-none transition-all placeholder:text-zinc-600"
                      placeholder="Motivo"
                      value={stockReason}
                      onChange={(e) => setStockReason(e.target.value)}
                    />
                  </div>
                  <button
                    className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)] disabled:opacity-50"
                    onClick={() => void handleStockUpdate()}
                    disabled={busy || !canAdmin}
                  >
                    Aplicar ajuste de stock
                  </button>
                </div>
              </div>
              <button
                onClick={() => {
                  loadTurnStatus()
                  loadLiveSales()
                  loadNotifications()
                }}
                disabled={busy}
                className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-emerald-400 border border-zinc-800 px-3 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} /> Actualizar
              </button>
            </div>
          </div>

          {/* Global Notifications */}
          {!canAdmin && (
            <div className="bg-amber-500/10 border border-amber-500/20 text-amber-500 px-4 py-3 rounded-2xl flex items-start gap-3 text-sm font-semibold max-w-2xl">
              <Radio className="w-5 h-5 shrink-0 mt-0.5" />
              <p>
                Tiene rol de solo lectura. La modificación remota, apertura de cajón y control de
                sucursales están deshabilitados.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Col: Turn & Live Sales */}
            <div className="lg:col-span-2 space-y-8">
              {/* Turn Status KPI */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6 relative overflow-hidden flex flex-col justify-center">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-6">
                  <Target className="w-4 h-4 text-emerald-500" /> Operador Actual (Terminal
                  Principal)
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
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6 flex flex-col">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-500" /> Flujo de transacciones en
                    tiempo real
                  </h2>
                  <div className="flex gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse delay-75"></span>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse delay-150"></span>
                  </div>
                </div>

                <div className="overflow-x-auto max-h-[400px] overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead className="sticky top-0 bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold z-10">
                      <tr>
                        <th className="px-4 py-2">Folio Tx</th>
                        <th className="px-4 py-2">Hora local</th>
                        <th className="px-4 py-2">Forma de pago</th>
                        <th className="px-4 py-2 text-right">Monto</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {liveSales.length === 0 && (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-4 py-12 text-center text-sm text-zinc-500 font-mono"
                          >
                            Esperando primera transmisión...
                          </td>
                        </tr>
                      )}
                      {liveSales.map((sale, i) => (
                        <tr
                          key={String(sale.id ?? i)}
                          className="hover:bg-zinc-800/40 transition-colors group"
                        >
                          <td className="px-4 py-2 text-sm font-mono font-bold text-zinc-300">
                            {String(sale.folio ?? sale.id ?? '-')}
                          </td>
                          <td className="px-4 py-2 text-sm font-mono text-zinc-500">
                            {String(sale.timestamp ?? sale.created_at ?? '-').slice(11, 19)}
                          </td>
                          <td className="px-4 py-2 text-sm font-bold uppercase text-zinc-400">
                            {String(sale.payment_method ?? '-')}
                          </td>
                          <td className="px-4 py-2 text-sm font-mono font-bold text-emerald-400 text-right group-hover:scale-105 transition-transform origin-right">
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
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-6">
                  <DoorOpen className="w-4 h-4 text-amber-500" /> Control remoto
                </h2>
                <button
                  className="w-full flex items-center justify-center gap-3 bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 rounded-xl p-4 transition-colors disabled:opacity-50 group"
                  onClick={() => void handleOpenDrawer()}
                  disabled={busy || !canAdmin}
                >
                  <DoorOpen className="w-6 h-6 text-zinc-400 group-hover:text-amber-500 transition-colors" />
                  <div className="text-left flex-1">
                    <p className="text-sm font-bold text-white">Apertura forzada</p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
                      Disparar pulso 24V al cajón
                    </p>
                  </div>
                </button>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-6">
                  <Ban className="w-4 h-4 text-rose-500" /> Cancelación supervisada
                </h2>
                <div className="space-y-3">
                  <input
                    className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm text-zinc-200 focus:border-rose-500 focus:outline-none transition-all placeholder:text-zinc-600"
                    placeholder="ID o folio de la venta"
                    value={cancelSaleId}
                    onChange={(e) => setCancelSaleId(e.target.value)}
                  />
                  <input
                    className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:border-rose-500 focus:outline-none transition-all placeholder:text-zinc-600"
                    placeholder="Motivo de cancelación"
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                  />
                  <button
                    className="w-full mt-2 bg-rose-600 hover:bg-rose-500 text-white font-bold py-3 rounded-xl transition-all disabled:opacity-50"
                    onClick={() => void handleCancelRemoteSale()}
                    disabled={busy || !canAdmin}
                  >
                    Autorizar cancelación
                  </button>
                </div>
              </div>

              {/* Price Change Component */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-6">
                  <Tag className="w-4 h-4 text-blue-500" /> Actualización de precios
                </h2>
                <div className="space-y-3">
                  <input
                    className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm text-zinc-200 focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                    placeholder="SKU o código de barras"
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
                    Aplicar actualización
                  </button>
                </div>
              </div>

              {/* Operations Broadcast */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-6">
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
                  <div className="mt-6 pt-6 border-t border-zinc-800">
                    <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                      <BellRing className="w-3 h-3" /> Entregas Pendientes
                    </h3>
                    <div className="space-y-2 max-h-32 overflow-y-auto pr-1">
                      {notifications.map((n, i) => (
                        <div
                          key={String(n.id ?? i)}
                          className="bg-zinc-950 rounded-2xl p-3 border border-zinc-800 flex items-start gap-3"
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

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider">
                    Solicitudes remotas pendientes
                  </h2>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-amber-500/15 px-2 py-1 text-[11px] font-bold text-amber-400">
                      {pendingRequests.length}
                    </span>
                    <button
                      type="button"
                      onClick={() => void loadPendingRequests()}
                      disabled={busy || pendingRequestsStatus === 'loading'}
                      className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 text-[11px] font-semibold text-zinc-300 disabled:opacity-50"
                    >
                      <RefreshCw
                        className={`h-3.5 w-3.5 ${pendingRequestsStatus === 'loading' ? 'animate-spin' : ''}`}
                      />
                      Cargar
                    </button>
                  </div>
                </div>
                {pendingRequestsStatus === 'unsupported' ? (
                  <p className="text-sm text-zinc-500">
                    El backend actual no soporta esta bandeja local. La pantalla principal sigue
                    operativa.
                  </p>
                ) : pendingRequestsStatus === 'idle' ? (
                  <p className="text-sm text-zinc-500">
                    Carga esta bandeja bajo demanda para evitar ruido en nodos que aún no soportan
                    solicitudes locales.
                  </p>
                ) : pendingRequests.length === 0 ? (
                  <p className="text-sm text-zinc-500">
                    No hay solicitudes pendientes de aprobación local.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {pendingRequests.map((request) => {
                      const requestId = Number(request.id)
                      const payload =
                        request.payload && typeof request.payload === 'object'
                          ? (request.payload as Record<string, unknown>)
                          : {}
                      return (
                        <div
                          key={requestId}
                          className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-zinc-200">
                                {String(request.request_type ?? 'solicitud remota')}
                              </p>
                              <p className="text-[11px] text-zinc-500">
                                SKU: {String(payload.sku ?? payload.product_sku ?? '—')} • Nuevo
                                precio:{' '}
                                {payload.new_price != null ? `$${String(payload.new_price)}` : '—'}
                              </p>
                            </div>
                            <span className="text-[11px] uppercase tracking-wider text-zinc-500">
                              {String(request.status ?? 'pending')}
                            </span>
                          </div>
                          <input
                            type="text"
                            placeholder="Notas de aprobación o rechazo"
                            value={requestNotes[requestId] ?? ''}
                            onChange={(e) =>
                              setRequestNotes((prev) => ({ ...prev, [requestId]: e.target.value }))
                            }
                            className="mt-3 w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600"
                          />
                          <div className="mt-3 flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => void handleResolvePendingRequest(requestId, false)}
                              disabled={busy || !canAdmin}
                              className="inline-flex items-center gap-1 rounded-lg border border-rose-800 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-300 disabled:opacity-50"
                            >
                              <X className="h-3.5 w-3.5" />
                              Rechazar
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleResolvePendingRequest(requestId, true)}
                              disabled={busy || !canAdmin}
                              className="inline-flex items-center gap-1 rounded-lg border border-emerald-800 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 disabled:opacity-50"
                            >
                              <Check className="h-3.5 w-3.5" />
                              Aprobar
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider">
                    Cola offline
                  </h2>
                  <button
                    type="button"
                    onClick={() => void handleFlushQueue()}
                    disabled={busy || queuedActions.length === 0}
                    className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs font-semibold text-zinc-300 disabled:opacity-50"
                  >
                    Sincronizar {queuedActions.length > 0 ? `(${queuedActions.length})` : ''}
                  </button>
                </div>
                {queuedActions.length === 0 ? (
                  <p className="text-sm text-zinc-500">No hay acciones pendientes.</p>
                ) : (
                  <div className="space-y-2">
                    {queuedActions.map((action) => (
                      <div
                        key={action.id}
                        className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2"
                      >
                        <p className="text-sm font-semibold text-zinc-200">{action.summary}</p>
                        <p className="text-[11px] text-zinc-500">
                          {action.kind} • {action.createdAt.slice(0, 19).replace('T', ' ')}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
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
