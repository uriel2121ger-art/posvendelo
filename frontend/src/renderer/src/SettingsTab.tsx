import type { ReactElement } from 'react'
import { useState } from 'react'
import TopNavbar from './components/TopNavbar'
import { getSyncStatus, getSystemInfo, loadRuntimeConfig, saveRuntimeConfig } from './posApi'

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
  const initial = loadRuntimeConfig()
  const [form, setForm] = useState<RuntimeState>({
    baseUrl: initial.baseUrl,
    token: initial.token,
    terminalId: initial.terminalId
  })
  const [busy, setBusy] = useState(false)
  const [profileName, setProfileName] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [profiles, setProfiles] = useState<ConfigProfile[]>(() => {
    const raw = localStorage.getItem(CONFIG_PROFILES_KEY)
    if (!raw) return []
    try {
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
    saveRuntimeConfig(form)
    setMessage('Configuracion guardada en localStorage.')
  }

  function persistProfiles(next: ConfigProfile[]): void {
    setProfiles(next)
    localStorage.setItem(CONFIG_PROFILES_KEY, JSON.stringify(next))
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
      token: form.token,
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

  function deleteProfile(): void {
    if (!selectedProfileId) {
      setMessage('Selecciona un perfil para eliminar.')
      return
    }
    const target = profiles.find((p) => p.id === selectedProfileId)
    if (!window.confirm(`¿Eliminar perfil "${target?.name ?? selectedProfileId}"?`)) return
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
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_1fr_160px_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={form.baseUrl}
          placeholder="Base URL"
          onChange={(e) => setForm((prev) => ({ ...prev, baseUrl: e.target.value }))}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="password"
          autoComplete="off"
          value={form.token}
          placeholder="Token"
          onChange={(e) => setForm((prev) => ({ ...prev, token: e.target.value }))}
        />
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={1}
          value={form.terminalId}
          placeholder="Terminal ID"
          onChange={(e) =>
            setForm((prev) => ({
              ...prev,
              terminalId: parseTerminalId(e.target.value)
            }))
          }
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={persistConfig}
          disabled={busy}
        >
          Guardar
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={() => void testConnection()}
          disabled={busy}
        >
          {busy ? 'Probando...' : 'Probar conexion'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900 p-4 md:grid-cols-[1fr_1fr_auto_auto]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          placeholder="Nombre del perfil (ej. Caja 1)"
          value={profileName}
          onChange={(e) => setProfileName(e.target.value)}
        />
        <select
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={selectedProfileId}
          onChange={(e) => loadProfile(e.target.value)}
        >
          <option value="">Seleccionar perfil...</option>
          {profiles.map((profile) => (
            <option key={profile.id} value={profile.id}>
              {profile.name}
            </option>
          ))}
        </select>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={saveProfile}
          disabled={busy}
        >
          Guardar perfil
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={deleteProfile}
          disabled={busy || !selectedProfileId}
        >
          Eliminar perfil
        </button>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-4 md:grid-cols-2">
        <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="mb-3 font-semibold">Info del sistema</h3>
          {!systemInfo && <p className="text-sm text-zinc-400">Sin informacion.</p>}
          {systemInfo && (
            <pre className="max-h-96 overflow-auto rounded border border-zinc-800 bg-zinc-950 p-2 text-xs">
              {JSON.stringify(systemInfo, null, 2)}
            </pre>
          )}
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
          <h3 className="mb-3 font-semibold">Estado de sincronizacion</h3>
          {!lastStatus && <p className="text-sm text-zinc-400">Sin informacion.</p>}
          {lastStatus && (
            <pre className="max-h-96 overflow-auto rounded border border-zinc-800 bg-zinc-950 p-2 text-xs">
              {JSON.stringify(lastStatus, null, 2)}
            </pre>
          )}
        </div>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
