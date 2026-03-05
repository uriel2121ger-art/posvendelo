import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useConfirm } from '../components/ConfirmDialog'
import {
  Search,
  Plus,
  X,
  AlertCircle,
  RefreshCw,
  PackageOpen,
  Edit2,
  Download,
  Upload,
  ChevronDown
} from 'lucide-react'
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
} from '../posApi'
import { useFocusTrap } from '../hooks/useFocusTrap'
import * as XLSX from 'xlsx'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  stock: number
  category?: string
  barcode?: string
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
    barcode: String(raw.barcode ?? '').trim() || undefined,
    satClaveProdServ:
      String(raw.sat_clave_prod_serv ?? raw.satClaveProdServ ?? '').trim() || undefined,
    satClaveUnidad: String(raw.sat_clave_unidad ?? raw.satClaveUnidad ?? '').trim() || undefined,
    satDescripcion: String(raw.sat_descripcion ?? raw.satDescripcion ?? '').trim() || undefined
  }
}

// ─── Exportar / Importar CSV ─────────────────────────────────────────────────

function toCsvCell(value: string): string {
  // eslint-disable-next-line no-control-regex -- strip control chars for CSV safety
  const clean = value.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
  const safe = /^[=+\-@\t\r\n]/.test(clean) ? `\t${clean}` : clean
  return `"${safe.replace(/"/g, '""')}"`
}

