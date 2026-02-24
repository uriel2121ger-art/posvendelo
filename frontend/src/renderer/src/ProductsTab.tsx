import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, pullTable, syncTable } from './posApi'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  stock: number
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
    stock
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products
    return products.filter(
      (p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q)
    )
  }, [products, query])

  const handleLoad = useCallback(async (): Promise<void> => {
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const rows = await pullTable('products', cfg)
      const normalized = rows.map(normalizeProduct).filter((item): item is Product => item !== null)
      setProducts(normalized)
      setMessage(`Productos cargados: ${normalized.length}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    void handleLoad()
  }, [handleLoad])

  async function handleCreate(): Promise<void> {
    if (!sku.trim() || !name.trim()) {
      setMessage('SKU y nombre son obligatorios.')
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
      setProducts((prev) => [product, ...prev.filter((p) => p.sku !== product.sku)])
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
    if (!selectedSku) {
      setMessage('Selecciona un producto para eliminar.')
      return
    }
    const target = products.find((item) => item.sku === selectedSku)
    if (!target) return
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
    setPrice(String(product.price))
    setStock(String(product.stock))
    setMessage(`Producto seleccionado: ${product.sku}`)
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
          disabled={busy}
        >
          Eliminar
        </button>
      </div>

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
            {filtered.map((p) => (
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

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
