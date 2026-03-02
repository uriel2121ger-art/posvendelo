import type { ReactElement } from 'react'
import { useEffect, useRef, useState } from 'react'

import { useConfirm } from './components/ConfirmDialog'
import { getSyncStatus, getSystemInfo, loadRuntimeConfig, saveRuntimeConfig } from './posApi'
import { Server, ShieldCheck, Wifi, Key, Save, Trash2, Database, AlertCircle, Activity, Link2, MonitorDot } from 'lucide-react'

type RuntimeState = {
  baseUrl: string
  token: string
  terminalId: number
}

type ConfigProfile = {
  id: string
  name: string
  baseUrl: string
  token: string
  terminalId: number
}

const CONFIG_PROFILES_KEY = 'titan.configProfiles'

function parseTerminalId(value: string): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.max(1, Math.floor(parsed))
}

export default function SettingsTab(): ReactElement {
  const confirm = useConfirm()
  const [form, setForm] = useState<RuntimeState>(() => {
    const cfg = loadRuntimeConfig()
    return { baseUrl: cfg.baseUrl, token: cfg.token, terminalId: cfg.terminalId }
  })
  const [savedForm, setSavedForm] = useState<RuntimeState>(() => {
    const cfg = loadRuntimeConfig()
    return { baseUrl: cfg.baseUrl, token: cfg.token, terminalId: cfg.terminalId }
  })
  const isDirty = JSON.stringify(form) !== JSON.stringify(savedForm)

  // Warn on window/tab close when dirty
  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent): void => { e.preventDefault() }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  // Intercept hash navigation when dirty (F-key navigation)
  const suppressRef = useRef(false)
  useEffect(() => {
    if (!isDirty) return
    const savedHash = window.location.hash
    const onHashChange = (): void => {
      if (suppressRef.current) { suppressRef.current = false; return }
      const leave = window.confirm('Tienes cambios sin guardar. ¿Deseas salir sin guardar?')
      if (!leave) {
        suppressRef.current = true
        window.location.hash = savedHash
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [isDirty])

  const [busy, setBusy] = useState(false)
  const [profileName, setProfileName] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [profiles, setProfiles] = useState<ConfigProfile[]>(() => {
    try {
      const raw = localStorage.getItem(CONFIG_PROFILES_KEY)
      if (!raw) return []
      const parsed = JSON.parse(raw) as ConfigProfile[]
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  })
  const [message, setMessage] = useState('Configuraciones listas: actualiza y valida conexion.')
  const [lastStatus, setLastStatus] = useState<Record<string, unknown> | null>(null)
  const [systemInfo, setSystemInfo] = useState<Record<string, unknown> | null>(null)

  function persistConfig(): void {
    const url = form.baseUrl.trim()
    if (!url) {
      setMessage('Error: Base URL no puede estar vacia.')
      return
    }
    try {
      new URL(url)
    } catch {
      setMessage('Error: Base URL invalida. Ejemplo: http://127.0.0.1:8000')
      return
    }
    if (!Number.isFinite(form.terminalId) || form.terminalId < 1) {
      setMessage('Error: Terminal ID debe ser un numero entero >= 1.')
      return
    }
    saveRuntimeConfig({ ...form, baseUrl: url })
    setSavedForm({ ...form, baseUrl: url })
    setMessage('Configuracion guardada en localStorage.')
  }

  function persistProfiles(next: ConfigProfile[]): void {
    setProfiles(next)
    try {
      localStorage.setItem(CONFIG_PROFILES_KEY, JSON.stringify(next))
    } catch {
      /* QuotaExceeded */
    }
  }

  function saveProfile(): void {
    const name = profileName.trim()
    if (!name) {
      setMessage('Captura un nombre para el perfil.')
      return
    }
    const next: ConfigProfile = {
      id: `profile-${Date.now()}`,
      name,
      baseUrl: form.baseUrl,
      token: '',  // SECURITY: tokens excluded from saved profiles
      terminalId: form.terminalId
    }
    const merged = [
      next,
      ...profiles.filter((p) => p.name.toLowerCase() !== name.toLowerCase())
    ].slice(0, 20)
    persistProfiles(merged)
    setSelectedProfileId(next.id)
    setMessage(`Perfil guardado: ${name}`)
  }

  function loadProfile(profileId: string): void {
    setSelectedProfileId(profileId)
    const found = profiles.find((p) => p.id === profileId)
    if (!found) return
    setForm({ baseUrl: found.baseUrl, token: found.token, terminalId: found.terminalId })
    setProfileName(found.name)
    setMessage(`Perfil cargado: ${found.name}`)
  }

  async function deleteProfile(): Promise<void> {
    if (!selectedProfileId) {
      setMessage('Selecciona un perfil para eliminar.')
      return
    }
    const target = profiles.find((p) => p.id === selectedProfileId)
    if (!await confirm(`¿Eliminar perfil "${target?.name ?? selectedProfileId}"?`, { variant: 'danger', title: 'Eliminar perfil' })) return
    const next = profiles.filter((p) => p.id !== selectedProfileId)
    persistProfiles(next)
    setSelectedProfileId('')
    setMessage(`Perfil eliminado: ${target?.name ?? selectedProfileId}`)
  }

  async function testConnection(): Promise<void> {
    setBusy(true)
    try {
      const info = await getSystemInfo(form)
      const syncStatus = await getSyncStatus(form)
      setSystemInfo(info)
      setLastStatus(syncStatus)
      setMessage('Conexion correcta con backend y estado de sync obtenido.')
    } catch (error) {
      setMessage((error as Error).message)
      setSystemInfo(null)
      setLastStatus(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-screen bg-[#09090b] font-sans text-slate-200 select-none overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full p-6 md:p-8 space-y-8 pb-32">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <h1 className="text-3xl font-black text-white flex items-center gap-3 tracking-tight">
              <Server className="w-8 h-8 text-blue-500" />
              Configuración del Servidor
            </h1>
            <p className="text-zinc-500 mt-2 font-medium">
              Ajustes de conexión al backend, credenciales de API y perfiles de terminal.
            </p>
          </div>
          <div className="flex items-center gap-3">
             <button
                onClick={() => void testConnection()} disabled={busy}
                className="flex items-center gap-2 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-5 py-2.5 rounded-xl font-bold transition-colors disabled:opacity-50"
             >
                <Activity className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} />
                {busy ? 'Probando...' : 'Test de Conexión'}
             </button>
             <button
                onClick={persistConfig} disabled={busy}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-xl font-bold shadow-[0_4px_20px_-5px_rgba(59,130,246,0.4)] transition-all hover:-translate-y-0.5 disabled:opacity-50"
             >
                <Save className="w-4 h-4" /> Guardar Cambios
             </button>
          </div>
        </div>

        {message && message !== 'Configuraciones listas: actualiza y valida conexion.' && (
           <div className="bg-blue-500/10 border border-blue-500/20 text-blue-400 px-4 py-3 rounded-xl flex items-center gap-3 text-sm font-semibold animate-fade-in-up">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <p>{message}</p>
           </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
           
           {/* Connection Settings */}
           <div className="space-y-6">
              <div>
                 <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                    <Link2 className="w-4 h-4 text-zinc-500" /> Red y Autenticación
                 </h2>
                 <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl overflow-hidden divide-y divide-zinc-800/60">
                    
                    {/* Base URL */}
                    <div className="p-5 flex flex-col gap-2">
                       <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                          <Wifi className="w-4 h-4" /> Base URL del Backend
                       </label>
                       <input
                          className="w-full bg-zinc-950/50 border border-zinc-800/80 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                          value={form.baseUrl} placeholder="http://127.0.0.1:8000"
                          onChange={(e) => setForm((prev) => ({ ...prev, baseUrl: e.target.value }))}
                       />
                       <p className="text-[10px] text-zinc-600">IP local o dominio de internet donde reside la BD principal.</p>
                    </div>

                    {/* Token */}
                    <div className="p-5 flex flex-col gap-2">
                       <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                          <Key className="w-4 h-4" /> Access Token
                       </label>
                       <input
                          className="w-full bg-zinc-950/50 border border-zinc-800/80 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                          type="password" autoComplete="off" value={form.token} placeholder="Token de API"
                          onChange={(e) => setForm((prev) => ({ ...prev, token: e.target.value }))}
                       />
                       <p className="text-[10px] text-zinc-600">Clave de autorización JWT o API Key para conectarse.</p>
                    </div>

                    {/* Terminal ID */}
                    <div className="p-5 flex flex-col gap-2">
                       <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                          <MonitorDot className="w-4 h-4" /> ID Lógico de Terminal
                       </label>
                       <input
                          className="w-full bg-zinc-950/50 border border-zinc-800/80 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                          type="number" min={1} value={form.terminalId} placeholder="1"
                          onChange={(e) => setForm((prev) => ({ ...prev, terminalId: parseTerminalId(e.target.value) }))}
                       />
                       <p className="text-[10px] text-zinc-600">Para separar arqueos y cierres en operación multi-caja.</p>
                    </div>

                 </div>
              </div>
           </div>

           {/* Profiles */}
           <div className="space-y-6">
              <div>
                 <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                    <Database className="w-4 h-4 text-zinc-500" /> Perfiles de Configuración
                 </h2>
                 <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-5 space-y-5">
                    
                    <div className="space-y-3">
                       <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Cargar Perfil</label>
                       <select
                          className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={selectedProfileId} onChange={(e) => loadProfile(e.target.value)}
                       >
                          <option value="">(Seleccionar / Sin perfil)</option>
                          {profiles.map((profile) => (
                             <option key={profile.id} value={profile.id}>{profile.name}</option>
                          ))}
                       </select>
                       <button
                          onClick={deleteProfile} disabled={busy || !selectedProfileId}
                          className="w-full flex items-center justify-center gap-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 border border-rose-500/20 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-50"
                       >
                          <Trash2 className="w-4 h-4" /> Eliminar perfil seleccionado
                       </button>
                    </div>

                    <div className="h-px bg-zinc-800/60 w-full" />

                    <div className="space-y-3">
                       <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Guardar Entorno Actual</label>
                       <input
                          className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                          placeholder="Ej. Servidor Nube Principal" value={profileName} onChange={(e) => setProfileName(e.target.value)}
                       />
                       <button
                          onClick={saveProfile} disabled={busy || !profileName.trim()}
                          className="w-full flex items-center justify-center gap-2 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-50"
                       >
                          <Save className="w-4 h-4" /> Guardar como nuevo perfil
                       </button>
                    </div>
                 </div>
              </div>
           </div>

        </div>

        {/* Status Responses */}
        {(systemInfo || lastStatus) && (
           <div className="pt-8 border-t border-zinc-800 animate-fade-in-up">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                 <ShieldCheck className="w-4 h-4 text-zinc-500" /> Diagnósticos del Servidor
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 {systemInfo && (
                    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden">
                       <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/50 text-xs font-bold text-zinc-400 uppercase tracking-widest flex justify-between">
                          <span>Info del Sistema</span>
                       </div>
                       <pre className="p-4 text-[10px] font-mono text-emerald-400 overflow-x-auto max-h-60 overflow-y-auto">
                          {JSON.stringify(systemInfo, null, 2)}
                       </pre>
                    </div>
                 )}
                 {lastStatus && (
                    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden">
                       <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/50 text-xs font-bold text-zinc-400 uppercase tracking-widest flex justify-between">
                          <span>Estado de Sincronización</span>
                       </div>
                       <pre className="p-4 text-[10px] font-mono text-blue-400 overflow-x-auto max-h-60 overflow-y-auto">
                          {JSON.stringify(lastStatus, null, 2)}
                       </pre>
                    </div>
                 )}
              </div>
           </div>
        )}

      </div>
    </div>
  )
}
