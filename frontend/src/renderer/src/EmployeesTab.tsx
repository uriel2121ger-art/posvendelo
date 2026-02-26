import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import {
  loadRuntimeConfig,
  getUserRole,
  listEmployees,
  createEmployee,
  updateEmployee,
  deleteEmployee
} from './posApi'

type Employee = {
  id: number
  employee_code: string
  name: string
  position: string
  base_salary: number
  commission_rate: number
  phone: string
  email: string
  notes: string
}

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeEmployee(raw: Record<string, unknown>): Employee | null {
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!name) return null
  return {
    id: toNumber(raw.id),
    employee_code: String(raw.employee_code ?? raw.code ?? ''),
    name,
    position: String(raw.position ?? raw.puesto ?? ''),
    base_salary: toNumber(raw.base_salary ?? raw.salary),
    commission_rate: toNumber(raw.commission_rate ?? raw.commission),
    phone: String(raw.phone ?? raw.telefono ?? ''),
    email: String(raw.email ?? ''),
    notes: String(raw.notes ?? raw.notas ?? '')
  }
}

export default function EmployeesTab(): ReactElement {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [position, setPosition] = useState('')
  const [salary, setSalary] = useState('0')
  const [commission, setCommission] = useState('0')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Empleados: gestiona tu equipo de trabajo.')
  const requestIdRef = useRef(0)
  const role = getUserRole()
  const canEdit = role === 'manager' || role === 'owner' || role === 'admin'

  const PAGE_SIZE = 50
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return employees
    return employees.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.employee_code.toLowerCase().includes(q) ||
        e.phone.toLowerCase().includes(q) ||
        e.email.toLowerCase().includes(q)
    )
  }, [employees, query])

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
      const raw = await listEmployees(cfg)
      if (requestIdRef.current !== reqId) return
      const data = (raw.data ?? raw.employees ?? []) as Record<string, unknown>[]
      const arr = Array.isArray(data) ? data : []
      const normalized = arr.map(normalizeEmployee).filter((e): e is Employee => e !== null)
      setEmployees(normalized)
      setMessage(`Empleados cargados: ${normalized.length}`)
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

  async function handleSave(): Promise<void> {
    if (busy || !canEdit) return
    if (!name.trim()) {
      setMessage('Nombre es obligatorio.')
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const body = {
        employee_code: code.trim(),
        name: name.trim(),
        position: position.trim(),
        base_salary: toNumber(salary),
        commission_rate: toNumber(commission),
        phone: phone.trim(),
        email: email.trim(),
        notes: notes.trim()
      }
      if (selectedId) {
        await updateEmployee(cfg, selectedId, body)
        setEmployees((prev) =>
          prev.map((e) => (e.id === selectedId ? { ...e, ...body, id: selectedId } : e))
        )
        setMessage(`Empleado actualizado: ${body.name}`)
      } else {
        const result = await createEmployee(cfg, body)
        const data = (result.data ?? result) as Record<string, unknown>
        const newEmp = normalizeEmployee({ ...body, id: data.id ?? Date.now() })
        if (newEmp) setEmployees((prev) => [newEmp, ...prev])
        setMessage(`Empleado creado: ${body.name}`)
      }
      resetForm()
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(): Promise<void> {
    if (busy || !canEdit || !selectedId) return
    const target = employees.find((e) => e.id === selectedId)
    if (!target) return
    if (!window.confirm(`¿Eliminar empleado "${target.name}"?`)) return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await deleteEmployee(cfg, selectedId)
      setEmployees((prev) => prev.filter((e) => e.id !== selectedId))
      resetForm()
      setMessage(`Empleado eliminado: ${target.name}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function selectEmployee(emp: Employee): void {
    setSelectedId(emp.id)
    setCode(emp.employee_code)
    setName(emp.name)
    setPosition(emp.position)
    setSalary(emp.base_salary.toFixed(2))
    setCommission(emp.commission_rate.toFixed(2))
    setPhone(emp.phone)
    setEmail(emp.email)
    setNotes(emp.notes)
    setMessage(`Empleado seleccionado: ${emp.name}`)
  }

  function resetForm(): void {
    setSelectedId(null)
    setCode('')
    setName('')
    setPosition('')
    setSalary('0')
    setCommission('0')
    setPhone('')
    setEmail('')
    setNotes('')
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_1fr_1fr_160px_160px_1fr_1fr_auto_auto_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Codigo"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Nombre"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Posicion"
          value={position}
          onChange={(e) => setPosition(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Salario"
          type="number"
          min={0}
          value={salary}
          onChange={(e) => setSalary(e.target.value)}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Comision %"
          type="number"
          min={0}
          value={commission}
          onChange={(e) => setCommission(e.target.value)}
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
          onClick={() => void handleSave()}
          disabled={busy || !canEdit || !name.trim()}
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
          disabled={busy || !canEdit || !selectedId}
        >
          Eliminar
        </button>
      </div>

      <div className="border-b border-zinc-800 bg-zinc-900/50 p-4 mx-4 mb-2 rounded-xl mt-4">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Buscar empleado"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)]">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm">
              <th className="py-4 px-6">Codigo</th>
              <th className="py-4 px-6">Nombre</th>
              <th className="py-4 px-6">Posicion</th>
              <th className="py-4 px-6">Salario</th>
              <th className="py-4 px-6">Telefono</th>
              <th className="py-4 px-6">Email</th>
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 && (
              <tr>
                <td colSpan={6} className="py-12 text-center text-zinc-600">
                  {query.trim()
                    ? 'Sin resultados para la busqueda.'
                    : 'Sin empleados. Haz clic en Cargar.'}
                </td>
              </tr>
            )}
            {paginated.map((e) => (
              <tr
                key={e.id}
                className={`border-b border-zinc-800/50 cursor-pointer transition-colors text-sm ${
                  selectedId === e.id
                    ? 'bg-blue-900/20 border-l-4 border-blue-500'
                    : 'hover:bg-zinc-800/40'
                }`}
                onClick={() => selectEmployee(e)}
              >
                <td className="py-4 px-6 font-medium">{e.employee_code || '-'}</td>
                <td className="py-4 px-6 font-medium">{e.name}</td>
                <td className="py-4 px-6 font-medium">{e.position || '-'}</td>
                <td className="py-4 px-6 font-medium">${e.base_salary.toFixed(2)}</td>
                <td className="py-4 px-6 font-medium">{e.phone || '-'}</td>
                <td className="py-4 px-6 font-medium">{e.email || '-'}</td>
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
