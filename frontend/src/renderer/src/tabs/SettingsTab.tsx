import type { ReactElement } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useConfirm } from '../components/ConfirmDialog'
import {
  getSyncStatus,
  getSystemInfo,
  loadRuntimeConfig,
  saveRuntimeConfig,
  type RuntimeConfig,
  type HardwareConfig,
  type CupsPrinter,
  getHardwareConfig,
  updateHardwareConfig,
  discoverPrinters,
  testPrint,
  testDrawer
} from '../posApi'

import {
  Server,
  ShieldCheck,
  Wifi,
  Key,
  Save,
  Trash2,
  Database,
  AlertCircle,
  Activity,
  Link2,
  MonitorDot,
  Printer,
  ScanBarcode,
  DoorOpen,
  Building2,
  RefreshCw,
  Settings
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------
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
const HW_CACHE_KEY = 'titan.hwConfig'

function saveToCache(cfg: HardwareConfig): void {
  try {
    localStorage.setItem(HW_CACHE_KEY, JSON.stringify(cfg))
  } catch {
    /* quota exceeded */
  }
}

function parseTerminalId(value: string): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.max(1, Math.floor(parsed))
}

// ---------------------------------------------------------------------------
// Reusable Local Components
// ---------------------------------------------------------------------------
function Card({ title, children }: { title: string; children: React.ReactNode }): ReactElement {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <h2 className="text-lg font-bold mb-4 text-zinc-200">{title}</h2>
      {children}
    </div>
  )
}

function Field({
  label,
  children,
  full
}: {
  label: string
  children: React.ReactNode
  full?: boolean
}): ReactElement {
  return (
    <label className={`block ${full ? 'md:col-span-2' : ''}`}>
      <span className="text-xs text-zinc-400 mb-1 block">{label}</span>
      {children}
    </label>
  )
}

function Toggle({
  label,
  checked,
  onChange
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}): ReactElement {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none py-1">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors ${
          checked ? 'bg-blue-600' : 'bg-zinc-700'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
      <span className="text-sm text-zinc-300">{label}</span>
    </label>
  )
}

