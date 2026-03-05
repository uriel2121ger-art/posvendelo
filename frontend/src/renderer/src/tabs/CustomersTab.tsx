import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useConfirm } from '../components/ConfirmDialog'
import {
  Search,
  Plus,
  Users,
  X,
  UserCircle,
  RefreshCw,
  Mail,
  Phone,
  CreditCard,
  ShoppingBag,
  Download,
  Upload,
  ChevronDown
} from 'lucide-react'
import {
  loadRuntimeConfig,
  pullTable,
  syncTable,
  createCustomer,
  getCustomerCredit,
  getCustomerSales
} from '../posApi'
import { useFocusTrap } from '../hooks/useFocusTrap'
import * as XLSX from 'xlsx'

type Customer = {
  id?: number | string
  name: string
  phone?: string
  email?: string
  /** Facturación (opcionales) */
  rfc?: string
  codigo_postal?: string
  razon_social?: string
  regimen_fiscal?: string
}

const PHONE_RE = /^[\d\s()+-]{7,20}$/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function normalizeCustomer(raw: Record<string, unknown>): Customer | null {
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!name) return null
  return {
    id: (raw.id as number | string | undefined) ?? `${name}-${Date.now()}`,
    name,
    phone: String(raw.phone ?? raw.telefono ?? ''),
    email: String(raw.email ?? ''),
    rfc: raw.rfc != null ? String(raw.rfc) : undefined,
    codigo_postal: raw.codigo_postal != null ? String(raw.codigo_postal) : (raw.postal_code != null ? String(raw.postal_code) : undefined),
    razon_social: raw.razon_social != null ? String(raw.razon_social) : undefined,
    regimen_fiscal: raw.regimen_fiscal != null ? String(raw.regimen_fiscal) : undefined
  }
}

// ─── Exportar / Importar CSV y Excel ───────────────────────────────────────

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

const CUSTOMER_IMPORT_FIELDS: {
  key: 'name' | 'phone' | 'email'
  label: string
  required: boolean
}[] = [
  { key: 'name', label: 'Nombre', required: true },
  { key: 'phone', label: 'Teléfono', required: false },
  { key: 'email', label: 'Correo electrónico', required: false }
]

function suggestCustomerMapping(fileHeaders: string[]): Record<string, string> {
  const normal = (s: string): string =>
    s
      .toLowerCase()
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .replace(/[^a-z0-9]/g, '')
  const mapping: Record<string, string> = {}
  const used = new Set<string>()
  for (const header of fileHeaders) {
    const n = normal(header)
    for (const f of CUSTOMER_IMPORT_FIELDS) {
      if (used.has(f.key)) continue
      const keys: string[] =
        f.key === 'name'
          ? ['nombre', 'name', 'cliente']
          : f.key === 'phone'
            ? ['telefono', 'phone', 'tel', 'cel']
            : ['email', 'correo', 'mail']
      if (keys.some((k) => n.includes(k) || n === k)) {
        mapping[header] = f.key
        used.add(f.key)
        break
      }
    }
  }
  return mapping
}

