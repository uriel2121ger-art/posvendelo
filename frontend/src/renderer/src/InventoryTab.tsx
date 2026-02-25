import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, pullTable, adjustStock } from './posApi'

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

  useEffect(() => { setPage(0) }, [query])

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
    return () => { requestIdRef.current++ }
  }, [handleLoad])

  async function handleAdjustStock(): Promise<void> {
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
    const signed = movementType === 'in' ? qty : -qty
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const result = await adjustStock(cfg, {
        product_id: current.id,
        quantity: signed,
        reason: `Ajuste manual ${movementType === 'in' ? 'entrada' : 'salida'}`
      })
      const data = result.data as Record<string, unknown>
      const newStock = Number(data?.new_stock ?? current.stock + signed)
      setRows((prev) => {
        const idx = prev.findIndex((r) => r.sku === targetSku)
        if (idx < 0) return prev
        const copy = [...prev]
        copy[idx] = { ...copy[idx], stock: newStock }
        return copy
      })
      setMessage(
        `Movimiento ${movementType === 'in' ? 'entrada' : 'salida'} aplicado a ${targetSku}. Nuevo stock: ${newStock}`
      )
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
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
              <tr><td colSpan={3} className="py-12 text-center text-zinc-600">
                {query.trim() ? 'Sin resultados para la busqueda.' : 'Sin datos de inventario. Haz clic en Cargar.'}
              </td></tr>
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
              >&laquo; Ant</button>
              <span className="text-zinc-400">{page + 1} / {totalPages}</span>
              <button
                className="px-2 py-1 rounded border border-zinc-700 hover:bg-zinc-800 disabled:opacity-30 transition-colors"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >Sig &raquo;</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
