import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useConfirm } from './components/ConfirmDialog'
import { Search, Plus, X, AlertCircle, RefreshCw, PackageOpen, Edit2 } from 'lucide-react'
import {
  loadRuntimeConfig,
  pullTable,
  syncTable,
  getProductCategories,
  getLowStockProducts,
  searchSatCodes,
  getSatUnits,
  createProduct,
  updateProduct
} from './posApi'
import { useFocusTrap } from './hooks/useFocusTrap'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  stock: number
  category?: string
  satClaveProdServ?: string
  satClaveUnidad?: string
  satDescripcion?: string
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
    category: String(raw.category ?? '').trim() || undefined,
    satClaveProdServ:
      String(raw.sat_clave_prod_serv ?? raw.satClaveProdServ ?? '').trim() || undefined,
    satClaveUnidad: String(raw.sat_clave_unidad ?? raw.satClaveUnidad ?? '').trim() || undefined,
    satDescripcion: String(raw.sat_descripcion ?? raw.satDescripcion ?? '').trim() || undefined
  }
}

export default function ProductsTab(): ReactElement {
  const confirm = useConfirm()
  const [products, setProducts] = useState<Product[]>([])
  const [query, setQuery] = useState('')
  const [selectedSku, setSelectedSku] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [sku, setSku] = useState('')
  const [name, setName] = useState('')
  const [price, setPrice] = useState('0')
  const [stock, setStock] = useState('0')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Productos (F3): carga, alta, edicion y baja logica funcional.'
  )
  const requestIdRef = useRef(0)
  const skuFormRef = useRef<HTMLInputElement>(null)
  const nameFormRef = useRef<HTMLInputElement>(null)
  const drawerRef = useRef<HTMLDivElement>(null)

  useFocusTrap(drawerRef, isDrawerOpen)
  const [categories, setCategories] = useState<string[]>([])
  const [categoryFilter, setCategoryFilter] = useState('')
  const [lowStock, setLowStock] = useState<Record<string, unknown>[]>([])
  const [showLowStock, setShowLowStock] = useState(false)
  const [satCode, setSatCode] = useState('01010101')
  const [satUnit, setSatUnit] = useState('H87')
  const [satDesc, setSatDesc] = useState('')
  const [satQuery, setSatQuery] = useState('')
  const [satResults, setSatResults] = useState<{ code: string; description: string }[]>([])
  const [satUnits, setSatUnits] = useState<{ code: string; name: string }[]>([])
  const [showSatDropdown, setShowSatDropdown] = useState(false)
  const satSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

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
        setCategories(
          data.map((c) => String((c as Record<string, unknown>)?.name ?? c)).filter(Boolean)
        )
      } catch {
        /* categories are optional */
      }
    })()
    void (async () => {
      try {
        const cfg = loadRuntimeConfig()
        const units = await getSatUnits(cfg)
        if (units.length > 0) setSatUnits(units)
      } catch {
        /* sat units are optional */
      }
    })()
    const reqRef = requestIdRef
    return () => {
      reqRef.current++
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
      const isUpdate = Boolean(selectedSku)
      const payload: Record<string, unknown> = {
        name: name.trim(),
        price: toNumber(price),
        stock: Math.max(0, Math.floor(toNumber(stock))),
        sat_clave_prod_serv: satCode || '01010101',
        sat_clave_unidad: satUnit || 'H87',
        sat_descripcion: satDesc || ''
      }
      if (isUpdate) {
        const target = products.find((p) => p.sku === selectedSku)
        if (target?.id && typeof target.id === 'number') {
          await updateProduct(cfg, target.id, payload)
        } else {
          payload.sku = sku.trim()
          await syncTable('products', [{ ...payload, deleted: false }], cfg)
        }
      } else {
        payload.sku = sku.trim()
        await createProduct(cfg, payload)
      }
      const product: Product = {
        id: products.find((p) => p.sku === sku.trim())?.id ?? sku.trim(),
        sku: sku.trim(),
        name: name.trim(),
        price: toNumber(price),
        stock: Math.max(0, Math.floor(toNumber(stock))),
        satClaveProdServ: satCode || '01010101',
        satClaveUnidad: satUnit || 'H87',
        satDescripcion: satDesc || ''
      }
      setProducts((prev) => {
        const idx = prev.findIndex((p) => p.sku === product.sku)
        if (idx >= 0) {
          const copy = [...prev]
          copy[idx] = { ...prev[idx], ...product }
          return copy
        }
        return [product, ...prev]
      })
      setSelectedSku(null)
      setSku('')
      setName('')
      setPrice('0')
      setStock('0')
      setSatCode('01010101')
      setSatUnit('H87')
      setSatDesc('')
      setSatQuery('')
      setIsDrawerOpen(false)
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
    if (
      !(await confirm(`¿Eliminar producto "${target.name}" (${target.sku})?`, {
        variant: 'danger',
        title: 'Eliminar producto'
      }))
    )
      return
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
      setIsDrawerOpen(false)
      setMessage(`Producto eliminado: ${target.sku}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function selectProduct(product: Product): void {
    setSelectedSku(product.sku)
    setIsDrawerOpen(true)
    setSku(product.sku)
    setName(product.name)
    setPrice(product.price.toFixed(2))
    setStock(String(product.stock))
    setSatCode(product.satClaveProdServ || '01010101')
    setSatUnit(product.satClaveUnidad || 'H87')
    setSatDesc(product.satDescripcion || '')
    setSatQuery(
      product.satClaveProdServ
        ? `${product.satClaveProdServ} - ${product.satDescripcion || ''}`
        : ''
    )
    setMessage(`Producto seleccionado: ${product.sku}`)
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
    setIsDrawerOpen(true)
    setSku('')
    setName('')
    setPrice('0')
    setStock('0')
    setSatCode('01010101')
    setSatUnit('H87')
    setSatDesc('')
    setSatQuery('')
  }

  return (
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-hidden relative">
      {/* Sidebar Tooling (Left) is handled by the global Layout, so this is just the content area */}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Header Area */}
        <div className="px-8 py-6 border-b border-zinc-900 bg-zinc-950 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <PackageOpen className="w-7 h-7 text-blue-500" />
              Catálogo de Productos
            </h1>
            <p className="text-zinc-500 text-sm mt-1">
              {products.length} productos registrados en total
            </p>
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
                resetForm()
                setIsDrawerOpen(true)
              }}
              disabled={busy}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl font-bold shadow-[0_4px_20px_-5px_rgba(37,99,235,0.4)] transition-all hover:-translate-y-0.5"
            >
              <Plus className="w-5 h-5" />
              <span>Nuevo Producto</span>
            </button>
          </div>
        </div>

        {/* Toolbar (Search & Filters) */}
        <div className="px-8 py-4 bg-zinc-950/50 flex flex-wrap items-center gap-4 shrink-0">
          <div className="relative flex-1 min-w-[300px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
            <input
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-11 pr-4 text-sm font-medium focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
              placeholder="Buscar por SKU, Nombre o Código de barras..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {categories.length > 0 && (
            <select
              className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium focus:outline-none focus:border-blue-500 cursor-pointer min-w-[200px]"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">Todas las Categorías</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          )}

          <div className="flex bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden p-1">
            <button
              onClick={() => (showLowStock ? setShowLowStock(false) : void loadLowStock())}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2 ${showLowStock ? 'bg-amber-500/20 text-amber-500' : 'hover:bg-zinc-800 text-zinc-400'}`}
            >
              <AlertCircle className="w-4 h-4" />
              {showLowStock ? 'Ocultar Alertas' : 'Stock Bajo'}
            </button>
          </div>
        </div>

        {showLowStock && lowStock.length > 0 && (
          <div className="mx-8 mt-2 max-h-40 overflow-auto rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 shrink-0">
            <p className="text-xs font-bold text-amber-400 mb-3 uppercase tracking-wider flex items-center gap-2">
              <AlertCircle className="w-4 h-4" /> Alertas de Inventario
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
              {lowStock.map((p, i) => (
                <div
                  key={i}
                  className="flex justify-between items-center rounded-lg bg-zinc-900 px-3 py-2 border border-amber-900/30"
                >
                  <span className="text-zinc-300 truncate pr-2 font-medium">
                    {String(p.sku ?? p.name ?? `#${i}`)}
                  </span>
                  <span className="text-rose-400 font-mono font-bold bg-rose-950/50 px-2 py-0.5 rounded">
                    {String(p.stock ?? '?')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Master List (Data Grid) */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold">
                  <th className="px-6 py-4 w-40">SKU / CÓDIGO</th>
                  <th className="px-6 py-4">Producto</th>
                  <th className="px-6 py-4 text-right w-32">Precio</th>
                  <th className="px-6 py-4 text-right w-32">Stock</th>
                  <th className="px-6 py-4 w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-16 text-center text-zinc-500">
                      <PackageOpen className="w-12 h-12 mx-auto mb-3 opacity-20" />
                      <p className="text-lg font-medium text-zinc-400">
                        No hay productos para mostrar
                      </p>
                      <p className="text-sm mt-1">
                        {query.trim() || categoryFilter
                          ? 'Intenta con otra búsqueda o filtro.'
                          : 'Haz clic en "Sincronizar" o crea uno nuevo.'}
                      </p>
                    </td>
                  </tr>
                ) : (
                  paginated.map((p) => (
                    <tr
                      key={String(p.id)}
                      onClick={() => {
                        selectProduct(p)
                        setIsDrawerOpen(true)
                      }}
                      className="group hover:bg-zinc-800/40 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 font-mono text-sm text-zinc-400 group-hover:text-blue-400 transition-colors">
                        {p.sku}
                      </td>
                      <td className="px-6 py-4 font-medium text-zinc-200">
                        {p.name}{' '}
                        {p.category && (
                          <span className="ml-2 text-[10px] bg-zinc-800 text-zinc-500 px-2 py-0.5 rounded-full">
                            {p.category}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right font-bold text-emerald-400">
                        ${p.price.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`inline-flex items-center justify-center min-w-[2.5rem] px-2 py-1 rounded-lg text-xs font-bold ${p.stock <= 5 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-zinc-800 text-zinc-300'}`}
                        >
                          {p.stock}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="p-2 -mr-2 text-zinc-600 hover:text-blue-400 opacity-0 group-hover:opacity-100 transition-all rounded-lg hover:bg-blue-500/10">
                          <Edit2 className="w-4 h-4" />
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
            <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                {selectedSku ? (
                  <Edit2 className="w-5 h-5 text-blue-500" />
                ) : (
                  <Plus className="w-5 h-5 text-emerald-500" />
                )}
                {selectedSku ? 'Editar Producto' : 'Nuevo Producto'}
              </h2>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  CÓDIGO / SKU
                </label>
                <input
                  ref={skuFormRef}
                  disabled={Boolean(selectedSku)}
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  placeholder="Ej: 7501234567890"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  NOMBRE DEL PRODUCTO
                </label>
                <input
                  ref={nameFormRef}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Coca Cola 600ml"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                    PRECIO DE VENTA
                  </label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 font-bold">
                      $
                    </span>
                    <input
                      type="number"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      min={0}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-8 pr-4 text-sm font-medium text-white focus:outline-none focus:border-blue-500 focus:text-emerald-400 transition-colors"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                    STOCK
                  </label>
                  <input
                    type="number"
                    value={stock}
                    onChange={(e) => setStock(e.target.value)}
                    min={0}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="relative">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  CLAVE SAT PRODUCTO
                </label>
                <input
                  value={satQuery}
                  onChange={(e) => {
                    const q = e.target.value
                    setSatQuery(q)
                    if (satSearchTimer.current) clearTimeout(satSearchTimer.current)
                    if (q.trim().length >= 2) {
                      satSearchTimer.current = setTimeout(() => {
                        void (async () => {
                          try {
                            const cfg = loadRuntimeConfig()
                            const results = await searchSatCodes(cfg, q.trim())
                            setSatResults(results)
                            setShowSatDropdown(results.length > 0)
                          } catch {
                            setSatResults([])
                          }
                        })()
                      }, 300)
                    } else {
                      setSatResults([])
                      setShowSatDropdown(false)
                    }
                  }}
                  onFocus={() => {
                    if (satResults.length > 0) setShowSatDropdown(true)
                  }}
                  placeholder="Buscar: 50161800, bebidas, cremas..."
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-blue-500"
                />
                {satCode && (
                  <span className="absolute right-3 top-9 text-xs text-blue-400 font-mono">
                    {satCode}
                  </span>
                )}
                {showSatDropdown && satResults.length > 0 && (
                  <div className="absolute z-50 w-full mt-1 bg-zinc-900 border border-zinc-700 rounded-xl max-h-48 overflow-y-auto shadow-xl">
                    {satResults.map((r) => (
                      <button
                        key={r.code}
                        type="button"
                        onClick={() => {
                          setSatCode(r.code)
                          setSatDesc(r.description)
                          setSatQuery(`${r.code} - ${r.description}`)
                          setShowSatDropdown(false)
                        }}
                        className="w-full text-left px-4 py-2.5 hover:bg-zinc-800 text-sm transition-colors border-b border-zinc-800/50 last:border-0"
                      >
                        <span className="font-mono text-blue-400">{r.code}</span>
                        <span className="text-zinc-400 ml-2">{r.description}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  CLAVE SAT UNIDAD
                </label>
                <select
                  value={satUnit}
                  onChange={(e) => setSatUnit(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-blue-500 cursor-pointer"
                >
                  {satUnits.length > 0 ? (
                    satUnits.map((u) => (
                      <option key={u.code} value={u.code}>
                        {u.code} - {u.name}
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="H87">H87 - Pieza</option>
                      <option value="E48">E48 - Unidad de servicio</option>
                      <option value="KGM">KGM - Kilogramo</option>
                      <option value="LTR">LTR - Litro</option>
                    </>
                  )}
                </select>
              </div>
            </div>

            <div className="p-6 border-t border-zinc-800 bg-zinc-900/50 flex flex-col gap-3">
              <button
                onClick={() => void handleCreate()}
                disabled={busy}
                className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold tracking-wide shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all active:scale-[0.98] disabled:opacity-50"
              >
                {busy ? 'PROCESANDO...' : 'GUARDAR PRODUCTO'}
              </button>
              {selectedSku && (
                <button
                  onClick={() => void handleDelete()}
                  disabled={busy}
                  className="w-full py-3.5 bg-transparent border border-rose-500/30 text-rose-500 rounded-xl font-bold tracking-wide hover:bg-rose-500/10 transition-colors disabled:opacity-50"
                >
                  ELIMINAR PRODUCTO
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
