import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, pullTable, adjustStock, getStockAlerts, getInventoryMovements } from './posApi'

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
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [query, setQuery] = useState('')
  const [sku, setSku] = useState('')
  const [movementQty, setMovementQty] = useState('1')
  const [movementType, setMovementType] = useState<'in' | 'out'>('in')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Inventario (F4): carga y movimientos de entrada/salida funcional.'
  )
  const requestIdRef = useRef(0)
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
    return () => {
      requestIdRef.current++
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
    if (movementType === 'out' && qty > toNumber(current.stock)) {
      setMessage(`Stock insuficiente. Actual: ${current.stock}, salida solicitada: ${qty}`)
      return
    }
    const signed = movementType === 'in' ? qty : -qty
    if (
      !window.confirm(
        `¿Aplicar ${movementType === 'in' ? 'entrada' : 'salida'} de ${qty} unidades a ${targetSku}?`
      )
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const result = await adjustStock(cfg, {
        product_id: current.id,
        quantity: signed,
        reason: `Ajuste manual ${movementType === 'in' ? 'entrada' : 'salida'}`
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
      setMessage(
        `Movimiento ${movementType === 'in' ? 'entrada' : 'salida'} aplicado a ${targetSku}. Nuevo stock: ${newStock}`
      )
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
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_180px_180px_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="SKU para movimiento"
          value={sku}
          onChange={(e) => setSku(e.target.value)}
        />
        <select
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={movementType}
          onChange={(e) => setMovementType(e.target.value as 'in' | 'out')}
        >
          <option value="in">Entrada</option>
          <option value="out">Salida</option>
        </select>
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Cantidad"
          type="number"
          min={1}
          value={movementQty}
          onChange={(e) => setMovementQty(e.target.value)}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void handleAdjustStock()}
          disabled={busy || !sku.trim()}
        >
          Aplicar
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={() => void handleLoad()}
          disabled={busy}
        >
          Cargar
        </button>
      </div>

      <div className="flex gap-2 border-b border-zinc-800 bg-zinc-900 px-4 py-2">
        <button
          className="px-3 py-1.5 rounded-lg bg-amber-600/20 border border-amber-500/30 text-amber-400 text-xs font-bold hover:bg-amber-600/40 transition-colors"
          onClick={() => (showAlerts ? setShowAlerts(false) : void loadAlerts())}
        >
          {showAlerts ? 'Ocultar Alertas' : 'Ver Alertas Stock'}
        </button>
        <button
          className="px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs font-bold hover:bg-zinc-700 transition-colors"
          onClick={() => (showMovements ? setShowMovements(false) : void loadMovements())}
        >
          {showMovements ? 'Ocultar Movimientos' : 'Historial Movimientos'}
        </button>
        {showMovements && (
          <>
            <select
              className="rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300"
              value={movFilterType}
              onChange={(e) => setMovFilterType(e.target.value as 'all' | 'IN' | 'OUT')}
            >
              <option value="all">Todos</option>
              <option value="IN">Entradas</option>
              <option value="OUT">Salidas</option>
            </select>
            <button
              className="px-2 py-1 rounded-lg bg-zinc-800 text-xs text-zinc-400 hover:text-white transition-colors"
              onClick={() => void loadMovements()}
            >
              Recargar
            </button>
          </>
        )}
      </div>

      {showAlerts && alerts.length > 0 && (
        <div className="mx-4 mt-2 max-h-40 overflow-auto rounded-xl border border-amber-500/30 bg-amber-950/20 p-3">
          <p className="text-xs font-bold text-amber-400 mb-2 uppercase">Alertas de Stock Bajo</p>
          <div className="grid grid-cols-3 gap-1 text-xs">
            {alerts.map((a, i) => (
              <div key={i} className="flex justify-between rounded bg-zinc-900 px-2 py-1">
                <span className="text-zinc-300 truncate">{String(a.sku ?? a.product_name ?? `#${i}`)}</span>
                <span className="text-amber-400 font-mono ml-2">{String(a.stock ?? a.current_stock ?? '?')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {showMovements && movements.length > 0 && (
        <div className="mx-4 mt-2 max-h-48 overflow-auto rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
          <p className="text-xs font-bold text-zinc-400 mb-2 uppercase">Historial de Movimientos</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500">
                <th className="px-2 py-1 text-left">Producto</th>
                <th className="px-2 py-1 text-left">Tipo</th>
                <th className="px-2 py-1 text-left">Cant</th>
                <th className="px-2 py-1 text-left">Razon</th>
                <th className="px-2 py-1 text-left">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((m, i) => (
                <tr key={i} className="border-b border-zinc-900">
                  <td className="px-2 py-1 truncate max-w-[120px]">{String(m.product_name ?? m.sku ?? m.product_id ?? '-')}</td>
                  <td className={`px-2 py-1 font-bold ${String(m.movement_type ?? m.type) === 'IN' ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {String(m.movement_type ?? m.type ?? '-')}
                  </td>
                  <td className="px-2 py-1 font-mono">{String(m.quantity ?? '-')}</td>
                  <td className="px-2 py-1 truncate max-w-[140px]">{String(m.reason ?? '-')}</td>
                  <td className="px-2 py-1">{String(m.timestamp ?? m.created_at ?? '-').slice(0, 19).replace('T', ' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="border-b border-zinc-800 bg-zinc-900/50 p-4 mx-4 mb-2 rounded-xl mt-4">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Buscar por SKU o nombre"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)]">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm">
              <th className="py-4 px-6">SKU</th>
              <th className="py-4 px-6">Nombre</th>
              <th className="py-4 px-6">Stock</th>
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 && (
              <tr>
                <td colSpan={3} className="py-12 text-center text-zinc-600">
                  {query.trim()
                    ? 'Sin resultados para la busqueda.'
                    : 'Sin datos de inventario. Haz clic en Cargar.'}
                </td>
              </tr>
            )}
            {paginated.map((r) => (
              <tr
                key={r.id}
                className={`border-b border-zinc-800/50 cursor-pointer transition-colors text-sm ${
                  sku === r.sku
                    ? 'bg-blue-900/20 border-l-4 border-blue-500'
                    : 'hover:bg-zinc-800/40'
                }`}
                onClick={() => setSku(r.sku)}
              >
                <td className="py-4 px-6 font-medium">{r.sku}</td>
                <td className="py-4 px-6 font-medium">{r.name}</td>
                <td className="py-4 px-6 font-medium">{r.stock}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 flex items-center justify-between">
        <span>{message}</span>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-zinc-500">{filtered.length} resultados</span>
          {totalPages > 1 && (
            <>
              <button
                className="px-2 py-1 rounded border border-zinc-700 hover:bg-zinc-800 disabled:opacity-30 transition-colors"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                &laquo; Ant
              </button>
              <span className="text-zinc-400">
                {page + 1} / {totalPages}
              </span>
              <button
                className="px-2 py-1 rounded border border-zinc-700 hover:bg-zinc-800 disabled:opacity-30 transition-colors"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                Sig &raquo;
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