function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const csv = [headers.join(','), ...rows.map((r) => r.map(toCsvCell).join(','))].join('\n')
  const blob = new Blob([`\uFEFF${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

/** Parsea una línea CSV respetando comillas (campos con coma). */
function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (c === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"'
        i++
        continue
      }
      inQuotes = !inQuotes
      continue
    }
    if (!inQuotes && c === ',') {
      result.push(current.trim())
      current = ''
      continue
    }
    current += c
  }
  result.push(current.trim())
  return result
}

/** Campos del sistema para importación y su mapeo amigable. */
const IMPORT_FIELDS: { key: keyof Product | 'barcode'; label: string; required: boolean }[] = [
  { key: 'sku', label: 'Código (SKU)', required: true },
  { key: 'name', label: 'Nombre del producto', required: true },
  { key: 'price', label: 'Precio', required: true },
  { key: 'stock', label: 'Stock', required: false },
  { key: 'category', label: 'Categoría', required: false },
  { key: 'barcode', label: 'Código de barras', required: false },
  { key: 'satClaveProdServ', label: 'Clave SAT producto', required: false },
  { key: 'satClaveUnidad', label: 'Clave SAT unidad', required: false },
  { key: 'satDescripcion', label: 'Descripción SAT', required: false }
]

/** Sugiere mapeo: nombre de columna del archivo → key de IMPORT_FIELDS. */
function suggestMapping(fileHeaders: string[]): Record<string, string> {
  const normal = (s: string): string =>
    s
      .toLowerCase()
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .replace(/[^a-z0-9]/g, '')
  const aliases: Record<string, string[]> = {
    sku: ['sku', 'codigo', 'code', 'clave'],
    name: ['nombre', 'name', 'producto', 'descripcion'],
    price: ['precio', 'price', 'precioventa'],
    stock: ['stock', 'existencia', 'cantidad'],
    category: ['categoria', 'category', 'categoría'],
    barcode: ['barcode', 'codigobarras', 'ean'],
    satClaveProdServ: ['sat', 'clavesat', 'claveprodserv'],
    satClaveUnidad: ['unidad', 'satunidad'],
    satDescripcion: ['descripcionsat', 'satdesc']
  }
  const mapping: Record<string, string> = {}
  const used = new Set<string>()
  for (const header of fileHeaders) {
    const n = normal(header)
    for (const f of IMPORT_FIELDS) {
      if (used.has(f.key)) continue
      const fn = normal(f.label)
      const keys = aliases[f.key] ?? [f.key]
      const match = n === fn || keys.some((k) => n.includes(k) || k.includes(n))
      if (match) {
        mapping[header] = f.key
        used.add(f.key)
        break
      }
    }
  }
  return mapping
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

  // Importar CSV: archivo parseado, mapeo columna → campo, y estado del modal
  const [importOpen, setImportOpen] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [importMenuOpen, setImportMenuOpen] = useState(false)
  const [importHeaders, setImportHeaders] = useState<string[]>([])
  const [importRows, setImportRows] = useState<string[][]>([])
  const [importMapping, setImportMapping] = useState<Record<string, string>>({}) // columna archivo → key
  const [importProgress, setImportProgress] = useState<{
    done: number
    total: number
    error?: string
  } | null>(null)
  const importFileInputRef = useRef<HTMLInputElement>(null)

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

  const EXPORT_HEADERS = [
    'Código (SKU)',
    'Nombre',
    'Precio',
    'Stock',
    'Categoría',
    'Código de barras',
    'Clave SAT producto',
    'Clave SAT unidad',
    'Descripción SAT'
  ]

  function getExportRows(): string[][] {
    return products.map((p) => [
      p.sku,
      p.name,
      String(p.price),
      String(p.stock),
      p.category ?? '',
      p.barcode ?? '',
      p.satClaveProdServ ?? '',
      p.satClaveUnidad ?? '',
      p.satDescripcion ?? ''
    ])
  }

  function exportProductsCsv(): void {
    const rows = getExportRows()
    downloadCsv(`productos_${new Date().toISOString().slice(0, 10)}.csv`, EXPORT_HEADERS, rows)
    setMessage(`Exportados ${products.length} productos a CSV.`)
  }

  function exportProductsExcel(): void {
    const rows = getExportRows()
    const wb = XLSX.utils.book_new()
    const ws = XLSX.utils.aoa_to_sheet([EXPORT_HEADERS, ...rows])
    XLSX.utils.book_append_sheet(wb, ws, 'Productos')
    const date = new Date().toISOString().slice(0, 10)
    XLSX.writeFile(wb, `productos_${date}.xlsm`, { bookType: 'xlsm' })
    setMessage(`Exportados ${products.length} productos a Excel (.xlsm).`)
  }

  function openImportDialog(): void {
    setImportOpen(true)
    setImportHeaders([])
    setImportRows([])
    setImportMapping({})
    setImportProgress(null)
    importFileInputRef.current?.click()
  }

  function handleImportFile(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    const isXlsx = /\.xlsx$/i.test(file.name) || /\.xls$/i.test(file.name)
    if (isXlsx) {
      const reader = new FileReader()
      reader.onload = () => {
        try {
          const ab = reader.result as ArrayBuffer
          const wb = XLSX.read(ab, { type: 'array' })
          const firstSheetName = wb.SheetNames[0]
          if (!firstSheetName) {
            setMessage('El archivo Excel no tiene hojas.')
            return
          }
          const ws = wb.Sheets[firstSheetName]
          const raw = XLSX.utils.sheet_to_json<string[]>(ws, { header: 1, defval: '' }) as (
            | string
            | number
          )[][]
          if (!raw.length) {
            setMessage('La primera hoja está vacía.')
            return
          }
          const toString = (v: string | number): string => (v == null ? '' : String(v)).trim()
          const headerRow = raw[0].map(toString)
          const headers = headerRow.map((h, i) => h || `Columna ${i + 1}`)
          const rows = raw.slice(1).map((row) => {
            const arr: string[] = []
            for (let i = 0; i < headers.length; i++) arr.push(toString(row[i]))
            return arr
          })
          setImportHeaders(headers)
          setImportRows(rows)
          setImportMapping(suggestMapping(headers))
          setImportProgress(null)
        } catch (err) {
          setMessage((err as Error).message)
        }
      }
      reader.readAsArrayBuffer(file)
    } else {
      const reader = new FileReader()
      reader.onload = () => {
        const text = (reader.result as string) ?? ''
        const bom = /^\uFEFF/
        const lines = text
          .replace(/\r\n/g, '\n')
          .replace(/\r/g, '\n')
          .split('\n')
          .filter((l) => l.trim())
        if (lines.length < 2) {
          setMessage('El archivo debe tener al menos una fila de encabezados y una de datos.')
          return
        }
        const rawHeaders = parseCsvLine(lines[0].replace(bom, ''))
        const headers = rawHeaders.map((h) => h.trim() || `Columna ${rawHeaders.indexOf(h) + 1}`)
        const rows = lines.slice(1).map((line) => parseCsvLine(line))
        setImportHeaders(headers)
        setImportRows(rows)
        setImportMapping(suggestMapping(headers))
        setImportProgress(null)
      }
      reader.readAsText(file, 'UTF-8')
    }
  }

  function getMappedRow(row: string[]): Record<string, string> {
    const out: Record<string, string> = {}
    importHeaders.forEach((col, i) => {
      const field = importMapping[col]
      if (field && row[i] !== undefined) out[field] = String(row[i]).trim()
    })
    return out
  }

  async function runImport(): Promise<void> {
    if (importRows.length === 0) {
      setMessage('No hay filas para importar.')
      return
    }
    const cfg = loadRuntimeConfig()
    const requiredKeys = IMPORT_FIELDS.filter((f) => f.required).map((f) => f.key)
    const mapped = importRows.map((r) => getMappedRow(r))
    const valid = mapped.filter((row) => requiredKeys.every((k) => row[k]))
    if (valid.length === 0) {
      setMessage('Ninguna fila tiene SKU, Nombre y Precio. Revisa el mapeo de columnas.')
      return
    }
    setImportProgress({ done: 0, total: valid.length })
    let done = 0
    let lastError: string | undefined
    for (const row of valid) {
      try {
        const payload: Record<string, unknown> = {
          sku: row.sku,
          name: row.name,
          price: toNumber(row.price) || 0,
          stock: Math.max(0, Math.floor(toNumber(row.stock))),
          sat_clave_prod_serv: row.satClaveProdServ || '01010101',
          sat_clave_unidad: row.satClaveUnidad || 'H87',
          sat_descripcion: row.satDescripcion || ''
        }
        if (row.category) payload.category = row.category
        if (row.barcode) payload.barcode = row.barcode
        await createProduct(cfg, payload)
        const product: Product = {
          sku: row.sku,
          name: row.name,
          price: toNumber(row.price),
          stock: toNumber(row.stock),
          category: row.category || undefined,
          barcode: row.barcode || undefined,
          satClaveProdServ: row.satClaveProdServ || undefined,
          satClaveUnidad: row.satClaveUnidad || undefined,
          satDescripcion: row.satDescripcion || undefined
        }
        setProducts((prev) => {
          const idx = prev.findIndex((p) => p.sku === product.sku)
          if (idx >= 0) return prev.map((p, i) => (i === idx ? { ...p, ...product } : p))
          return [product, ...prev]
        })
      } catch (err) {
        lastError = (err as Error).message
      }
      done++
      setImportProgress((p) => (p ? { ...p, done, error: lastError } : null))
    }
    setMessage(
      lastError
        ? `Importados ${done - 1}/${valid.length}. Último error: ${lastError}`
        : `Importados ${valid.length} productos correctamente.`
    )
    setImportOpen(false)
    setImportProgress(null)
  }

  async function loadLowStock(): Promise<void> {
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getLowStockProducts(cfg, 50)
      const data = (raw.data ?? raw.products ?? []) as Record<string, unknown>[]
      setLowStock(Array.isArray(data) ? data : [])
      setShowLowStock(true)
      const n = Array.isArray(data) ? data.length : 0
      if (n === 0) {
        setMessage('No hay productos con stock bajo. Todo en orden.')
      } else {
        setMessage(`${n} producto${n === 1 ? '' : 's'} con pocas existencias. Conviene reponer.`)
      }
    } catch {
      setMessage(
        'No se pudo cargar la lista. Revisa la conexión con el servidor e inténtalo de nuevo.'
      )
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
        {/* Header Area — una sola fila: título + botones compactos */}
        <div className="px-6 py-4 border-b border-zinc-900 bg-zinc-950 flex items-center justify-between gap-4 shrink-0 flex-nowrap">
          <div className="min-w-0 shrink">
            <h1 className="text-xl font-bold text-white flex items-center gap-2 truncate">
              <PackageOpen className="w-6 h-6 text-blue-500 shrink-0" />
              <span className="truncate">Catálogo de Productos</span>
            </h1>
            <p className="text-zinc-500 text-xs mt-0.5 truncate">{products.length} productos</p>
          </div>
          <div className="flex items-center gap-2 shrink-0 flex-nowrap">
            <button
              onClick={() => void handleLoad()}
              disabled={busy}
              className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 px-3 py-2 rounded-lg text-xs font-semibold transition-colors border border-zinc-800"
            >
              <RefreshCw className={`w-3.5 h-3.5 shrink-0 ${busy ? 'animate-spin' : ''}`} />
              <span>Sincronizar</span>
            </button>
            <div className="relative">
              <button
                type="button"
                onClick={() => setExportMenuOpen((o) => !o)}
                disabled={busy || products.length === 0}
                className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 px-3 py-2 rounded-lg text-xs font-semibold transition-colors border border-zinc-800"
                title="Exportar catálogo (CSV o Excel)"
              >
                <Download className="w-3.5 h-3.5 shrink-0" />
                <span>Exportar</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 shrink-0 transition-transform ${exportMenuOpen ? 'rotate-180' : ''}`}
                />
              </button>
              {exportMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    aria-hidden
                    onClick={() => setExportMenuOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 z-20 min-w-[140px] py-1 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl">
                    <button
                      type="button"
                      onClick={() => {
                        exportProductsCsv()
                        setExportMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                    >
                      <Download className="w-3.5 h-3.5" />
                      CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        exportProductsExcel()
                        setExportMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Excel (.xlsm)
                    </button>
                  </div>
                </>
              )}
            </div>
            <input
              ref={importFileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={handleImportFile}
            />
            <div className="relative">
              <button
                type="button"
                onClick={() => setImportMenuOpen((o) => !o)}
                disabled={busy}
                className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 px-3 py-2 rounded-lg text-xs font-semibold transition-colors border border-zinc-800"
                title="Importar productos desde archivo"
              >
                <Upload className="w-3.5 h-3.5 shrink-0" />
                <span>Importar</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 shrink-0 transition-transform ${importMenuOpen ? 'rotate-180' : ''}`}
                />
              </button>
              {importMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    aria-hidden
                    onClick={() => setImportMenuOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 z-20 min-w-[160px] py-1 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl">
                    <button
                      type="button"
                      onClick={() => {
                        openImportDialog()
                        setImportMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                    >
                      <Upload className="w-3.5 h-3.5" />
                      CSV o Excel
                    </button>
                  </div>
                </>
              )}
            </div>
            <button
              onClick={() => {
                resetForm()
                setIsDrawerOpen(true)
              }}
              disabled={busy}
              className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white px-3 py-2 rounded-lg text-xs font-bold shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Nuevo</span>
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

        {showLowStock && (
          <div className="mx-8 mt-2 max-h-56 overflow-auto rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 shrink-0">
            <p className="text-sm font-semibold text-amber-400 mb-1 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {lowStock.length === 0 ? 'Sin alertas' : 'Productos con pocas existencias'}
            </p>
            {lowStock.length === 0 ? (
              <p className="text-zinc-400 text-sm">
                Ningún producto está por debajo del mínimo. No hace falta reponer por ahora.
              </p>
            ) : (
              <>
                <p className="text-zinc-500 text-xs mb-2">
                  Haz clic en un producto para editarlo o reponer. La lista tiene scroll y muestra
                  hasta 50; si hay más, usa la tabla de abajo y el filtro de categoría.
                </p>
                {lowStock.length >= 50 && (
                  <p className="text-amber-500/90 text-xs mb-2">
                    Hay al menos 50 con stock bajo. Se muestran los más urgentes primero.
                  </p>
                )}
              </>
            )}
            {lowStock.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-sm">
                {lowStock.map((p, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      const sku = String(p.sku ?? '')
                      const prod = products.find((x) => x.sku === sku)
                      if (prod) selectProduct(prod)
                    }}
                    className="flex justify-between items-center rounded-lg bg-zinc-900 px-3 py-2.5 border border-amber-900/30 hover:bg-zinc-800 hover:border-amber-500/40 text-left transition-colors"
                  >
                    <span className="text-zinc-200 truncate pr-2 font-medium">
                      {String(p.name || p.sku || `Producto ${i + 1}`)}
                    </span>
                    <span className="text-amber-400 font-bold shrink-0 ml-2">
                      Quedan {String(p.stock ?? '0')}
                    </span>
                  </button>
                ))}
              </div>
            )}
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
                        <button
                          type="button"
                          aria-label={`Editar ${p.sku}`}
                          className="p-2 -mr-2 text-zinc-500 hover:text-blue-400 opacity-60 group-hover:opacity-100 transition-all rounded-lg hover:bg-blue-500/10 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        >
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

      {/* Modal Importar CSV: mapeo de columnas y vista previa */}
      {importOpen && (
        <div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => !importProgress && setImportOpen(false)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between shrink-0">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-500" />
                Importar productos (CSV o Excel)
              </h2>
              <button
                type="button"
                onClick={() => !importProgress && setImportOpen(false)}
                className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {importHeaders.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-zinc-400 mb-4">
                    Selecciona un archivo CSV o Excel (.xlsx, .xls). La primera fila debe ser los
                    encabezados de columna.
                  </p>
                  <button
                    type="button"
                    onClick={() => importFileInputRef.current?.click()}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-sm font-medium"
                  >
                    Elegir archivo
                  </button>
                </div>
              ) : (
                <>
                  <div>
                    <p className="text-xs text-zinc-500 mb-3">
                      Asigna cada <strong className="text-zinc-400">columna de tu archivo</strong>{' '}
                      al <strong className="text-zinc-400">campo del sistema</strong>. Los
                      obligatorios son Código (SKU), Nombre y Precio.
                    </p>
                    <div className="space-y-2">
                      {IMPORT_FIELDS.map((f) => (
                        <div key={f.key} className="flex items-center gap-3 flex-wrap">
                          <label className="w-40 text-sm font-medium text-zinc-300 shrink-0">
                            {f.label}
                            {f.required && <span className="text-rose-400 ml-0.5">*</span>}
                          </label>
                          <select
                            className="flex-1 min-w-[140px] bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-blue-500"
                            value={
                              Object.keys(importMapping).find(
                                (col) => importMapping[col] === f.key
                              ) ?? ''
                            }
                            onChange={(e) => {
                              const col = e.target.value
                              setImportMapping((prev) => {
                                const next = { ...prev }
                                Object.keys(next).forEach((k) => {
                                  if (next[k] === f.key) delete next[k]
                                })
                                if (col) next[col] = f.key
                                return next
                              })
                            }}
                          >
                            <option value="">— No usar esta columna —</option>
                            {importHeaders.map((col) => (
                              <option key={col} value={col}>
                                {col}
                              </option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 mb-2">Vista previa (primeras 5 filas)</p>
                    <div className="overflow-x-auto rounded-xl border border-zinc-700 max-h-40 overflow-y-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="bg-zinc-800/80 text-zinc-400">
                            {IMPORT_FIELDS.filter((f) =>
                              importHeaders.some((col) => importMapping[col] === f.key)
                            ).map((f) => (
                              <th key={f.key} className="px-3 py-2 font-medium">
                                {f.label}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {importRows.slice(0, 5).map((row, i) => {
                            const mapped = getMappedRow(row)
                            return (
                              <tr key={i} className="border-t border-zinc-800">
                                {IMPORT_FIELDS.filter((f) =>
                                  importHeaders.some((col) => importMapping[col] === f.key)
                                ).map((f) => (
                                  <td key={f.key} className="px-3 py-2 text-zinc-300">
                                    {mapped[f.key] ?? '—'}
                                  </td>
                                ))}
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    <p className="text-xs text-zinc-500 mt-2">
                      Total en archivo:{' '}
                      <strong className="text-zinc-300">{importRows.length}</strong> filas. Se
                      importarán las que tengan Código (SKU), Nombre y Precio asignados.
                    </p>
                  </div>
                </>
              )}
            </div>
            {importHeaders.length > 0 && (
              <div className="px-6 py-4 border-t border-zinc-800 flex items-center justify-between gap-4 shrink-0 bg-zinc-950/50">
                {importProgress ? (
                  <span className="text-sm text-zinc-400">
                    Importando… {importProgress.done} / {importProgress.total}
                    {importProgress.error && (
                      <span className="text-amber-400 ml-2">({importProgress.error})</span>
                    )}
                  </span>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => importFileInputRef.current?.click()}
                      className="text-sm text-zinc-500 hover:text-zinc-300"
                    >
                      Cambiar archivo
                    </button>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setImportOpen(false)}
                        className="px-4 py-2 rounded-xl border border-zinc-600 text-zinc-300 hover:bg-zinc-800"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={() => void runImport()}
                        disabled={
                          busy ||
                          !IMPORT_FIELDS.filter((f) => f.required).every((f) =>
                            Object.values(importMapping).includes(f.key)
                          )
                        }
                        className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-50"
                      >
                        Importar productos
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
