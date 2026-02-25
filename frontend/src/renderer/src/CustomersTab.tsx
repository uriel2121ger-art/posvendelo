import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { loadRuntimeConfig, pullTable, syncTable } from './posApi'

type Customer = {
  id?: number | string
  name: string
  phone?: string
  email?: string
}

function normalizeCustomer(raw: Record<string, unknown>): Customer | null {
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!name) return null
  return {
    id: (raw.id as number | string | undefined) ?? `${name}-${Date.now()}`,
    name,
    phone: String(raw.phone ?? raw.telefono ?? ''),
    email: String(raw.email ?? '')
  }
}

export default function CustomersTab(): ReactElement {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Clientes (F2): carga, alta, edicion y baja logica funcional.'
  )
  const requestIdRef = useRef(0)

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

  useEffect(() => { setPage(0) }, [query])

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
    return () => { requestIdRef.current++ }
  }, [handleLoad])

  async function handleCreate(): Promise<void> {
    if (!name.trim()) {
      setMessage('Nombre de cliente es obligatorio.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const customer = {
        id: selectedId ?? `c-${Date.now()}`,
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
        deleted: false
      }
      const isUpdate = Boolean(selectedId)
      await syncTable('customers', [customer], cfg)
      setCustomers((prev) => {
        const idKey = String(customer.id)
        const exists = prev.some((item) => String(item.id) === idKey)
        if (exists) {
          return prev.map((item) => (String(item.id) === idKey ? { ...item, ...customer } : item))
        }
        return [customer, ...prev]
      })
      setSelectedId(null)
      setName('')
      setPhone('')
      setEmail('')
      setMessage(
        isUpdate ? `Cliente actualizado: ${customer.name}` : `Cliente guardado: ${customer.name}`
      )
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(): Promise<void> {
    if (!selectedId) {
      setMessage('Selecciona un cliente para eliminar.')
      return
    }
    const target = customers.find((item) => String(item.id) === selectedId)
    if (!target) return
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
      setMessage(`Cliente eliminado: ${target.name}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function selectCustomer(customer: Customer): void {
    setSelectedId(String(customer.id))
    setName(customer.name)
    setPhone(customer.phone ?? '')
    setEmail(customer.email ?? '')
    setMessage(`Cliente seleccionado: ${customer.name}`)
  }

  function resetForm(): void {
    setSelectedId(null)
    setName('')
    setPhone('')
    setEmail('')
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_1fr_1fr_auto_auto_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Nombre cliente"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Telefono"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => void handleCreate()}
          disabled={busy}
        >
          {selectedId ? 'Actualizar' : 'Guardar'}
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
          disabled={busy || !selectedId}
        >
          Eliminar
        </button>
      </div>

      <div className="border-b border-zinc-800 bg-zinc-900/50 p-4 mx-4 mb-2 rounded-xl mt-4">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Buscar cliente"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)]">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm">
              <th className="py-4 px-6">Nombre</th>
              <th className="py-4 px-6">Telefono</th>
              <th className="py-4 px-6">Email</th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((c) => (
              <tr
                key={String(c.id)}
                className={`border-b border-zinc-800/50 cursor-pointer transition-colors text-sm ${
                  selectedId === String(c.id)
                    ? 'bg-blue-900/20 border-l-4 border-blue-500'
                    : 'hover:bg-zinc-800/40'
                }`}
                onClick={() => selectCustomer(c)}
              >
                <td className="py-4 px-6 font-medium">{c.name}</td>
                <td className="py-4 px-6 font-medium">{c.phone || '-'}</td>
                <td className="py-4 px-6 font-medium">{c.email || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 flex items-center justify-between">
        <span>{message}</span>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-zinc-500">{filtered.length} resultados</span>
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
        </div>
      </div>
    </div>
  )
}
