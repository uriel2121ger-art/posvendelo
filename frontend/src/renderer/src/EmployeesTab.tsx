import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useConfirm } from './components/ConfirmDialog'
import {
  loadRuntimeConfig,
  getUserRole,
  listEmployees,
  createEmployee,
  updateEmployee,
  deleteEmployee
} from './posApi'
import { Users, Search, Plus, X, UserCog, Mail, Phone, Briefcase, DollarSign, Percent, RefreshCw } from 'lucide-react'

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
  const confirm = useConfirm()
  const [employees, setEmployees] = useState<Employee[]>([])
  const [query, setQuery] = useState('')
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
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

  // Clamp page when filtered data shrinks (e.g. after delete or reload with fewer items)
  useEffect(() => {
    const maxPage = Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1)
    setPage((p) => Math.min(p, maxPage))
  }, [filtered.length])

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
    if (!code.trim()) {
      setMessage('Codigo de empleado es obligatorio.')
      return
    }
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
        commission_rate: toNumber(commission) / 100,
        phone: phone.trim(),
        email: email.trim(),
        notes: notes.trim()
      }
      if (selectedId) {
        await updateEmployee(cfg, selectedId, body)
        setEmployees((prev) =>
          prev.map((e) => (e.id === selectedId ? { ...e, ...body, id: selectedId } : e))
        )
        setMessage(`Empleado actualizado: ${body.name}`); setIsDrawerOpen(false)
      } else {
        const result = await createEmployee(cfg, body)
        const data = (result.data ?? result) as Record<string, unknown>
        const newEmp = normalizeEmployee({ ...body, id: data.id ?? Date.now() })
        if (newEmp) setEmployees((prev) => [newEmp, ...prev])
        setMessage(`Empleado creado: ${body.name}`); setIsDrawerOpen(false)
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
    if (!await confirm(`¿Eliminar empleado "${target.name}"?`, { variant: 'danger', title: 'Eliminar empleado' })) return
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      await deleteEmployee(cfg, selectedId)
      setEmployees((prev) => prev.filter((e) => e.id !== selectedId))
      resetForm()
      setMessage(`Empleado eliminado: ${target.name}`); setIsDrawerOpen(false)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function selectEmployee(emp: Employee): void {
    setIsDrawerOpen(true)
    setSelectedId(emp.id)
    setCode(emp.employee_code)
    setName(emp.name)
    setPosition(emp.position)
    setSalary(emp.base_salary.toFixed(2))
    setCommission((emp.commission_rate * 100).toFixed(2))
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
    <div className="flex h-screen bg-[#09090b] font-sans text-slate-200 select-none overflow-hidden relative">
      <div className="flex flex-col flex-1 max-w-7xl mx-auto w-full p-4 md:p-6 lg:p-8 h-full">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 shrink-0">
          <div>
            <h1 className="text-3xl font-black text-white flex items-center gap-3 tracking-tight">
              <Users className="w-8 h-8 text-indigo-500" />
              Directorio de Personal
            </h1>
            <p className="text-zinc-500 mt-1 font-medium">
              Gestión de empleados, accesos, comisiones y salarios base.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative group w-full md:w-80">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-zinc-500" />
              </div>
              <input
                type="text"
                className="block w-full pl-10 pr-3 py-2.5 bg-zinc-900 border border-zinc-800 rounded-xl leading-5 text-zinc-300 placeholder-zinc-500 focus:outline-none focus:bg-zinc-950 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-medium sm:text-sm"
                placeholder="Buscar por nombre, código o contacto..."
                value={query}
                onChange={(e) => setQuery(e.target.value.replace(/[\x00-\x1F\x7F-\x9F]/g, ''))}
              />
            </div>
            
            <button
              onClick={() => { resetForm(); setIsDrawerOpen(true); }}
              disabled={!canEdit}
              className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/20 disabled:opacity-50"
            >
              <Plus className="w-5 h-5" /> <span className="hidden sm:inline">Nuevo Empleado</span>
            </button>
            <button
              className="flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2.5 rounded-xl transition-colors disabled:opacity-50"
              onClick={() => void handleLoad()} disabled={busy}
            >
              <RefreshCw className={`w-5 h-5 ${busy ? 'animate-spin text-indigo-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* Master List (Grid) */}
        <div className="flex-1 bg-zinc-900/40 border border-zinc-800/60 rounded-3xl overflow-hidden flex flex-col relative z-0">
           
           <div className="flex-1 overflow-auto custom-scrollbar p-6">
              {paginated.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-zinc-500 space-y-4">
                  <UserCog className="w-16 h-16 opacity-20" />
                  <p className="text-lg font-medium">{query.trim() ? 'No se encontraron coincidencias.' : 'No hay empleados registrados.'}</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {paginated.map((emp) => (
                    <div
                      key={emp.id}
                      onClick={() => selectEmployee(emp)}
                      className={`group relative bg-zinc-900 border ${selectedId === emp.id ? 'border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.15)] scale-[1.02]' : 'border-zinc-800 hover:border-zinc-700 hover:-translate-y-1'} rounded-2xl p-5 cursor-pointer transition-all duration-200 overflow-hidden flex flex-col`}
                    >
                      <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
                         <Users className="w-24 h-24 -mt-8 -mr-8 text-indigo-500" />
                      </div>
                      <div className="flex justify-between items-start mb-4 relative z-10">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-md">
                           {emp.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="bg-zinc-950/80 text-zinc-400 border border-zinc-800/50 px-2 py-1 rounded text-[10px] font-mono font-bold tracking-wider uppercase">
                          {emp.employee_code || 'S/N'}
                        </span>
                      </div>
                      
                      <div className="flex-1 relative z-10">
                         <h3 className="font-bold text-base text-zinc-100 mb-1 truncate">{emp.name}</h3>
                         <p className="text-xs text-indigo-400 font-medium mb-4 flex items-center gap-1.5"><Briefcase className="w-3.5 h-3.5" /> {emp.position || 'Sin puesto'}</p>
                         
                         <div className="space-y-2 mt-auto text-xs text-zinc-500 font-medium">
                            {emp.phone && <div className="flex items-center gap-2 truncate"><Phone className="w-3.5 h-3.5" />{emp.phone}</div>}
                            {emp.email && <div className="flex items-center gap-2 truncate"><Mail className="w-3.5 h-3.5" />{emp.email}</div>}
                         </div>
                      </div>
                      
                      <div className="mt-4 pt-3 border-t border-zinc-800/80 flex justify-between items-center relative z-10">
                         <div className="text-xs">
                           <span className="text-zinc-500 block">Salario Base</span>
                           <span className="font-mono font-bold text-white">${emp.base_salary.toFixed(2)}</span>
                         </div>
                         <div className="text-xs text-right">
                           <span className="text-zinc-500 block">Comisión</span>
                           <span className="font-mono font-bold text-emerald-400">{(emp.commission_rate * 100).toFixed(1)}%</span>
                         </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
           </div>

           {/* Pagination Footer */}
           <div className="bg-zinc-950 px-6 py-4 border-t border-zinc-800 flex items-center justify-between shrink-0">
             <div className="text-sm text-zinc-500 font-medium">
               Mostrando <span className="text-white">{paginated.length}</span> de <span className="text-white">{filtered.length}</span> empleados
             </div>
             {totalPages > 1 && (
               <div className="flex items-center gap-2">
                 <button
                   className="px-3 py-1.5 rounded-lg border border-zinc-700 text-sm font-medium hover:bg-zinc-800 disabled:opacity-30 transition-colors"
                   onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
                 >
                   Anterior
                 </button>
                 <span className="text-zinc-400 text-sm font-medium px-2">
                   {page + 1} de {totalPages}
                 </span>
                 <button
                   className="px-3 py-1.5 rounded-lg border border-zinc-700 text-sm font-medium hover:bg-zinc-800 disabled:opacity-30 transition-colors"
                   onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                 >
                   Siguiente
                 </button>
               </div>
             )}
           </div>
        </div>
      </div>

      {/* Persistent Status Bar */}
      {message && message !== 'Empleados: gestiona tu equipo de trabajo.' && !message.startsWith('Empleados cargados') && (
         <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-zinc-900 border border-zinc-700 text-white px-6 py-3 rounded-2xl shadow-2xl flex items-center gap-3 animate-fade-in-up">
            <span className="text-sm font-semibold truncate">{message}</span>
         </div>
      )}

      {/* Detail Slide Drawer */}
      <div className={`fixed inset-0 z-[100] flex justify-end transition-opacity duration-300 ${isDrawerOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setIsDrawerOpen(false)} />
        
        {/* Drawer Panel */}
        <div className={`relative w-full max-w-md bg-zinc-950 border-l border-zinc-800 h-full flex flex-col transform transition-transform duration-300 ease-out shadow-2xl ${isDrawerOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          
          <div className="flex items-center justify-between p-6 border-b border-zinc-800 bg-zinc-900/40">
            <div className="flex items-center gap-3">
               <div className="w-10 h-10 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                 <UserCog className="w-5 h-5" />
               </div>
               <h2 className="text-xl font-bold text-white tracking-tight">{selectedId ? 'Editar Perfil' : 'Nuevo Empleado'}</h2>
            </div>
            <button className="text-zinc-500 hover:text-white transition-colors bg-zinc-900 hover:bg-zinc-800 p-2 rounded-full" onClick={() => setIsDrawerOpen(false)}>
               <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
            
            <div className="space-y-4">
               <div>
                 <label className="text-xs font-bold uppercase tracking-widest text-zinc-500 mb-2 block">Identidad</label>
                 <div className="space-y-3">
                   <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500"><UserCog className="w-4 h-4" /></div>
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 pl-10 pr-4 font-semibold focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600 text-zinc-200"
                        placeholder="Nombre completo" value={name} onChange={(e) => setName(e.target.value)}
                      />
                   </div>
                   <div className="grid grid-cols-2 gap-3">
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 px-4 font-mono text-sm focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600 text-zinc-200 uppercase"
                        placeholder="Cód. Interno" value={code} onChange={(e) => setCode(e.target.value)}
                      />
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 px-4 font-medium text-sm focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600 text-zinc-200"
                        placeholder="Cargo / Puesto" value={position} onChange={(e) => setPosition(e.target.value)}
                      />
                   </div>
                 </div>
               </div>

               <div className="pt-4 border-t border-zinc-800/60">
                 <label className="text-xs font-bold uppercase tracking-widest text-zinc-500 mb-2 block">Contacto</label>
                 <div className="space-y-3">
                   <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500"><Phone className="w-4 h-4" /></div>
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 pl-10 pr-4 font-mono text-sm focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600 text-zinc-200"
                        placeholder="Número telefónico" value={phone} onChange={(e) => setPhone(e.target.value)}
                      />
                   </div>
                   <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500"><Mail className="w-4 h-4" /></div>
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 pl-10 pr-4 font-medium text-sm focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600 text-zinc-200"
                        placeholder="Correo electrónico" value={email} onChange={(e) => setEmail(e.target.value)}
                      />
                   </div>
                 </div>
               </div>

               <div className="pt-4 border-t border-zinc-800/60">
                 <label className="text-xs font-bold uppercase tracking-widest text-zinc-500 mb-2 block">Compensación</label>
                 <div className="grid grid-cols-2 gap-3">
                   <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-emerald-500"><DollarSign className="w-4 h-4" /></div>
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 pl-10 pr-4 font-mono font-bold text-emerald-400 focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600"
                        placeholder="Salario Base" type="number" min={0} value={salary} onChange={(e) => setSalary(e.target.value)}
                      />
                   </div>
                   <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-indigo-400"><Percent className="w-4 h-4" /></div>
                      <input
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 py-3 pl-10 pr-4 font-mono font-bold text-indigo-300 focus:border-indigo-500 focus:outline-none transition-all placeholder:text-zinc-600"
                        placeholder="Comisión %" type="number" min={0} value={commission} onChange={(e) => setCommission(e.target.value)}
                      />
                   </div>
                 </div>
               </div>

            </div>
            
          </div>

          <div className="p-6 border-t border-zinc-800 bg-zinc-900/80 flex flex-col gap-3">
            <button
               className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-3.5 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/20 disabled:opacity-50"
               onClick={() => void handleSave()} disabled={busy || !canEdit || !name.trim() || !code.trim()}
            >
               {busy ? <RefreshCw className="w-5 h-5 animate-spin" /> : <UserCog className="w-5 h-5" />}
               {selectedId ? 'Actualizar Ficha' : 'Crear Empleado'}
            </button>
            {selectedId && (
              <button
                className="w-full flex items-center justify-center gap-2 bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 py-3 rounded-xl font-bold transition-colors disabled:opacity-50 border border-rose-500/20"
                onClick={() => void handleDelete()} disabled={busy || !canEdit}
              >
                Eliminar Registro
              </button>
            )}
          </div>
        </div>
      </div>
      
    </div>
  )
}