// ---------------------------------------------------------------------------
// Main Tab Component
// ---------------------------------------------------------------------------
export default function SettingsTab(): ReactElement {
  const confirm = useConfirm()
  const [activeTab, setActiveTab] = useState<
    'server' | 'business' | 'printer' | 'scanner' | 'drawer'
  >('server')

  // -- Server Config State --
  const [form, setForm] = useState<RuntimeState>(() => {
    const cfg = loadRuntimeConfig()
    return { baseUrl: cfg.baseUrl, token: cfg.token, terminalId: cfg.terminalId }
  })
  const [savedForm, setSavedForm] = useState<RuntimeState>(() => {
    const cfg = loadRuntimeConfig()
    return { baseUrl: cfg.baseUrl, token: cfg.token, terminalId: cfg.terminalId }
  })

  // -- HW Config State --
  const [hwConfig] = useState<RuntimeConfig>(loadRuntimeConfig)
  const [hw, setHw] = useState<HardwareConfig | null>(null)
  const [savedHw, setSavedHw] = useState<HardwareConfig | null>(null)
  const [printers, setPrinters] = useState<CupsPrinter[]>([])

  // -- UI State --
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Configuraciones listas: actualiza y valida conexion.')
  const [lastStatus, setLastStatus] = useState<Record<string, unknown> | null>(null)
  const [systemInfo, setSystemInfo] = useState<Record<string, unknown> | null>(null)

  // -- Profiles State --
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

  const isServerDirty = JSON.stringify(form) !== JSON.stringify(savedForm)
  const isHwDirty =
    hw !== null && savedHw !== null && JSON.stringify(hw) !== JSON.stringify(savedHw)
  const isDirty = isServerDirty || isHwDirty

  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent): void => {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  const suppressRef = useRef(false)
  useEffect(() => {
    if (!isDirty) return
    const savedHash = window.location.hash
    const onHashChange = (): void => {
      if (suppressRef.current) {
        suppressRef.current = false
        return
      }
      const leave = window.confirm('Tienes cambios sin guardar. ¿Deseas salir sin guardar?')
      if (!leave) {
        suppressRef.current = true
        window.location.hash = savedHash
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [isDirty])

  const loadHwData = useCallback(async () => {
    try {
      const data = await getHardwareConfig(hwConfig)
      setHw(data)
      setSavedHw(data)
      saveToCache(data)
    } catch {
      // Ignored initially
    }
  }, [hwConfig])

  useEffect(() => {
    loadHwData()
  }, [loadHwData])

  function showMessage(msg: string, isError = false): void {
    setMessage(isError ? `Error: ${msg}` : msg)
  }

  // -- SERVERS METHODS --
  function persistConfig(): void {
    const url = form.baseUrl.trim()
    if (!url) return showMessage('Base URL no puede estar vacia.', true)
    try {
      new URL(url)
    } catch {
      return showMessage('Base URL invalida. Ejemplo: http://127.0.0.1:8000', true)
    }
    if (!Number.isFinite(form.terminalId) || form.terminalId < 1) {
      return showMessage('Terminal ID debe ser un numero entero >= 1.', true)
    }
    saveRuntimeConfig({ ...form, baseUrl: url })
    setSavedForm({ ...form, baseUrl: url })
    showMessage('Configuracion de Servidor guardada en localStorage.')
  }

  function persistProfiles(next: ConfigProfile[]): void {
    setProfiles(next)
    try {
      localStorage.setItem(CONFIG_PROFILES_KEY, JSON.stringify(next))
    } catch {
      // quota exceeded or localStorage unavailable
    }
  }

  function saveProfile(): void {
    const name = profileName.trim()
    if (!name) return showMessage('Captura un nombre para el perfil.', true)
    const next: ConfigProfile = {
      id: `profile-${Date.now()}`,
      name,
      baseUrl: form.baseUrl,
      token: '',
      terminalId: form.terminalId
    }
    const merged = [
      next,
      ...profiles.filter((p) => p.name.toLowerCase() !== name.toLowerCase())
    ].slice(0, 20)
    persistProfiles(merged)
    setSelectedProfileId(next.id)
    showMessage(`Perfil guardado: ${name}`)
  }

  function loadProfile(profileId: string): void {
    setSelectedProfileId(profileId)
    const found = profiles.find((p) => p.id === profileId)
    if (!found) return
    setForm({ baseUrl: found.baseUrl, token: found.token, terminalId: found.terminalId })
    setProfileName(found.name)
    showMessage(`Perfil cargado: ${found.name}${!found.token ? ' (Token vacío)' : ''}`)
  }

  async function deleteProfile(): Promise<void> {
    if (!selectedProfileId) return showMessage('Selecciona un perfil para eliminar.', true)
    const target = profiles.find((p) => p.id === selectedProfileId)
    if (
      !(await confirm(`¿Eliminar perfil "${target?.name ?? selectedProfileId}"?`, {
        variant: 'danger',
        title: 'Eliminar perfil'
      }))
    )
      return
    const next = profiles.filter((p) => p.id !== selectedProfileId)
    persistProfiles(next)
    setSelectedProfileId('')
    showMessage(`Perfil eliminado: ${target?.name ?? selectedProfileId}`)
  }

  async function testConnection(): Promise<void> {
    setBusy(true)
    try {
      const savedCfg = loadRuntimeConfig()
      const testCfg = { ...savedCfg, baseUrl: form.baseUrl, terminalId: form.terminalId }
      const info = await getSystemInfo(testCfg)
      const syncStatus = await getSyncStatus(testCfg)
      setSystemInfo(info)
      setLastStatus(syncStatus)
      showMessage('Conexion correcta con backend y estado de sync obtenido.')
    } catch (error) {
      showMessage((error as Error).message, true)
      setSystemInfo(null)
      setLastStatus(null)
    } finally {
      setBusy(false)
    }
  }

  // -- HW METHODS --
  const handleSaveHw = async (
    sec: 'printer' | 'business' | 'scanner' | 'drawer',
    body: Record<string, unknown>
  ): Promise<void> => {
    setBusy(true)
    try {
      await updateHardwareConfig(hwConfig, sec, body)
      await loadHwData()
      showMessage('Ajustes guardados correctamente')
    } catch (error) {
      showMessage((error as Error).message, true)
    } finally {
      setBusy(false)
    }
  }

  const handleDiscover = async (): Promise<void> => {
    setBusy(true)
    try {
      const list = await discoverPrinters(hwConfig)
      setPrinters(list)
      showMessage(`${list.length} impresora(s) detectada(s)`)
    } catch (error) {
      showMessage((error as Error).message, true)
    } finally {
      setBusy(false)
    }
  }

  const handleTestPrint = async (): Promise<void> => {
    setBusy(true)
    try {
      await testPrint(hwConfig)
      showMessage('Ticket de prueba enviado a cola de impresión')
    } catch (error) {
      showMessage((error as Error).message, true)
    } finally {
      setBusy(false)
    }
  }

  const handleTestDrawer = async (): Promise<void> => {
    setBusy(true)
    try {
      await testDrawer(hwConfig)
      showMessage('Comando de apertura de cajón enviado')
    } catch (error) {
      showMessage((error as Error).message, true)
    } finally {
      setBusy(false)
    }
  }

  const TABS = [
    { id: 'server' as const, label: 'Servidor y Enlaces', icon: Server },
    { id: 'business' as const, label: 'Datos del Negocio', icon: Building2 },
    { id: 'printer' as const, label: 'Impresoras y Tickets', icon: Printer },
    { id: 'drawer' as const, label: 'Cajón de Dinero', icon: DoorOpen },
    { id: 'scanner' as const, label: 'Lector de Códigos', icon: ScanBarcode }
  ]

  return (
    <div className="flex flex-col h-full bg-[#09090b] font-sans text-slate-200 select-none">
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8 pb-32">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <h1 className="text-3xl font-black text-white flex items-center gap-3 tracking-tight">
              <Settings className="w-8 h-8 text-blue-500" />
              Configuraciones Generales
            </h1>
            <p className="text-zinc-500 mt-2 font-medium">
              Ajustes de conexión al backend, módulos de hardware, impresoras y perfiles del
              sistema.
            </p>
          </div>
        </div>

        {message && message !== 'Configuraciones listas: actualiza y valida conexion.' && (
          <div
            className={`px-4 py-3 rounded-xl flex items-center gap-3 text-sm font-semibold animate-fade-in-up border ${
              message.startsWith('Error')
                ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            }`}
          >
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p>{message}</p>
          </div>
        )}

        {/* Master-Detail Layout */}
        <div className="flex flex-col md:flex-row gap-8">
          {/* SIDEBAR SECTIONS */}
          <div className="w-full md:w-64 space-y-1 shrink-0">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20'
                    : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200 border border-transparent'
                }`}
              >
                <tab.icon
                  className={`w-5 h-5 ${activeTab === tab.id ? 'text-blue-400' : 'text-zinc-500'}`}
                />
                {tab.label}
              </button>
            ))}
          </div>

          {/* CONTENT SECTIONS */}
          <div className="flex-1 min-w-0">
            {/* SERVER SETTINGS */}
            {activeTab === 'server' && (
              <div className="animate-fade-in-up space-y-6">
                <div>
                  <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                    <Link2 className="w-4 h-4 text-zinc-500" /> Red y Autenticación
                  </h2>
                  <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl overflow-hidden divide-y divide-zinc-800/60">
                    <div className="p-5 flex flex-col gap-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                        <Wifi className="w-4 h-4" /> Base URL del Backend
                      </label>
                      <input
                        className="w-full bg-zinc-950/50 border border-zinc-800/80 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                        value={form.baseUrl}
                        placeholder="http://127.0.0.1:8000"
                        onChange={(e) => setForm((prev) => ({ ...prev, baseUrl: e.target.value }))}
                      />
                    </div>
                    <div className="p-5 flex flex-col gap-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                        <Key className="w-4 h-4" /> Access Token
                      </label>
                      <input
                        className="w-full bg-zinc-950/50 border border-zinc-800/80 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                        type="password"
                        autoComplete="off"
                        value={form.token}
                        onChange={(e) => setForm((prev) => ({ ...prev, token: e.target.value }))}
                      />
                    </div>
                    <div className="p-5 flex flex-col gap-2">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                        <MonitorDot className="w-4 h-4" /> ID Lógico de Terminal
                      </label>
                      <input
                        className="w-full bg-zinc-950/50 border border-zinc-800/80 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                        type="number"
                        min={1}
                        value={form.terminalId}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            terminalId: parseTerminalId(e.target.value)
                          }))
                        }
                      />
                    </div>
                  </div>

                  <div className="flex gap-4 mt-6">
                    <button
                      onClick={testConnection}
                      disabled={busy}
                      className="flex-1 flex justify-center items-center gap-2 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-5 py-3 rounded-xl font-bold transition-colors disabled:opacity-50"
                    >
                      <Activity className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Test
                    </button>
                    <button
                      onClick={persistConfig}
                      disabled={busy}
                      className="flex-[2] flex justify-center items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-bold transition-all hover:-translate-y-0.5 disabled:opacity-50"
                    >
                      <Save className="w-4 h-4" /> Guardar Conexión
                    </button>
                  </div>
                </div>

                <div className="pt-6 border-t border-zinc-800">
                  <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                    <Database className="w-4 h-4 text-zinc-500" /> Perfiles de Configuración Local
                  </h2>
                  <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-3xl p-5 space-y-5">
                    <div className="space-y-3">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                        Cargar Perfil
                      </label>
                      <select
                        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={selectedProfileId}
                        onChange={(e) => loadProfile(e.target.value)}
                      >
                        <option value="">(Seleccionar / Sin perfil)</option>
                        {profiles.map((profile) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={deleteProfile}
                        disabled={busy || !selectedProfileId}
                        className="w-full flex items-center justify-center gap-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 border border-rose-500/20 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-50"
                      >
                        <Trash2 className="w-4 h-4" /> Eliminar perfil seleccionado
                      </button>
                    </div>

                    <div className="h-px bg-zinc-800/60 w-full" />

                    <div className="space-y-3">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                        Guardar Entorno
                      </label>
                      <input
                        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                        placeholder="Ej. Servidor Principal"
                        value={profileName}
                        onChange={(e) => setProfileName(e.target.value)}
                      />
                      <button
                        onClick={saveProfile}
                        disabled={busy || !profileName.trim()}
                        className="w-full flex items-center justify-center gap-2 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-50"
                      >
                        <Save className="w-4 h-4" /> Guardar como nuevo perfil
                      </button>
                    </div>
                  </div>
                </div>

                {/* Status Dump */}
                {(systemInfo || lastStatus) && (
                  <div className="pt-8 border-t border-zinc-800 animate-fade-in-up">
                    <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 mb-4">
                      <ShieldCheck className="w-4 h-4 text-zinc-500" /> Diagnósticos
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {systemInfo && (
                        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden">
                          <pre className="p-4 text-[10px] font-mono text-emerald-400 overflow-x-auto max-h-40 overflow-y-auto">
                            {JSON.stringify(systemInfo, null, 2)}
                          </pre>
                        </div>
                      )}
                      {lastStatus && (
                        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden">
                          <pre className="p-4 text-[10px] font-mono text-blue-400 overflow-x-auto max-h-40 overflow-y-auto">
                            {JSON.stringify(lastStatus, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* HARDWARE: BUSINESS */}
            {activeTab === 'business' && hw && (
              <div className="animate-fade-in-up space-y-6">
                <Card title="Datos del Negocio en Ticket">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Field label="Nombre del negocio / Sucursal">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.business.name}
                        onChange={(e) =>
                          setHw({ ...hw, business: { ...hw.business, name: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Razón social fiscal (Opcional)">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.business.legal_name}
                        onChange={(e) =>
                          setHw({ ...hw, business: { ...hw.business, legal_name: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="RFC / Tax ID">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all uppercase"
                        value={hw.business.rfc}
                        maxLength={13}
                        onChange={(e) =>
                          setHw({
                            ...hw,
                            business: { ...hw.business, rfc: e.target.value.toUpperCase() }
                          })
                        }
                      />
                    </Field>
                    <Field label="Régimen fiscal">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.business.regimen}
                        onChange={(e) =>
                          setHw({ ...hw, business: { ...hw.business, regimen: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Teléfono / WhatsApp">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.business.phone}
                        onChange={(e) =>
                          setHw({ ...hw, business: { ...hw.business, phone: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Dirección matriz/sucursal" full>
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.business.address}
                        onChange={(e) =>
                          setHw({ ...hw, business: { ...hw.business, address: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Mensaje de agradecimiento o Políticas (Pie de ticket)" full>
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.business.footer}
                        placeholder="Ej. ¡Gracias por su compra! Cambios solo con ticket."
                        onChange={(e) =>
                          setHw({ ...hw, business: { ...hw.business, footer: e.target.value } })
                        }
                      />
                    </Field>
                  </div>
                  <div className="mt-6 flex justify-end">
                    <button
                      disabled={busy}
                      onClick={() =>
                        handleSaveHw('business', {
                          business_name: hw.business.name,
                          business_legal_name: hw.business.legal_name,
                          business_address: hw.business.address,
                          business_rfc: hw.business.rfc,
                          business_regimen: hw.business.regimen,
                          business_phone: hw.business.phone,
                          business_footer: hw.business.footer
                        })
                      }
                      className="px-6 py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-500 transition-colors"
                    >
                      Actualizar Diseño de Ticket
                    </button>
                  </div>
                </Card>
              </div>
            )}

            {/* HARDWARE: PRINTER */}
            {activeTab === 'printer' && hw && (
              <div className="animate-fade-in-up space-y-6">
                <Card title="Impresora Térmica Predeterminada (CUPS)">
                  <div className="flex gap-4 mb-6">
                    <button
                      onClick={handleDiscover}
                      disabled={busy}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 text-zinc-300 text-sm font-bold hover:bg-zinc-700 transition-colors"
                    >
                      <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Desplegar
                      Red de Impresoras
                    </button>
                    <button
                      onClick={handleTestPrint}
                      disabled={busy}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm font-bold hover:bg-zinc-700 transition-colors"
                    >
                      Hacer Prueba de Impresión
                    </button>
                  </div>

                  {printers.length > 0 && (
                    <div className="mb-6 border border-zinc-700 rounded-xl overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-zinc-800/80 text-zinc-400 uppercase text-xs">
                          <tr>
                            <th className="px-4 py-3 text-left">Impresora Lógica</th>
                            <th className="px-4 py-3 text-left">Conexión</th>
                            <th className="px-4 py-3 text-left">Sistema</th>
                            <th className="px-4 py-3"></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-800">
                          {printers.map((p) => (
                            <tr key={p.name} className="hover:bg-zinc-800/30">
                              <td className="px-4 py-3 font-mono font-medium">{p.name}</td>
                              <td className="px-4 py-3">
                                <span
                                  className={
                                    p.enabled
                                      ? 'text-emerald-400 font-medium'
                                      : 'text-rose-400 font-medium'
                                  }
                                >
                                  {p.status}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-zinc-500">
                                {p.is_default ? 'Por Defecto' : ''}
                              </td>
                              <td className="px-4 py-3 text-right">
                                <button
                                  onClick={() =>
                                    handleSaveHw('printer', { receipt_printer_name: p.name })
                                  }
                                  className="text-xs font-bold text-blue-400 hover:text-blue-300 bg-blue-500/10 px-3 py-1.5 rounded-lg"
                                >
                                  Usar esta
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Field label="ID Impresora CUPS Asignada">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-mono text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.printer.name}
                        onChange={(e) =>
                          setHw({ ...hw, printer: { ...hw.printer, name: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Bobina y Margen">
                      <select
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.printer.paper_width}
                        onChange={(e) => {
                          const w = Number(e.target.value)
                          setHw({
                            ...hw,
                            printer: {
                              ...hw.printer,
                              paper_width: w,
                              char_width: w === 58 ? 32 : 48
                            }
                          })
                        }}
                      >
                        <option value={58}>Rollo 58mm (32 chars)</option>
                        <option value={80}>Rollo 80mm (48 chars)</option>
                      </select>
                    </Field>
                    <Field label="Modo Operativo">
                      <select
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.printer.mode}
                        onChange={(e) =>
                          setHw({ ...hw, printer: { ...hw.printer, mode: e.target.value } })
                        }
                      >
                        <option value="basic">Ticket Básico (Simplificado)</option>
                        <option value="fiscal">Ticket Fiscal (Incluye RFC y Desglose)</option>
                      </select>
                    </Field>
                    <Field label="Patrón de Corte (Guillotina)">
                      <select
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.printer.cut_type}
                        onChange={(e) =>
                          setHw({ ...hw, printer: { ...hw.printer, cut_type: e.target.value } })
                        }
                      >
                        <option value="partial">Corte Parcial (Recomendado)</option>
                        <option value="full">Corte Completo Directo</option>
                      </select>
                    </Field>
                  </div>

                  <div className="flex flex-col gap-3 mt-6 border-t border-zinc-800 pt-6">
                    <Toggle
                      label="Permitir emisión de tickets"
                      checked={hw.printer.enabled}
                      onChange={(v) => setHw({ ...hw, printer: { ...hw.printer, enabled: v } })}
                    />
                    <Toggle
                      label="Lanzar ticket al cobrar venta automáticamente"
                      checked={hw.printer.auto_print}
                      onChange={(v) => setHw({ ...hw, printer: { ...hw.printer, auto_print: v } })}
                    />
                  </div>

                  <div className="mt-8 flex justify-end">
                    <button
                      disabled={busy}
                      onClick={() =>
                        handleSaveHw('printer', {
                          receipt_printer_name: hw.printer.name,
                          receipt_printer_enabled: hw.printer.enabled,
                          receipt_paper_width: hw.printer.paper_width,
                          receipt_char_width: hw.printer.char_width,
                          receipt_auto_print: hw.printer.auto_print,
                          receipt_mode: hw.printer.mode,
                          receipt_cut_type: hw.printer.cut_type
                        })
                      }
                      className="px-6 py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-500 transition-colors"
                    >
                      Gurdar Perfil Impresora
                    </button>
                  </div>
                </Card>
              </div>
            )}

            {/* HARDWARE: SCANNER */}
            {activeTab === 'scanner' && hw && (
              <div className="animate-fade-in-up space-y-6">
                <Card title="Comportamiento del Escáner de Barras">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Field label="Cáracter Inicial de Barrido (Prefijo)">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.scanner.prefix}
                        placeholder="Normalmente sin prefijo"
                        onChange={(e) =>
                          setHw({ ...hw, scanner: { ...hw.scanner, prefix: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Cáracter de Cierre (Sufijo)">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.scanner.suffix}
                        placeholder="Generalmente \n o \r"
                        onChange={(e) =>
                          setHw({ ...hw, scanner: { ...hw.scanner, suffix: e.target.value } })
                        }
                      />
                    </Field>
                    <Field label="Tolerancia Humana (ms entre teclas)">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                        type="number"
                        min={10}
                        max={500}
                        value={hw.scanner.min_speed_ms}
                        onChange={(e) =>
                          setHw({
                            ...hw,
                            scanner: { ...hw.scanner, min_speed_ms: Number(e.target.value) || 50 }
                          })
                        }
                      />
                    </Field>
                  </div>

                  <div className="flex flex-col gap-3 mt-6 border-t border-zinc-800 pt-6">
                    <Toggle
                      label="Utilizar modo Escáner Dedicado"
                      checked={hw.scanner.enabled}
                      onChange={(v) => setHw({ ...hw, scanner: { ...hw.scanner, enabled: v } })}
                    />
                    <Toggle
                      label="Agregar producto al carrito automáticamente (Auto-submit)"
                      checked={hw.scanner.auto_submit}
                      onChange={(v) => setHw({ ...hw, scanner: { ...hw.scanner, auto_submit: v } })}
                    />
                  </div>

                  <div className="mt-8 flex justify-end">
                    <button
                      disabled={busy}
                      onClick={() =>
                        handleSaveHw('scanner', {
                          scanner_enabled: hw.scanner.enabled,
                          scanner_prefix: hw.scanner.prefix,
                          scanner_suffix: hw.scanner.suffix,
                          scanner_min_speed_ms: hw.scanner.min_speed_ms,
                          scanner_auto_submit: hw.scanner.auto_submit
                        })
                      }
                      className="px-6 py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-500 transition-colors"
                    >
                      Ajustar Escáner
                    </button>
                  </div>
                </Card>
              </div>
            )}

            {/* HARDWARE: DRAWER */}
            {activeTab === 'drawer' && hw && (
              <div className="animate-fade-in-up space-y-6">
                <Card title="Gatillo de Apertura (Cajón RJ11)">
                  <div className="flex gap-4 mb-6">
                    <button
                      onClick={handleTestDrawer}
                      disabled={busy}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 text-zinc-300 text-sm font-bold hover:bg-zinc-700 transition-colors"
                    >
                      <DoorOpen className="w-5 h-5 text-amber-500" /> Confirmar Puente Serial / EXP
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <Field label="Nombre de Impresora Emisora del Cajón">
                      <input
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                        value={hw.drawer.printer_name}
                        placeholder="Ej. POS-80C"
                        onChange={(e) =>
                          setHw({ ...hw, drawer: { ...hw.drawer, printer_name: e.target.value } })
                        }
                      />
                    </Field>
                  </div>

                  <div className="flex flex-col gap-4 border-t border-zinc-800 pt-6">
                    <Toggle
                      label="Permitir interactuar con el Cajón"
                      checked={hw.drawer.enabled}
                      onChange={(v) => setHw({ ...hw, drawer: { ...hw.drawer, enabled: v } })}
                    />
                    <Toggle
                      label="Soltar caja al cobrar un Efectivo"
                      checked={hw.drawer.auto_open_cash}
                      onChange={(v) =>
                        setHw({ ...hw, drawer: { ...hw.drawer, auto_open_cash: v } })
                      }
                    />
                    <Toggle
                      label="Soltar caja tras validación Tarjeta"
                      checked={hw.drawer.auto_open_card}
                      onChange={(v) =>
                        setHw({ ...hw, drawer: { ...hw.drawer, auto_open_card: v } })
                      }
                    />
                    <Toggle
                      label="Soltar caja tras validación Transferencia"
                      checked={hw.drawer.auto_open_transfer}
                      onChange={(v) =>
                        setHw({ ...hw, drawer: { ...hw.drawer, auto_open_transfer: v } })
                      }
                    />
                  </div>

                  <div className="mt-8 flex justify-end">
                    <button
                      disabled={busy}
                      onClick={() =>
                        handleSaveHw('drawer', {
                          cash_drawer_enabled: hw.drawer.enabled,
                          printer_name: hw.drawer.printer_name,
                          cash_drawer_auto_open_cash: hw.drawer.auto_open_cash,
                          cash_drawer_auto_open_card: hw.drawer.auto_open_card,
                          cash_drawer_auto_open_transfer: hw.drawer.auto_open_transfer
                        })
                      }
                      className="px-6 py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-500 transition-colors"
                    >
                      Guardar Comportamiento
                    </button>
                  </div>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
