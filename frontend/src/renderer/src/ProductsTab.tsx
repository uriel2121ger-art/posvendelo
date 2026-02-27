import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, pullTable, syncTable, getProductCategories, scanProduct, getLowStockProducts } from './posApi'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  stock: number
  category?: string
}

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeProduct(raw: Record<string, unknown>): Product | null {
  const sku = String(raw.sku ?? raw.code ?? '').trim()
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!sku || !name) return null
  const price = toNumber(raw.price ?? raw.sale_price ?? raw.precio)
  const stock = toNumber(raw.stock)
  return {
    id: (raw.id as number | string | undefined) ?? sku,
    sku,
    name,
    price,
    stock,
    category: String(raw.category ?? '').trim() || undefined
  }
}

export default function ProductsTab(): ReactElement {
  const [products, setProducts] = useState<Product[]>([])
  const [query, setQuery] = useState('')
  const [selectedSku, setSelectedSku] = useState<string | null>(null)
  const [sku, setSku] = useState('')
  const [name, setName] = useState('')
  const [price, setPrice] = useState('0')
  const [stock, setStock] = useState('0')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Productos (F3): carga, alta, edicion y baja logica funcional.'
  )
  const requestIdRef = useRef(0)
  const scanInputRef = useRef<HTMLInputElement>(null)
  const lastScanEnterRef = useRef(0)
  const [categories, setCategories] = useState<string[]>([])
  const [categoryFilter, setCategoryFilter] = useState('')
  const [scanSku, setScanSku] = useState('')
  const [lowStock, setLowStock] = useState<Record<string, unknown>[]>([])
  const [showLowStock, setShowLowStock] = useState(false)

  const PAGE_SIZE = 50
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    let result = products
    if (categoryFilter) {
      result = result.filter((p) => {
        const raw = p as unknown as Record<string, unknown>
        return String(raw.category ?? '').toLowerCase() === categoryFilter.toLowerCase()
      })
    }
    const q = query.trim().toLowerCase()
    if (q) {
      result = result.filter(
        (p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q)
      )
    }
    return result
  }, [products, query, categoryFilter])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated = useMemo(() => {
    const start = page * PAGE_SIZE
    return filtered.slice(start, start + PAGE_SIZE)
  }, [filtered, page])

  // Reset page when search or category filter changes
  useEffect(() => {
    setPage(0)
  }, [query, categoryFilter])

  const handleLoad = useCallback(async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const rows = await pullTable('products', cfg)
      if (requestIdRef.current !== reqId) return
      const normalized = rows.map(normalizeProduct).filter((item): item is Product => item !== null)
      setProducts(normalized)
      setMessage(`Productos cargados: ${normalized.length}`)
    } catch (error) {
      if (requestIdRef.current !== reqId) return
      setMessage((error as Error).message)
    } finally {
      if (requestIdRef.current === reqId) setBusy(false)
    }
  }, [])

  useEffect(() => {
    void handleLoad()
    void (async () => {
      try {
        const cfg = loadRuntimeConfig()
        const raw = await getProductCategories(cfg)
        const data = (raw.data ?? raw.categories ?? []) as unknown[]
        setCategories(data.map((c) => String((c as Record<string, unknown>)?.name ?? c)).filter(Boolean))
      } catch { /* categories are optional */ }
    })()
    return () => {
      requestIdRef.current++
    }
  }, [handleLoad])

  async function handleCreate(): Promise<void> {
    if (busy) return
    if (!sku.trim() || !name.trim()) {
      setMessage('SKU y nombre son obligatorios.')
      return
    }
    const parsedPrice = toNumber(price)
    if (parsedPrice < 0) {
      setMessage('El precio no puede ser negativo.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const product = {
        id: sku.trim(),
        sku: sku.trim(),
        name: name.trim(),
        price: toNumber(price),
        stock: Math.max(0, Math.floor(toNumber(stock))),
        deleted: false
      }
      const isUpdate = Boolean(selectedSku)
      await syncTable('products', [product], cfg)
      setProducts((prev) => {
        const idx = prev.findIndex((p) => p.sku === product.sku)
        if (idx >= 0) {
          const copy = [...prev]
          copy[idx] = product
          return copy
        }
        return [product, ...prev]
      })
      setSelectedSku(null)
      setSku('')
      setName('')
      setPrice('0')
      setStock('0')
      setMessage(
        isUpdate ? `Producto actualizado: ${product.sku}` : `Producto guardado: ${product.sku}`
      )
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(): Promise<void> {
    if (busy) return
    if (!selectedSku) {
      setMessage('Selecciona un producto para eliminar.')
      return
    }
    const target = products.find((item) => item.sku === selectedSku)
    if (!target) {
      setMessage('Producto no encontrado. Recarga la lista.')
      return
    }
    if (!window.confirm(`¿Eliminar producto "${target.name}" (${target.sku})?`)) return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await syncTable(
        'products',
        [
          {
            id: target.id ?? target.sku,
            sku: target.sku,
            name: target.name,
            price: target.price,
            stock: target.stock,
            deleted: true
          }
        ],
        cfg
      )
      setProducts((prev) => prev.filter((item) => item.sku !== selectedSku))
      setSelectedSku(null)
      setSku('')
      setName('')
      setPrice('0')
      setStock('0')
      setMessage(`Producto eliminado: ${target.sku}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function selectProduct(product: Product): void {
    setSelectedSku(product.sku)
    setSku(product.sku)
    setName(product.name)
    setPrice(product.price.toFixed(2))
    setStock(String(product.stock))
    setMessage(`Producto seleccionado: ${product.sku}`)
  }

  async function handleScan(): Promise<void> {
    const target = scanSku.trim()
    if (!target) return
    try {
      const cfg = loadRuntimeConfig()
      const raw = await scanProduct(cfg, target)
      const data = (raw.data ?? raw) as Record<string, unknown>
      const found = normalizeProduct(data)
      if (found) {
        selectProduct(found)
        setMessage(`Producto escaneado: ${found.sku}`)
      } else {
        setMessage(`Sin resultados para SKU: ${target}`)
      }
    } catch (err) {
      setMessage((err as Error).message)
    }
    setScanSku('')
  }

  async function loadLowStock(): Promise<void> {
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getLowStockProducts(cfg, 50)
      const data = (raw.data ?? raw.products ?? []) as Record<string, unknown>[]
      setLowStock(Array.isArray(data) ? data : [])
      setShowLowStock(true)
      setMessage(`Productos con stock bajo: ${Array.isArray(data) ? data.length : 0}`)
    } catch (err) {
      setMessage((err as Error).message)
    }
  }

  function resetForm(): void {
    setSelectedSku(null)
    setSku('')
    setName('')
    setPrice('0')
    setStock('0')
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_1fr_160px_160px_auto_auto_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="SKU"
          value={sku}
          onChange={(e) => setSku(e.target.value)}
          disabled={Boolean(selectedSku)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Nombre producto"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Precio"
          type="number"
          min={0}
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Stock"
          type="number"
          min={0}
          value={stock}
          onChange={(e) => setStock(e.target.value)}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void handleCreate()}
          disabled={busy}
        >
          {selectedSku ? 'Actualizar' : 'Guardar'}
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={() => void handleLoad()}
          disabled={busy}
        >
          Cargar
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-amber-600/20 border border-amber-500/30 px-5 py-2.5 font-bold text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.1)] hover:bg-amber-600/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={resetForm}
          disabled={busy}
        >
          Nuevo
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void handleDelete()}
          disabled={busy || !selectedSku}
        >
          Eliminar
        </button>
      </div>

      <div className="flex gap-2 border-b border-zinc-800 bg-zinc-900 px-4 py-2 items-center">
        {categories.length > 0 && (
          <select
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-300"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">Todas categorias</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}
        <input
          ref={scanInputRef}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-300 w-36 placeholder:text-zinc-600"
          placeholder="SKU a escanear"
          value={scanSku}
          onChange={(e) => setScanSku(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              e.stopPropagation()
              const now = Date.now()
              if (now - lastScanEnterRef.current < 150) return
              lastScanEnterRef.current = now
              void handleScan()
              setTimeout(() => scanInputRef.current?.focus(), 0)
            }
          }}
        />
        <button
          className="px-3 py-1.5 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 text-xs font-bold hover:bg-blue-600/40 transition-colors"
          onClick={() => void handleScan()}
          disabled={!scanSku.trim()}
        >
          Escanear
        </button>
        <button
          className="px-3 py-1.5 rounded-lg bg-amber-600/20 border border-amber-500/30 text-amber-400 text-xs font-bold hover:bg-amber-600/40 transition-colors"
          onClick={() => (showLowStock ? setShowLowStock(false) : void loadLowStock())}
        >
          {showLowStock ? 'Ocultar Stock Bajo' : 'Stock Bajo'}
        </button>
      </div>

      {showLowStock && lowStock.length > 0 && (
        <div className="mx-4 mt-2 max-h-40 overflow-auto rounded-xl border border-amber-500/30 bg-amber-950/20 p-3">
          <p className="text-xs font-bold text-amber-400 mb-2 uppercase">Productos con Stock Bajo</p>
          <div className="grid grid-cols-3 gap-1 text-xs">
            {lowStock.map((p, i) => (
              <div key={i} className="flex justify-between rounded bg-zinc-900 px-2 py-1">
                <span className="text-zinc-300 truncate">{String((p as Record<string, unknown>).sku ?? (p as Record<string, unknown>).name ?? `#${i}`)}</span>
                <span className="text-amber-400 font-mono ml-2">{String((p as Record<string, unknown>).stock ?? '?')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-b border-zinc-800 bg-zinc-900/50 p-4 mx-4 mb-2 rounded-xl mt-4">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Buscar producto"
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
              <th className="py-4 px-6">Precio</th>
              <th className="py-4 px-6">Stock</th>
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 && (
              <tr>
                <td colSpan={4} className="py-12 text-center text-zinc-600">
                  {query.trim()
                    ? 'Sin resultados para la busqueda.'
                    : 'Sin productos. Haz clic en Cargar.'}
                </td>
              </tr>
            )}
            {paginated.map((p) => (
              <tr
                key={String(p.id)}
                className={`border-b border-zinc-800/50 cursor-pointer transition-colors text-sm ${
                  selectedSku === p.sku
                    ? 'bg-blue-900/20 border-l-4 border-blue-500'
                    : 'hover:bg-zinc-800/40'
                }`}
                onClick={() => selectProduct(p)}
              >
                <td className="py-4 px-6 font-medium">{p.sku}</td>
                <td className="py-4 px-6 font-medium">{p.name}</td>
                <td className="py-4 px-6 font-medium">${p.price.toFixed(2)}</td>
                <td className="py-4 px-6 font-medium">{p.stock}</td>
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