export default function CustomersTab(): ReactElement {
  const confirm = useConfirm()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [rfc, setRfc] = useState('')
  const [codigoPostal, setCodigoPostal] = useState('')
  const [razonSocial, setRazonSocial] = useState('')
  const [regimenFiscal, setRegimenFiscal] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Clientes (F2): carga, alta, edicion y baja logica funcional.'
  )
  const requestIdRef = useRef(0)
  const drawerRef = useRef<HTMLDivElement>(null)
  const [creditData, setCreditData] = useState<Record<string, unknown> | null>(null)

  useFocusTrap(drawerRef, isDrawerOpen)
  const [customerSales, setCustomerSales] = useState<Record<string, unknown>[]>([])
  const [showCredit, setShowCredit] = useState(false)
  const [showSales, setShowSales] = useState(false)

  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [importMenuOpen, setImportMenuOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importHeaders, setImportHeaders] = useState<string[]>([])
  const [importRows, setImportRows] = useState<string[][]>([])
  const [importMapping, setImportMapping] = useState<Record<string, string>>({})
  const [importProgress, setImportProgress] = useState<{
    done: number
    total: number
    error?: string
  } | null>(null)
  const importFileInputRef = useRef<HTMLInputElement>(null)

  const PAGE_SIZE = 50
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return customers
    return customers.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.phone ?? '').toLowerCase().includes(q) ||
        (c.email ?? '').toLowerCase().includes(q)
    )
  }, [customers, query])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated = useMemo(() => {
    const start = page * PAGE_SIZE
    return filtered.slice(start, start + PAGE_SIZE)
  }, [filtered, page])

  useEffect(() => {
    setPage(0)
  }, [query])

  const handleLoad = useCallback(async (): Promise<void> => {
    const reqId = ++requestIdRef.current
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const rows = await pullTable('customers', cfg)
      if (requestIdRef.current !== reqId) return
      const normalized = rows
        .map(normalizeCustomer)
        .filter((item): item is Customer => item !== null)
      setCustomers(normalized)
      setMessage(`Clientes cargados: ${normalized.length}`)
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

  async function handleCreate(): Promise<void> {
    if (busy) return
    requestIdRef.current++ // invalidate any in-flight load
    const trimmedName = name.trim()
    if (!trimmedName) {
      setMessage('Nombre de cliente es obligatorio.')
      return
    }
    if (phone.trim() && !PHONE_RE.test(phone.trim())) {
      setMessage('Telefono invalido. Usa solo digitos, espacios, +, - o parentesis (7-20 chars).')
      return
    }
    if (email.trim() && !EMAIL_RE.test(email.trim())) {
      setMessage('Email invalido. Ejemplo: usuario@dominio.com')
      return
    }
    const isUpdate = Boolean(selectedId)
    // Local duplicate check (case-insensitive) for new customers
    if (!isUpdate) {
      const dup = customers.some((c) => c.name.toLowerCase() === trimmedName.toLowerCase())
      if (dup) {
        setMessage(`Ya existe un cliente con el nombre "${trimmedName}".`)
        return
      }
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      if (isUpdate) {
        // Update via sync (selectedId is a real DB id)
        const customer = {
          id: selectedId as string | number,
          name: trimmedName,
          phone: phone.trim(),
          email: email.trim(),
          rfc: rfc.trim() || undefined,
          codigo_postal: codigoPostal.trim() || undefined,
          razon_social: razonSocial.trim() || undefined,
          regimen_fiscal: regimenFiscal.trim() || undefined,
          deleted: false
        }
        await syncTable('customers', [customer], cfg)
        setCustomers((prev) =>
          prev.map((item) => (String(item.id) === selectedId ? { ...item, ...customer } : item))
        )
        setMessage(`Cliente actualizado: ${trimmedName}`)
      } else {
        // Create via POST (returns real DB id)
        const result = await createCustomer(cfg, {
          name: trimmedName,
          phone: phone.trim(),
          email: email.trim(),
          rfc: rfc.trim() || undefined,
          codigo_postal: codigoPostal.trim() || undefined,
          razon_social: razonSocial.trim() || undefined,
          regimen_fiscal: regimenFiscal.trim() || undefined
        })
        const data = (result.data ?? result) as Record<string, unknown>
        const newCustomer: Customer = {
          id: Number(data.id),
          name: trimmedName,
          phone: phone.trim(),
          email: email.trim(),
          rfc: rfc.trim() || undefined,
          codigo_postal: codigoPostal.trim() || undefined,
          razon_social: razonSocial.trim() || undefined,
          regimen_fiscal: regimenFiscal.trim() || undefined
        }
        setCustomers((prev) => [newCustomer, ...prev])
        setIsDrawerOpen(false)
        setMessage(`Cliente guardado: ${trimmedName}`)
      }
      setSelectedId(null)
      setName('')
      setPhone('')
      setEmail('')
      setRfc('')
      setCodigoPostal('')
      setRazonSocial('')
      setRegimenFiscal('')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(): Promise<void> {
    if (busy) return
    requestIdRef.current++ // invalidate any in-flight load
    if (!selectedId) {
      setMessage('Selecciona un cliente para eliminar.')
      return
    }
    const target = customers.find((item) => String(item.id) === selectedId)
    if (!target) {
      setMessage('Cliente no encontrado. Recarga la lista.')
      return
    }
    if (
      !(await confirm(`¿Eliminar cliente "${target.name}"?`, {
        variant: 'danger',
        title: 'Eliminar cliente'
      }))
    )
      return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await syncTable(
        'customers',
        [
          {
            id: target.id,
            name: target.name,
            phone: target.phone ?? '',
            email: target.email ?? '',
            deleted: true
          }
        ],
        cfg
      )
      setCustomers((prev) => prev.filter((item) => String(item.id) !== selectedId))
      setSelectedId(null)
      setName('')
      setPhone('')
      setEmail('')
      setRfc('')
      setCodigoPostal('')
      setRazonSocial('')
      setRegimenFiscal('')
      setIsDrawerOpen(false)
      setMessage(`Cliente eliminado: ${target.name}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function loadCredit(customerId: string): Promise<void> {
    const numId = Number(customerId)
    if (!Number.isFinite(numId) || numId <= 0) {
      setMessage('ID de cliente invalido para consultar credito.')
      return
    }
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getCustomerCredit(cfg, numId)
      const data = (raw.data ?? raw) as Record<string, unknown>
      setCreditData(data)
      setShowCredit(true)
      setMessage(`Credito cargado para cliente ${customerId}.`)
    } catch (err) {
      setMessage((err as Error).message)
      setCreditData(null)
    }
  }

  async function loadCustomerSalesData(customerId: string): Promise<void> {
    const numId = Number(customerId)
    if (!Number.isFinite(numId) || numId <= 0) {
      setMessage('ID de cliente invalido para consultar ventas.')
      return
    }
    try {
      const cfg = loadRuntimeConfig()
      const raw = await getCustomerSales(cfg, numId, 20)
      const data = (raw.data ?? raw.sales ?? []) as Record<string, unknown>[]
      setCustomerSales(Array.isArray(data) ? data : [])
      setShowSales(true)
      setMessage(`Ventas cargadas para cliente ${customerId}.`)
    } catch (err) {
      setMessage((err as Error).message)
      setCustomerSales([])
    }
  }

  function selectCustomer(customer: Customer): void {
    setSelectedId(String(customer.id))
    setIsDrawerOpen(true)
    setName(customer.name)
    setPhone(customer.phone ?? '')
    setEmail(customer.email ?? '')
    setRfc(customer.rfc ?? '')
    setCodigoPostal(customer.codigo_postal ?? '')
    setRazonSocial(customer.razon_social ?? '')
    setRegimenFiscal(customer.regimen_fiscal ?? '')
    setShowCredit(false)
    setShowSales(false)
    setCreditData(null)
    setCustomerSales([])
    setMessage(`Cliente seleccionado: ${customer.name}`)
  }

  function resetForm(): void {
    setSelectedId(null)
    setIsDrawerOpen(true)
    setName('')
    setPhone('')
    setEmail('')
    setRfc('')
    setCodigoPostal('')
    setRazonSocial('')
    setRegimenFiscal('')
    setShowCredit(false)
    setShowSales(false)
    setCreditData(null)
    setCustomerSales([])
  }

  const EXPORT_HEADERS = ['Nombre', 'Teléfono', 'Correo']
  function getExportRows(): string[][] {
    return customers.map((c) => [c.name, c.phone ?? '', c.email ?? ''])
  }
  function exportCustomersCsv(): void {
    downloadCsv(
      `clientes_${new Date().toISOString().slice(0, 10)}.csv`,
      EXPORT_HEADERS,
      getExportRows()
    )
    setMessage(`Exportados ${customers.length} clientes a CSV.`)
  }
  function exportCustomersExcel(): void {
    const wb = XLSX.utils.book_new()
    const ws = XLSX.utils.aoa_to_sheet([EXPORT_HEADERS, ...getExportRows()])
    XLSX.utils.book_append_sheet(wb, ws, 'Clientes')
    XLSX.writeFile(wb, `clientes_${new Date().toISOString().slice(0, 10)}.xlsx`)
    setMessage(`Exportados ${customers.length} clientes a Excel.`)
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
          const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' }) as (
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
          setImportMapping(suggestCustomerMapping(headers))
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
        const lines = text
          .replace(/\r\n/g, '\n')
          .replace(/\r/g, '\n')
          .split('\n')
          .filter((l) => l.trim())
        if (lines.length < 2) {
          setMessage('El archivo debe tener encabezados y al menos una fila de datos.')
          return
        }
        const rawHeaders = parseCsvLine(lines[0].replace(/^\uFEFF/, ''))
        const headers = rawHeaders.map((h, i) => h.trim() || `Columna ${i + 1}`)
        const rows = lines.slice(1).map((line) => parseCsvLine(line))
        setImportHeaders(headers)
        setImportRows(rows)
        setImportMapping(suggestCustomerMapping(headers))
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
    const mapped = importRows.map((r) => getMappedRow(r))
    const valid = mapped.filter((row) => row.name)
    if (valid.length === 0) {
      setMessage('Ninguna fila tiene nombre. Asigna la columna "Nombre" en el mapeo.')
      return
    }
    setImportProgress({ done: 0, total: valid.length })
    let done = 0
    let lastError: string | undefined
    for (const row of valid) {
      try {
        await createCustomer(cfg, {
          name: row.name,
          phone: row.phone || undefined,
          email: row.email || undefined
        })
        const newCust = normalizeCustomer({ name: row.name, phone: row.phone, email: row.email })
        if (newCust) setCustomers((prev) => [...prev, newCust])
      } catch (err) {
        lastError = (err as Error).message
      }
      done++
      setImportProgress((p) => (p ? { ...p, done, error: lastError } : null))
    }
    setMessage(
      lastError
        ? `Importados ${done - 1}/${valid.length}. Último error: ${lastError}`
        : `Importados ${valid.length} clientes correctamente.`
    )
    setImportOpen(false)
    setImportProgress(null)
  }

  return (
    <div className="flex h-full bg-[#09090b] font-sans text-slate-200 select-none overflow-hidden relative">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Header Area — una fila: título + botones compactos (como Productos) */}
        <div className="px-6 py-4 border-b border-zinc-900 bg-zinc-950 flex items-center justify-between gap-4 shrink-0 flex-nowrap">
          <div className="min-w-0 shrink">
            <h1 className="text-xl font-bold text-white flex items-center gap-2 truncate">
              <Users className="w-6 h-6 text-emerald-500 shrink-0" />
              <span className="truncate">Directorio de Clientes</span>
            </h1>
            <p className="text-zinc-500 text-xs mt-0.5 truncate">{customers.length} clientes</p>
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
                disabled={busy || customers.length === 0}
                className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 px-3 py-2 rounded-lg text-xs font-semibold transition-colors border border-zinc-800"
                title="Exportar listado (CSV o Excel)"
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
                  <div className="absolute right-0 top-full mt-1 z-20 min-w-[120px] py-1 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl">
                    <button
                      type="button"
                      onClick={() => {
                        exportCustomersCsv()
                        setExportMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                    >
                      <Download className="w-3.5 h-3.5" /> CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        exportCustomersExcel()
                        setExportMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                    >
                      <Download className="w-3.5 h-3.5" /> Excel
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
                title="Importar clientes desde archivo"
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
                  <div className="absolute right-0 top-full mt-1 z-20 min-w-[140px] py-1 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl">
                    <button
                      type="button"
                      onClick={() => {
                        openImportDialog()
                        setImportMenuOpen(false)
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                    >
                      <Upload className="w-3.5 h-3.5" /> CSV o Excel
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
              className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-2 rounded-lg text-xs font-bold shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Nuevo</span>
            </button>
          </div>
        </div>

        {/* Toolbar (Search) */}
        <div className="px-8 py-4 bg-zinc-950/50 flex flex-wrap items-center gap-4 shrink-0">
          <div className="relative flex-1 min-w-[300px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
            <input
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-11 pr-4 text-sm font-medium focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all placeholder:text-zinc-600"
              placeholder="Buscar por nombre, teléfono o email..."
              value={query}
              // eslint-disable-next-line no-control-regex
              onChange={(e) => setQuery(e.target.value.replace(/[\x00-\x1F\x7F-\x9F]/g, ''))}
            />
          </div>
        </div>

        {/* Master List (Data Grid) */}
        <div className="flex-1 overflow-y-auto px-8 py-4">
          <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold">
                  <th className="px-6 py-4">Nombre del Cliente</th>
                  <th className="px-6 py-4 w-48">Contacto</th>
                  <th className="px-6 py-4 w-64">Email</th>
                  <th className="px-6 py-4 w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-16 text-center text-zinc-500">
                      <Users className="w-12 h-12 mx-auto mb-3 opacity-20" />
                      <p className="text-lg font-medium text-zinc-400">Directorio vacío</p>
                      <p className="text-sm mt-1">
                        {query.trim()
                          ? 'Intenta con otra búsqueda.'
                          : 'Haz clic en "Nuevo Cliente".'}
                      </p>
                    </td>
                  </tr>
                ) : (
                  paginated.map((c) => (
                    <tr
                      key={String(c.id)}
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        selectCustomer(c)
                        setIsDrawerOpen(true)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          selectCustomer(c)
                          setIsDrawerOpen(true)
                        }
                      }}
                      className="group hover:bg-zinc-800/40 cursor-pointer transition-colors"
                      aria-label={`Cliente ${c.name}`}
                    >
                      <td className="px-6 py-4 font-medium text-zinc-200">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-zinc-800 text-zinc-500 flex items-center justify-center shrink-0">
                            <UserCircle className="w-5 h-5" />
                          </div>
                          <div className="truncate group-hover:text-emerald-400 transition-colors">
                            {c.name}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-zinc-400 font-mono truncate">
                        {c.phone ? (
                          <div className="flex items-center gap-2">
                            <Phone className="w-3.5 h-3.5 opacity-50" /> {c.phone}
                          </div>
                        ) : (
                          <span className="opacity-30">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-zinc-400 truncate max-w-[200px]">
                        {c.email ? (
                          <div className="flex items-center gap-2">
                            <Mail className="w-3.5 h-3.5 opacity-50" /> {c.email}
                          </div>
                        ) : (
                          <span className="opacity-30">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="p-2 -mr-2 text-zinc-600 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-all rounded-lg hover:bg-emerald-500/10">
                          <UserCircle className="w-4 h-4" />
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
            className="w-[480px] bg-zinc-950 border-l border-zinc-800 h-full shadow-2xl flex flex-col transform transition-transform duration-300 translate-x-0 cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/30">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <UserCircle className="w-6 h-6 text-emerald-500" />
                {selectedId ? 'Perfil del Cliente' : 'Nuevo Cliente'}
              </h2>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="p-2 bg-zinc-900 hover:bg-zinc-800 rounded-full text-zinc-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Avatar Placeholder */}
              <div className="flex items-center gap-4 mb-2">
                <div className="w-16 h-16 rounded-2xl bg-zinc-900 border-2 border-zinc-800 flex items-center justify-center text-zinc-500 shadow-inner">
                  <Users className="w-8 h-8 opacity-50" />
                </div>
                <div className="flex-1">
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Nombre completo"
                    className="w-full bg-transparent border-b-2 border-zinc-800 focus:border-emerald-500 px-1 py-2 text-xl font-bold text-white focus:outline-none transition-colors placeholder:text-zinc-700"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
                    <Phone className="w-3.5 h-3.5" /> Teléfono
                  </label>
                  <input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Ej: 55 1234 5678"
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-emerald-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5" /> Correo
                  </label>
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="cliente@ejemplo.com"
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
                <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-3">
                  Datos de facturación (opcionales)
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                      RFC
                    </label>
                    <input
                      value={rfc}
                      onChange={(e) => setRfc(e.target.value.toUpperCase())}
                      placeholder="Ej: XAXX010101000"
                      maxLength={14}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm font-mono text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                      Código postal
                    </label>
                    <input
                      value={codigoPostal}
                      onChange={(e) => setCodigoPostal(e.target.value.replace(/\D/g, '').slice(0, 10))}
                      placeholder="Ej: 97000"
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm font-mono text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                      Razón social
                    </label>
                    <input
                      value={razonSocial}
                      onChange={(e) => setRazonSocial(e.target.value)}
                      placeholder="Nombre o razón social para factura"
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm font-medium text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                      Régimen fiscal
                    </label>
                    <input
                      value={regimenFiscal}
                      onChange={(e) => setRegimenFiscal(e.target.value)}
                      placeholder="Ej: 601, 603, 612"
                      maxLength={10}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm font-mono text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
              </div>

              {selectedId && (
                <>
                  <div className="h-px bg-zinc-900 w-full" />

                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() =>
                        showCredit ? setShowCredit(false) : void loadCredit(selectedId)
                      }
                      className={`py-3 px-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all ${showCredit ? 'bg-indigo-500/10 border-indigo-500/50 text-indigo-400' : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-white'}`}
                    >
                      <CreditCard className="w-5 h-5" />
                      <span className="text-xs font-bold uppercase tracking-wider">Crédito</span>
                    </button>
                    <button
                      onClick={() =>
                        showSales ? setShowSales(false) : void loadCustomerSalesData(selectedId)
                      }
                      className={`py-3 px-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all ${showSales ? 'bg-blue-500/10 border-blue-500/50 text-blue-400' : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-white'}`}
                    >
                      <ShoppingBag className="w-5 h-5" />
                      <span className="text-xs font-bold uppercase tracking-wider">Historial</span>
                    </button>
                  </div>

                  {/* Credit Panel */}
                  {showCredit && creditData && (
                    <div className="bg-indigo-950/20 border border-indigo-900/30 rounded-xl p-5 animate-fade-in-up">
                      <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                        <CreditCard className="w-4 h-4" /> Estado de Cuenta
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-[10px] uppercase text-indigo-300/60 font-bold mb-1">
                            Límite
                          </div>
                          <div className="text-lg font-mono text-zinc-300">
                            ${Number(creditData.credit_limit ?? creditData.limit ?? 0).toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase text-indigo-300/60 font-bold mb-1">
                            Balance Deuda
                          </div>
                          <div className="text-lg font-mono text-rose-400">
                            ${Number(creditData.balance ?? creditData.used ?? 0).toFixed(2)}
                          </div>
                        </div>
                        <div className="col-span-2 mt-2 pt-3 border-t border-indigo-900/30 flex justify-between items-end">
                          <div className="text-xs uppercase text-indigo-300/60 font-bold">
                            Disponible
                          </div>
                          <div className="text-2xl font-black text-emerald-400 tracking-tight">
                            ${Number(creditData.available ?? 0).toFixed(2)}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Sales Panel */}
                  {showSales && customerSales.length > 0 && (
                    <div className="bg-blue-950/20 border border-blue-900/30 rounded-xl overflow-hidden animate-fade-in-up">
                      <div className="px-4 py-3 bg-blue-900/20 border-b border-blue-900/30">
                        <h3 className="text-xs font-bold text-blue-400 uppercase tracking-widest flex items-center gap-2">
                          <ShoppingBag className="w-4 h-4" /> Últimas Compras
                        </h3>
                      </div>
                      <div className="max-h-48 overflow-y-auto p-2">
                        <div className="space-y-1">
                          {customerSales.map((s, i) => (
                            <div
                              key={i}
                              className="flex justify-between items-center p-2 hover:bg-blue-900/20 rounded-lg transition-colors"
                            >
                              <div>
                                <div className="text-xs font-bold text-zinc-300 uppercase">
                                  {String(s.folio ?? s.id ?? '-')}
                                </div>
                                <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                                  {String(s.timestamp ?? s.created_at ?? '-').slice(0, 10)} /{' '}
                                  {String(s.payment_method ?? '-')}
                                </div>
                              </div>
                              <div className="text-sm font-bold text-emerald-400 font-mono">
                                ${Number(s.total ?? 0).toFixed(2)}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  {showSales && customerSales.length === 0 && (
                    <div className="text-center p-4 py-8 text-zinc-600 bg-zinc-900/30 rounded-xl border border-zinc-800/50">
                      <ShoppingBag className="w-8 h-8 mx-auto mb-2 opacity-20" />
                      <div className="text-sm font-medium">No hay compras registradas</div>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="p-6 border-t border-zinc-800 bg-zinc-900/50 flex flex-col gap-3 shrink-0">
              <button
                onClick={() => void handleCreate()}
                disabled={busy || !name.trim()}
                className="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold tracking-widest shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-all active:scale-[0.98] disabled:opacity-50 text-sm"
              >
                {busy ? 'PROCESANDO...' : selectedId ? 'ACTUALIZAR PERFIL' : 'GUARDAR CLIENTE'}
              </button>
              {selectedId && (
                <button
                  onClick={() => void handleDelete()}
                  disabled={busy}
                  className="w-full py-3 bg-transparent border border-rose-500/30 text-rose-500 rounded-xl font-bold tracking-wider hover:bg-rose-500/10 transition-colors disabled:opacity-50 text-xs"
                >
                  ELIMINAR CLIENTE
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Importar clientes (CSV o Excel) */}
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
                <Upload className="w-5 h-5 text-emerald-500" />
                Importar clientes (CSV o Excel)
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
                    encabezados.
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
                  <p className="text-xs text-zinc-500">
                    Asigna cada columna de tu archivo al campo del sistema. Solo el{' '}
                    <strong className="text-zinc-400">Nombre</strong> es obligatorio.
                  </p>
                  <div className="space-y-2">
                    {CUSTOMER_IMPORT_FIELDS.map((f) => (
                      <div key={f.key} className="flex items-center gap-3 flex-wrap">
                        <label className="w-40 text-sm font-medium text-zinc-300 shrink-0">
                          {f.label}
                          {f.required && <span className="text-rose-400 ml-0.5">*</span>}
                        </label>
                        <select
                          className="flex-1 min-w-[140px] bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
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
                          <option value="">— No usar —</option>
                          {importHeaders.map((col) => (
                            <option key={col} value={col}>
                              {col}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 mb-2">Vista previa (primeras 5 filas)</p>
                    <div className="overflow-x-auto rounded-xl border border-zinc-700 max-h-32 overflow-y-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="bg-zinc-800/80 text-zinc-400">
                            {CUSTOMER_IMPORT_FIELDS.filter((f) =>
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
                                {CUSTOMER_IMPORT_FIELDS.filter((f) =>
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
                      Total: <strong className="text-zinc-300">{importRows.length}</strong> filas.
                      Se importan las que tengan nombre.
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
                        disabled={busy || !Object.values(importMapping).includes('name')}
                        className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold disabled:opacity-50"
                      >
                        Importar clientes
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
