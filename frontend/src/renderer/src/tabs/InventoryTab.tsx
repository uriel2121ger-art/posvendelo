import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useConfirm } from '../components/ConfirmDialog'
import { Search, Package, X, ArrowRightLeft, AlertCircle, RefreshCw, BarChart2, Check } from 'lucide-react'
import {
  loadRuntimeConfig,
  pullTable,
  adjustStock,
  getStockAlerts,
  getInventoryMovements
} from '../posApi'
import { useFocusTrap } from '../hooks/useFocusTrap'

type InventoryRow = {
  id: number
  sku: string
  name: string
  stock: number
}

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeProduct(raw: Record<string, unknown>): InventoryRow | null {
  const id = toNumber(raw.id)
  const sku = String(raw.sku ?? raw.code ?? '').trim()
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!id || !sku || !name) return null
  return {
    id,
    sku,
    name,
    stock: Math.max(0, Math.floor(toNumber(raw.stock)))
  }
}

export default function InventoryTab(): ReactElement {
  const confirm = useConfirm()
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [query, setQuery] = useState('')
  const [sku, setSku] = useState('')
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [movementQty, setMovementQty] = useState('1')
  const [movementType, setMovementType] = useState<'in' | 'out' | 'shrinkage'>('in')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Inventario (F4): carga y movimientos de entrada/salida funcional.'
  )
  const requestIdRef = useRef(0)
  const skuInputRef = useRef<HTMLInputElement>(null)
  const drawerRef = useRef<HTMLDivElement>(null)

  useFocusTrap(drawerRef, isDrawerOpen)
  const lastSkuEnterRef = useRef(0)
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([])
  const [showAlerts, setShowAlerts] = useState(false)
  const [movements, setMovements] = useState<Record<string, unknown>[]>([])
  const [showMovements, setShowMovements] = useState(false)
  const [movFilterType, setMovFilterType] = useState<'all' | 'IN' | 'OUT'>('all')

  const PAGE_SIZE = 50
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((r) => r.sku.toLowerCase().includes(q) || r.name.toLowerCase().includes(q))
  }, [rows, query])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated = useMemo(() => {
    const start = page * PAGE_SIZE
    return filtered.slice(start, start + PAGE_SIZE)
  }, [filtered, page])

  useEffect(() => {
    setPage(0)
  }, [query])

  // Clamp page when filtered data shrinks (e.g. after reload with fewer items)
  useEffect(() => {
    const maxPage = Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1)
    setPage((p) => Math.min(p, maxPage))
  }, [filtered.length])

  const handleLoad = useCallback(async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const products = await pullTable('products', cfg)
      if (requestIdRef.current !== reqId) return
      const normalized = products
        .map(normalizeProduct)
        .filter((item): item is InventoryRow => item !== null)
      setRows(normalized)
      setMessage(`Inventario cargado: ${normalized.length} productos.`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }, [])

  useEffect(() => {
    void handleLoad()
    const reqRef = requestIdRef
    return () => {
      reqRef.current++
    }
  }, [handleLoad])

  async function handleAdjustStock(): Promise<void> {
    if (busy) return
    const targetSku = sku.trim()
    if (!targetSku) {
      setMessage('Captura un SKU para ajustar inventario.')
      return
    }
    const qty = Math.max(1, Math.floor(Math.abs(toNumber(movementQty))))
    const current = rows.find((r) => r.sku === targetSku)
    if (!current) {
      setMessage(`SKU no encontrado en inventario: ${targetSku}`)
      return
    }
    const isOut = movementType === 'out' || movementType === 'shrinkage'
    if (isOut && qty > toNumber(current.stock)) {
      setMessage(
        `Stock insuficiente. Actual: ${current.stock}, ${movementType === 'shrinkage' ? 'merma' : 'salida'} solicitada: ${qty}`
      )
      return
    }
    const signed = movementType === 'in' ? qty : -qty
    const typeLabel =
      movementType === 'in' ? 'entrada' : movementType === 'shrinkage' ? 'merma' : 'salida'
    if (
      !(await confirm(`¿Aplicar ${typeLabel} de ${qty} unidades a ${targetSku}?`, {
        variant: 'warning',
        title: 'Confirmar movimiento'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const result = await adjustStock(cfg, {
        product_id: current.id,
        quantity: signed,
        reason: movementType === 'shrinkage' ? `Merma: ${targetSku}` : `Ajuste manual ${typeLabel}`
      })
      const data = result.data as Record<string, unknown>
      const rawNew = Number(data?.new_stock ?? current.stock + signed)
      const newStock = Number.isFinite(rawNew) ? rawNew : Math.max(0, current.stock + signed)
      setRows((prev) => {
        const idx = prev.findIndex((r) => r.sku === targetSku)
        if (idx < 0) return prev
        const copy = [...prev]
        copy[idx] = { ...copy[idx], stock: newStock }
        return copy
      })
      setSku('')
      setMovementQty('1')
      setIsDrawerOpen(false)
      setMessage(`Movimiento ${typeLabel} aplicado a ${targetSku}. Nuevo stock: ${newStock}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function loadAlerts(): Promise<void> {
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getStockAlerts(cfg)
      const data = (raw.data ?? raw.alerts ?? []) as Record<string, unknown>[]
      setAlerts(Array.isArray(data) ? data : [])
      setShowAlerts(true)
      setMessage(`Alertas cargadas: ${Array.isArray(data) ? data.length : 0}`)
    } catch (err) {
      setMessage((err as Error).message)
    }
  }

  async function loadMovements(): Promise<void> {
    try {
      const cfg = loadRuntimeConfig()
      const typeParam = movFilterType === 'all' ? undefined : movFilterType
      const raw = await getInventoryMovements(cfg, undefined, typeParam, 100)
      const data = (raw.data ?? raw.movements ?? []) as Record<string, unknown>[]
      setMovements(Array.isArray(data) ? data : [])
      setShowMovements(true)
      setMessage(`Movimientos cargados: ${Array.isArray(data) ? data.length : 0}`)
    } catch (err) {
      setMessage((err as Error).message)
    }
  }

  return (
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-hidden relative">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Header Area */}
        <div className="px-8 py-6 border-b border-zinc-900 bg-zinc-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Package className="w-7 h-7 text-indigo-500" />
              Gestión de Inventario
            </h1>
            <p className="text-zinc-500 text-sm mt-1">{rows.length} productos en catálogo</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => void handleLoad()}
              disabled={busy}
              className="flex items-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 px-4 py-2.5 rounded-xl font-semibold transition-colors border border-zinc-800"
            >
              <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} />
              <span>Sincronizar</span>
            </button>
            <button
              onClick={() => {
                setSku('')
                setIsDrawerOpen(true)
                setTimeout(() => skuInputRef.current?.focus(), 100)
              }}
              disabled={busy}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl font-bold shadow-[0_4px_20px_-5px_rgba(79,70,229,0.4)] transition-all hover:-translate-y-0.5"
            >
              <ArrowRightLeft className="w-5 h-5" />
              <span>Nuevo Movimiento</span>
            </button>
          </div>
        </div>

        {/* Toolbar (Search & Panels) */}
        <div className="px-8 py-4 bg-zinc-950/50 flex flex-wrap items-center gap-4 shrink-0">
          <div className="relative flex-1 min-w-[300px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
            <input
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-11 pr-4 text-sm font-medium focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-zinc-600"
              placeholder="Buscar por SKU o Nombre para consultar..."
              value={query}
              // eslint-disable-next-line no-control-regex
              onChange={(e) => setQuery(e.target.value.replace(/[\x00-\x1F\x7F-\x9F]/g, ''))}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  e.stopPropagation()
                  const q = query.trim().toLowerCase()
                  if (!q) return
                  const match = rows.find((r) => r.sku.toLowerCase() === q)
                  if (match) {
                    setSku(match.sku)
                    setIsDrawerOpen(true)
                  }
                }
              }}
            />
          </div>

          <div className="flex bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden p-1">
            <button
              onClick={() => (showAlerts ? setShowAlerts(false) : void loadAlerts())}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2 ${showAlerts ? 'bg-amber-500/20 text-amber-500' : 'hover:bg-zinc-800 text-zinc-400'}`}
            >
              <AlertCircle className="w-4 h-4" />
              Alertas de Stock
            </button>
            <div className="w-px bg-zinc-800 my-1 mx-1"></div>
            <button
              onClick={() => (showMovements ? setShowMovements(false) : void loadMovements())}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2 ${showMovements ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-zinc-800 text-zinc-400'}`}
            >
              <BarChart2 className="w-4 h-4" />
              Historial
            </button>
          </div>
        </div>

        {/* Info Panels (Collapsible) */}
        <div className="shrink-0 flex flex-col gap-2 px-8">
          {showAlerts && alerts.length > 0 && (
            <div className="max-h-40 overflow-y-auto rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
              <p className="text-xs font-bold text-amber-400 mb-3 uppercase tracking-wider flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> Alertas de Inventario
              </p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
                {alerts.map((a, i) => (
                  <div
                    key={i}
                    className="flex justify-between items-center rounded-lg bg-zinc-900 px-3 py-2 border border-amber-900/30"
                  >
                    <span className="text-zinc-300 truncate pr-2 font-medium">
                      {String(a.sku ?? a.product_name ?? `#${i}`)}
                    </span>
                    <span className="text-rose-400 font-mono font-bold bg-rose-950/50 px-2 py-0.5 rounded">
                      {String(a.stock ?? a.current_stock ?? '?')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {showMovements && (
            <div className="max-h-64 overflow-hidden flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 relative">
              <div className="flex items-center justify-between mb-3 border-b border-zinc-800 pb-2">
                <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <BarChart2 className="w-4 h-4" /> Historial de Movimientos
                </p>
                <div className="flex items-center gap-2">
                  <select
                    className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-zinc-300 focus:outline-none focus:border-indigo-500"
                    value={movFilterType}
                    onChange={(e) => setMovFilterType(e.target.value as 'all' | 'IN' | 'OUT')}
                  >
                    <option value="all">Todos</option>
                    <option value="IN">Solo Entradas</option>
                    <option value="OUT">Solo Salidas</option>
                  </select>
                  <button
                    className="p-1 rounded bg-zinc-800 text-zinc-400 hover:text-white"
                    onClick={() => void loadMovements()}
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {movements.length === 0 ? (
                <p className="text-center text-zinc-500 py-4 text-sm">
                  No hay movimientos recientes.
                </p>
              ) : (
                <div className="flex-1 overflow-y-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="sticky top-0 bg-zinc-900 shadow-md text-zinc-500">
                      <tr>
                        <th className="px-3 py-2 font-medium">Fecha</th>
                        <th className="px-3 py-2 font-medium">Producto</th>
                        <th className="px-3 py-2 font-medium">Tipo</th>
                        <th className="px-3 py-2 font-medium">Cant</th>
                        <th className="px-3 py-2 font-medium">Razón</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {movements.map((m, i) => (
                        <tr key={i} className="hover:bg-zinc-800/30">
                          <td className="px-3 py-2 text-zinc-400 font-mono">
                            {String(m.timestamp ?? m.created_at ?? '-')
                              .slice(0, 16)
                              .replace('T', ' ')}
                          </td>
                          <td className="px-3 py-2 text-zinc-200 truncate max-w-[150px]">
                            {String(m.product_name ?? m.sku ?? m.product_id ?? '-')}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${String(m.movement_type ?? m.type) === 'IN' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}
                            >
                              {String(m.movement_type ?? m.type ?? '-')}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono font-bold text-zinc-300">
                            {String(m.quantity ?? '-')}
                          </td>
                          <td className="px-3 py-2 text-zinc-500 truncate max-w-[200px]">
                            {String(m.reason ?? '-')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Master List (Data Grid) */}
        <div className="flex-1 overflow-y-auto px-8 py-4">
          <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold">
                  <th className="px-6 py-4 w-40">SKU / CÓDIGO</th>
                  <th className="px-6 py-4">Producto</th>
                  <th className="px-6 py-4 text-right w-32">Stock Actual</th>
                  <th className="px-6 py-4 w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-16 text-center text-zinc-500">
                      <Package className="w-12 h-12 mx-auto mb-3 opacity-20" />
                      <p className="text-lg font-medium text-zinc-400">Sin datos de inventario</p>
                      <p className="text-sm mt-1">
                        {query.trim() ? 'Intenta con otra búsqueda.' : 'Haz clic en "Sincronizar".'}
                      </p>
                    </td>
                  </tr>
                ) : (
                  paginated.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => {
                        setSku(r.sku)
                        setIsDrawerOpen(true)
                      }}
                      className="group hover:bg-zinc-800/40 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 font-mono text-sm text-zinc-400 group-hover:text-indigo-400 transition-colors">
                        {r.sku}
                      </td>
                      <td className="px-6 py-4 font-medium text-zinc-200">{r.name}</td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`inline-flex items-center justify-center min-w-[3rem] px-3 py-1.5 rounded-lg text-sm font-bold shadow-inner ${r.stock <= 5 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-zinc-950 text-emerald-400 border border-zinc-800'}`}
                        >
                          {r.stock}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="p-2 -mr-2 text-zinc-600 hover:text-indigo-400 opacity-0 group-hover:opacity-100 transition-all rounded-lg hover:bg-indigo-500/10">
                          <ArrowRightLeft className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer info */}
        <div className="bg-zinc-950 border-t border-zinc-900 px-8 py-3 flex items-center justify-between shrink-0 text-sm">
          <span className="text-zinc-500">{message}</span>
          <div className="flex items-center gap-4">
            <span className="text-zinc-600">{filtered.length} resultados en total</span>
            {totalPages > 1 && (
              <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-2 py-1 hover:bg-zinc-800 rounded text-zinc-400 disabled:opacity-30"
                >
                  &laquo;
                </button>
                <span className="px-3 text-xs font-bold text-zinc-300">
                  {page + 1} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-2 py-1 hover:bg-zinc-800 rounded text-zinc-400 disabled:opacity-30"
                >
                  &raquo;
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drawer Overlay */}
      {isDrawerOpen && (
        <div
          className="absolute inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity flex justify-end"
          onClick={() => setIsDrawerOpen(false)}
        >
          {/* Drawer Panel */}
          <div
            ref={drawerRef}
            className="w-[450px] bg-zinc-950 border-l border-zinc-800 h-full shadow-2xl flex flex-col transform transition-transform duration-300 translate-x-0 cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/30">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <ArrowRightLeft className="w-5 h-5 text-indigo-500" />
                Logística & Movimiento
              </h2>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* SKU Input & Validator */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  ESCANEAR PRODUCTO A MOVER (SKU)
                </label>
                <div className="relative">
                  <input
                    ref={skuInputRef}
                    placeholder="Ej: 7501234567890"
                    value={sku}
                    onChange={(e) => setSku(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        const now = Date.now()
                        if (now - lastSkuEnterRef.current < 150) return
                        lastSkuEnterRef.current = now
                        const target = sku.trim()
                        if (!target) return
                        const found = rows.find((r) => r.sku.toLowerCase() === target.toLowerCase())
                        if (found) {
                          setSku(found.sku)
                          setMessage(`Producto listo: ${found.name}`)
                        } else {
                          setMessage(`SKU no encontrado: ${target}`)
                        }
                      }
                    }}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 text-sm font-medium text-white focus:outline-none focus:border-indigo-500 pl-4 pr-10 shadow-inner"
                  />
                  {rows.find((r) => r.sku.toLowerCase() === sku.trim().toLowerCase()) && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 bg-emerald-500 rounded-full flex items-center justify-center">
                      <Check className="w-2.5 h-2.5 text-zinc-950 stroke-[3]" />
                    </div>
                  )}
                </div>
                {/* Product Info Preview */}
                {(() => {
                  const targetLine = sku.trim().toLowerCase()
                  if (!targetLine) return null
                  const match = rows.find((r) => r.sku.toLowerCase() === targetLine)
                  if (!match)
                    return <div className="mt-2 text-xs text-rose-400">Producto no reconocido.</div>
                  return (
                    <div className="mt-3 bg-indigo-950/20 border border-indigo-900/30 rounded-xl p-4">
                      <div className="text-sm font-semibold text-zinc-200 line-clamp-2">
                        {match.name}
                      </div>
                      <div className="mt-2 text-xs font-mono text-indigo-300">
                        Stock Actual:{' '}
                        <span className="font-bold text-lg ml-1 text-white">{match.stock}</span>
                      </div>
                    </div>
                  )
                })()}
              </div>

              <div className="h-px bg-zinc-900 w-full" />

              {/* Operation Type */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">
                  TIPO DE OPERACIÓN
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => setMovementType('in')}
                    className={`py-3 rounded-xl border font-bold text-xs uppercase tracking-wide flex flex-col items-center justify-center gap-1 transition-all ${movementType === 'in' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:bg-zinc-800'}`}
                  >
                    <span>+</span> Entrada
                  </button>
                  <button
                    onClick={() => setMovementType('out')}
                    className={`py-3 rounded-xl border font-bold text-xs uppercase tracking-wide flex flex-col items-center justify-center gap-1 transition-all ${movementType === 'out' ? 'bg-rose-500/20 border-rose-500/50 text-rose-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:bg-zinc-800'}`}
                  >
                    <span>-</span> Salida
                  </button>
                  <button
                    onClick={() => setMovementType('shrinkage')}
                    className={`py-3 rounded-xl border font-bold text-xs uppercase tracking-wide flex flex-col items-center justify-center gap-1 transition-all ${movementType === 'shrinkage' ? 'bg-amber-500/20 border-amber-500/50 text-amber-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:bg-zinc-800'}`}
                  >
                    <span>⊗</span> Merma
                  </button>
                </div>
              </div>

              {/* Quantity */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  CANTIDAD A APLICAR
                </label>
                <div className="flex bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-inner">
                  <button
                    onClick={() => setMovementQty((q) => String(Math.max(1, Number(q) - 1)))}
                    className="px-5 text-zinc-400 hover:bg-zinc-800 hover:text-white font-bold text-lg"
                  >
                    -
                  </button>
                  <input
                    type="number"
                    value={movementQty}
                    onChange={(e) => setMovementQty(e.target.value)}
                    min={1}
                    className="w-full bg-transparent py-4 text-center text-xl font-black text-white focus:outline-none"
                  />
                  <button
                    onClick={() => setMovementQty((q) => String(Number(q) + 1))}
                    className="px-5 text-zinc-400 hover:bg-zinc-800 hover:text-white font-bold text-lg"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-zinc-800 bg-zinc-900/80">
              <button
                onClick={() => void handleAdjustStock()}
                disabled={busy || !sku.trim()}
                className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold tracking-widest shadow-[0_0_20px_rgba(79,70,229,0.3)] transition-all active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2 text-lg"
              >
                {busy ? 'APLICANDO...' : 'CONFIRMAR MOVIMIENTO'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
