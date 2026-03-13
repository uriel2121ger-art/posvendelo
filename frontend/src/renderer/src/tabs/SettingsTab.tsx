import type { ReactElement } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useConfirm } from '../components/ConfirmDialog'
import {
  getSyncStatus,
  getSystemInfo,
  getBackupStatus,
  listBackups,
  buildRestorePlan,
  getLicenseStatus,
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
import { POS_API_URL } from '../runtimeEnv'

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
  Settings,
  ChevronDown,
  ChevronRight,
  Download,
  Package
} from 'lucide-react'

type SettingsTabId = 'server' | 'business' | 'printer' | 'scanner' | 'drawer'
type SettingsTabMode = 'general' | 'hardware'

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

const CONFIG_PROFILES_KEY = 'pos.configProfiles'
const HW_CACHE_KEY = 'pos.hwConfig'
const UPDATES_AUTO_KEY = 'pos.updates.autoCheck'

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
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6 mb-6">
      <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-4">
        {title}
      </h2>
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
export default function SettingsTab({
  mode = 'general',
  initialTab = 'server'
}: {
  mode?: SettingsTabMode
  initialTab?: SettingsTabId
} = {}): ReactElement {
  const confirm = useConfirm()
  const [activeTab, setActiveTab] = useState<SettingsTabId>(initialTab)
  const [advancedOpen, setAdvancedOpen] = useState(false)

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
  const [message, setMessage] = useState('Configuraciones listas: actualiza y valida conexión.')
  const [lastStatus, setLastStatus] = useState<Record<string, unknown> | null>(null)
  const [systemInfo, setSystemInfo] = useState<Record<string, unknown> | null>(null)
  const [licenseState, setLicenseState] = useState<Record<string, unknown> | null>(null)
  const [backupStatus, setBackupStatus] = useState<Record<string, unknown> | null>(null)
  const [agentStatus, setAgentStatus] = useState<Record<string, unknown> | null>(null)
  const [updatesAutoCheck, setUpdatesAutoCheck] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(UPDATES_AUTO_KEY)
      return v !== 'false'
    } catch {
      return true
    }
  })
  const [updatesChecking, setUpdatesChecking] = useState(false)
  const [backups, setBackups] = useState<Record<string, unknown>[]>([])
  const [selectedBackup, setSelectedBackup] = useState('')
  const [restorePlan, setRestorePlan] = useState<Record<string, unknown> | null>(null)
  const [cloudLinkCode, setCloudLinkCode] = useState<{
    code: string | null
    branchName: string | null
    expiresAt: string | null
  } | null>(null)

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
      const leave = window.confirm('Tienes cambios sin guardar. ¿Salir de todas formas?')
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

  useEffect(() => {
    let cancelled = false
    void getLicenseStatus(loadRuntimeConfig())
      .then((body) => {
        if (!cancelled) setLicenseState((body.data as Record<string, unknown>) ?? body)
      })
      .catch(() => {
        if (!cancelled) setLicenseState(null)
      })
    return () => { cancelled = true }
  }, [])

  const loadAgentStatus = useCallback(async () => {
    const agent = window.api?.agent
    if (!agent?.getStatus) return
    try {
      const status = await agent.getStatus()
      setAgentStatus(status as unknown as Record<string, unknown>)
    } catch {
      setAgentStatus(null)
    }
  }, [])

  useEffect(() => {
    void loadAgentStatus()
  }, [loadAgentStatus])

  const handleCheckUpdates = useCallback(async () => {
    const agent = window.api?.agent
    if (!agent?.refresh) return
    setUpdatesChecking(true)
    try {
      const status = await agent.refresh()
      setAgentStatus(status as unknown as Record<string, unknown>)
    } catch {
      setAgentStatus(null)
    } finally {
      setUpdatesChecking(false)
    }
  }, [])

  const handleToggleAutoUpdates = useCallback((enabled: boolean) => {
    setUpdatesAutoCheck(enabled)
    try {
      localStorage.setItem(UPDATES_AUTO_KEY, String(enabled))
    } catch {
      /* ignore */
    }
  }, [])

  const handlePrepareUpdate = useCallback(async () => {
    const agent = window.api?.agent
    if (!agent?.prepareAppUpdate) return
    setBusy(true)
    try {
      const status = await agent.prepareAppUpdate()
      setAgentStatus(status as unknown as Record<string, unknown>)
    } catch {
      setAgentStatus(null)
    } finally {
      setBusy(false)
    }
  }, [])

  const handleApplyUpdate = useCallback(async () => {
    const agent = window.api?.agent
    if (!agent?.applyAppUpdate) return
    setBusy(true)
    try {
      await agent.applyAppUpdate()
    } finally {
      setBusy(false)
    }
  }, [])

  function showMessage(msg: string, isError = false): void {
    setMessage(isError ? `Error: ${msg}` : msg)
  }

  // -- SERVERS METHODS --
  function persistConfig(): void {
    const url = form.baseUrl.trim()
    if (!url) return showMessage('La dirección del servidor no puede estar vacía.', true)
    try {
      new URL(url)
    } catch {
      return showMessage(`Dirección inválida. Ejemplo: ${POS_API_URL}`, true)
    }
    // Reject URLs with multiple protocol schemes (concatenation bug)
    if ((url.match(/https?:\/\//g) || []).length > 1) {
      return showMessage(
        'La dirección contiene múltiples URLs. Borra el campo y escribe solo una.',
        true
      )
    }
    if (!Number.isFinite(form.terminalId) || form.terminalId < 1) {
      return showMessage('El ID de terminal debe ser un número entero mayor o igual a 1.', true)
    }
    saveRuntimeConfig({ ...form, baseUrl: url })
    setSavedForm({ ...form, baseUrl: url })
    showMessage('Configuración de Servidor guardada en localStorage.')
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
      showMessage('Conexión correcta con backend y estado de sync obtenido.')
    } catch (error) {
      showMessage((error as Error).message, true)
      setSystemInfo(null)
      setLastStatus(null)
    } finally {
      setBusy(false)
    }
  }

  async function loadRecoveryData(): Promise<void> {
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const [statusBody, backupsBody] = await Promise.all([getBackupStatus(cfg), listBackups(cfg)])
      const nextStatus = (statusBody.data ?? statusBody) as Record<string, unknown>
      const nextBackups = (backupsBody.data ?? []) as Record<string, unknown>[]
      setBackupStatus(nextStatus)
      setBackups(Array.isArray(nextBackups) ? nextBackups : [])
      if (Array.isArray(nextBackups) && nextBackups.length > 0) {
        setSelectedBackup((current) => current || String(nextBackups[0].name ?? ''))
      }
      showMessage('Estado de respaldos actualizado.')
    } catch (error) {
      showMessage((error as Error).message, true)
      setBackupStatus(null)
      setBackups([])
    } finally {
      setBusy(false)
    }
  }

  async function prepareRestorePlan(): Promise<void> {
    if (!selectedBackup) {
      showMessage('Selecciona un respaldo antes de preparar la recuperación.', true)
      return
    }
    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const body = await buildRestorePlan(cfg, selectedBackup)
      setRestorePlan((body.data ?? body) as Record<string, unknown>)
      showMessage('Plan de recuperación preparado. Revísalo antes de ejecutar restore manual.')
    } catch (error) {
      showMessage((error as Error).message, true)
      setRestorePlan(null)
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

  const handleGenerateCloudLinkCode = async (): Promise<void> => {
    const agent = window.api?.agent
    if (!agent?.generateLinkCode) {
      showMessage('La vinculación con Nube PosVendelo requiere el agente local del desktop.', true)
      return
    }
    setBusy(true)
    try {
      const result = await agent.generateLinkCode(15)
      if (result.lastError) {
        throw new Error(result.lastError)
      }
      setCloudLinkCode({
        code: result.code,
        branchName: result.branchName,
        expiresAt: result.expiresAt
      })
      showMessage('Código de vinculación Nube PosVendelo generado.')
    } catch (error) {
      showMessage((error as Error).message, true)
    } finally {
      setBusy(false)
    }
  }

  const tabs: Array<{ id: SettingsTabId; label: string; icon: typeof Server }> = [
    { id: 'server' as const, label: 'Conexión', icon: Server },
    { id: 'business' as const, label: 'Mi negocio', icon: Building2 },
    { id: 'printer' as const, label: 'Impresora de tickets', icon: Printer },
    { id: 'drawer' as const, label: 'Cajón de dinero', icon: DoorOpen },
    { id: 'scanner' as const, label: 'Lector de códigos', icon: ScanBarcode }
  ]
  const visibleTabs =
    mode === 'hardware' ? tabs.filter((tab) => tab.id !== 'server' && tab.id !== 'business') : tabs
  const title = mode === 'hardware' ? 'Dispositivos' : 'Configuraciones generales'

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full p-4 lg:p-6 space-y-6 pb-32">
          {/* Header — mismo patrón que Productos/Clientes */}
          <div className="flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4">
            <h1 className="text-xl font-bold text-white flex items-center gap-2 truncate">
              <Settings className="w-6 h-6 text-blue-500 shrink-0" />
              <span className="truncate">{title}</span>
            </h1>
          </div>

          {message && message !== 'Configuraciones listas: actualiza y valida conexión.' && (
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

          {licenseState && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
              <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-zinc-400">
                <Key className="h-4 w-4 text-blue-400" />
                Licencia del nodo
              </div>
              <div className="grid grid-cols-1 gap-2 text-sm text-zinc-300 md:grid-cols-2">
                <div>
                  Plan:{' '}
                  <span className="font-mono text-zinc-100">
                    {String(licenseState.license_type ?? 'sin-licencia')}
                  </span>
                </div>
                <div>
                  Estado:{' '}
                  <span className="font-mono text-zinc-100">
                    {String(licenseState.effective_status ?? 'desconocido')}
                  </span>
                </div>
                <div>
                  Válida hasta:{' '}
                  <span className="font-mono text-zinc-100">
                    {String(licenseState.valid_until ?? 'sin límite')}
                  </span>
                </div>
                <div>
                  Soporte hasta:{' '}
                  <span className="font-mono text-zinc-100">
                    {String(licenseState.support_until ?? 'sin límite')}
                  </span>
                </div>
              </div>
              {typeof licenseState.message === 'string' && licenseState.message && (
                <p className="mt-3 rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-300">
                  {licenseState.message}
                </p>
              )}
            </div>
          )}

          {/* Actualizaciones — sin comandos ni terminal */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-zinc-400">
              <Package className="h-4 w-4 text-blue-400" />
              Actualizaciones
            </div>
            <p className="text-sm text-zinc-500 mb-2">
              Comprueba si hay una nueva versión de la aplicación. Si está activado, se buscarán
              actualizaciones automáticamente en segundo plano.
            </p>
            <p className="text-xs text-zinc-600 mb-4">
              Al instalar, el sistema puede pedir tu contraseña (Linux) o permisos de administrador
              (Windows) para completar la instalación. No hace falta usar comandos ni terminal.
            </p>
            <div className="flex flex-wrap items-center gap-4 mb-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={updatesAutoCheck}
                  onChange={(e) => handleToggleAutoUpdates(e.target.checked)}
                  className="rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
                />
                <span className="text-sm text-zinc-300">Buscar actualizaciones automáticamente</span>
              </label>
              <button
                type="button"
                onClick={handleCheckUpdates}
                disabled={updatesChecking || busy}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`h-4 w-4 ${updatesChecking ? 'animate-spin' : ''}`} />
                {updatesChecking ? 'Comprobando…' : 'Comprobar ahora'}
              </button>
            </div>
            {agentStatus && (
              <div className="space-y-2 text-sm text-zinc-400">
                <div>
                  Versión actual:{' '}
                  <span className="font-mono text-zinc-200">
                    {String(agentStatus.currentAppVersion ?? '—')}
                  </span>
                </div>
                {agentStatus.lastManifestCheckAt ? (
                  <div>
                    Última comprobación:{' '}
                    <span className="text-zinc-300">
                      {new Date(String(agentStatus.lastManifestCheckAt)).toLocaleString('es-MX')}
                    </span>
                  </div>
                ) : null}
                {agentStatus.lastManifestError ? (
                  <p className="rounded-lg bg-rose-500/10 border border-rose-500/20 px-3 py-2 text-rose-400 text-xs">
                    {String(agentStatus.lastManifestError)}
                  </p>
                ) : null}
                {agentStatus.appUpdateAvailable ? (
                  <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3">
                    <p className="font-medium text-emerald-400 mb-2">
                      Hay una actualización disponible
                      {agentStatus.availableAppVersion ? (
                        <span className="font-mono ml-1">
                          (versión {String(agentStatus.availableAppVersion)})
                        </span>
                      ) : null}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {agentStatus.desktopUpdate &&
                        (agentStatus.desktopUpdate as Record<string, unknown>).status === 'staged' ? (
                        <button
                          type="button"
                          onClick={handleApplyUpdate}
                          disabled={busy}
                          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                        >
                          <Package className="h-4 w-4" />
                          Instalar ahora
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={handlePrepareUpdate}
                          disabled={busy}
                          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                        >
                          <Download className="h-4 w-4" />
                          Descargar actualización
                        </button>
                      )}
                    </div>
                  </div>
                ) : null}
                {agentStatus.desktopUpdate &&
                ['downloading', 'staged'].includes(
                  String((agentStatus.desktopUpdate as Record<string, unknown>).status)
                ) ? (
                  <p className="text-xs text-zinc-500">
                    {(agentStatus.desktopUpdate as Record<string, unknown>).status === 'downloading'
                      ? 'Descargando…'
                      : 'Lista para instalar. Haz clic en "Instalar ahora".'}
                  </p>
                ) : null}
              </div>
            )}
          </div>

          {/* Master-Detail Layout */}
          <div className="flex flex-col md:flex-row gap-8">
            {/* SIDEBAR SECTIONS */}
            <div className="w-full md:w-64 space-y-1 shrink-0">
              {visibleTabs.map((tab) => (
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
                  {/* Bloque principal: solo dirección y botones */}
                  <div>
                    <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-4">
                      <Wifi className="w-4 h-4 text-zinc-500" /> Conectar con el sistema
                    </h2>
                    <p className="text-zinc-500 text-sm mb-4">
                      Indica la dirección donde está instalado el sistema (por ejemplo la IP de tu
                      servidor o equipo).
                    </p>
                    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2 mb-2">
                        Dirección del servidor
                      </label>
                      <input
                        className="w-full bg-zinc-950/50 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                        value={form.baseUrl}
                        placeholder={POS_API_URL}
                        onChange={(e) => setForm((prev) => ({ ...prev, baseUrl: e.target.value }))}
                        onFocus={(e) => e.target.select()}
                      />
                      <button
                        type="button"
                        className="mt-2 text-xs text-zinc-500 hover:text-rose-400 transition-colors"
                        onClick={() => {
                          setForm((prev) => ({ ...prev, baseUrl: POS_API_URL }))
                          showMessage(
                            'URL restablecida al valor por defecto. Haz clic en "Guardar conexión" para aplicar.'
                          )
                        }}
                      >
                        Restablecer URL por defecto
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-3 mt-6">
                      <button
                        onClick={testConnection}
                        disabled={busy}
                        className="flex-1 min-w-[120px] flex justify-center items-center gap-2 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-5 py-3 rounded-xl font-bold transition-colors disabled:opacity-50"
                      >
                        <Activity className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Probar
                        conexión
                      </button>
                      <button
                        onClick={persistConfig}
                        disabled={busy}
                        className="flex-[2] min-w-[160px] flex justify-center items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-bold transition-all hover:-translate-y-0.5 disabled:opacity-50"
                      >
                        <Save className="w-4 h-4" /> Guardar conexión
                      </button>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                    <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-4">
                      <Link2 className="w-4 h-4 text-cyan-500" /> Nube PosVendelo
                    </h2>
                    <p className="text-sm text-zinc-500 mb-4">
                      Genera un código temporal para vincular esta sucursal con la cuenta del dueño
                      desde la app móvil o desktop.
                    </p>
                    <button
                      type="button"
                      onClick={() => void handleGenerateCloudLinkCode()}
                      disabled={busy}
                      className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-cyan-500 disabled:opacity-50"
                    >
                      <Link2 className="h-4 w-4" />
                      Generar código de vinculación
                    </button>
                    {cloudLinkCode?.code && (
                      <div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3">
                        <p className="text-xs uppercase tracking-wider text-cyan-300">
                          Código actual
                        </p>
                        <p className="mt-1 font-mono text-2xl font-bold text-white">
                          {cloudLinkCode.code}
                        </p>
                        <p className="mt-2 text-sm text-zinc-300">
                          Sucursal: {cloudLinkCode.branchName ?? 'Sucursal actual'}
                        </p>
                        <p className="text-xs text-zinc-400">
                          Expira: {cloudLinkCode.expiresAt ?? 'sin dato'}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Menú desplegable para usuarios avanzados / técnicos */}
                  <div className="border border-zinc-800 rounded-2xl bg-zinc-900/30 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setAdvancedOpen((o) => !o)}
                      className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-300 transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <Link2 className="w-4 h-4 text-zinc-500" />
                        Opciones para técnicos
                      </span>
                      {advancedOpen ? (
                        <ChevronDown className="w-5 h-5 shrink-0 text-zinc-500" />
                      ) : (
                        <ChevronRight className="w-5 h-5 shrink-0 text-zinc-500" />
                      )}
                    </button>
                    {advancedOpen && (
                      <div className="border-t border-zinc-800 p-4 lg:p-6 space-y-6 animate-fade-in-up">
                        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden divide-y divide-zinc-800">
                          <div className="p-4 lg:p-6 flex flex-col gap-2">
                            <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                              <Key className="w-4 h-4" /> Token de acceso
                            </label>
                            <input
                              className="w-full bg-zinc-950/50 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
                              type="password"
                              autoComplete="off"
                              value={form.token}
                              onChange={(e) =>
                                setForm((prev) => ({ ...prev, token: e.target.value }))
                              }
                            />
                          </div>
                          <div className="p-4 lg:p-6 flex flex-col gap-2">
                            <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                              <MonitorDot className="w-4 h-4" /> ID lógico de terminal
                            </label>
                            <input
                              className="w-full bg-zinc-950/50 border border-zinc-800 rounded-xl py-3 px-4 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600"
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

                        <div>
                          <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2 mb-3">
                            <Database className="w-4 h-4" /> Perfiles de configuración local
                          </h3>
                          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6 space-y-5">
                            <div className="space-y-3">
                              <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                                Cargar perfil
                              </label>
                              <select
                                className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                                value={selectedProfileId}
                                onChange={(e) => loadProfile(e.target.value)}
                              >
                                <option value="">— Seleccionar perfil —</option>
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
                            <div className="h-px bg-zinc-800 w-full" />
                            <div className="space-y-3">
                              <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                                Guardar entorno
                              </label>
                              <input
                                className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all placeholder:text-zinc-600"
                                placeholder="Ej. Servidor principal"
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

                        {(systemInfo ||
                          lastStatus ||
                          backupStatus ||
                          backups.length > 0 ||
                          restorePlan) && (
                          <div>
                            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2 mb-3">
                              <ShieldCheck className="w-4 h-4" /> Diagnósticos
                            </h3>
                            <div className="space-y-6">
                              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                  <div>
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                                      Respaldo y recuperación
                                    </h4>
                                    <p className="mt-1 text-sm text-zinc-400">
                                      Consulta respaldos del nodo y prepara una guía de recuperación
                                      validada.
                                    </p>
                                  </div>
                                  <div className="flex gap-2">
                                    <button
                                      type="button"
                                      onClick={() => void loadRecoveryData()}
                                      disabled={busy}
                                      className="flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-2 text-sm font-semibold text-zinc-300 disabled:opacity-50"
                                    >
                                      <RefreshCw
                                        className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`}
                                      />
                                      Revisar respaldos
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => void prepareRestorePlan()}
                                      disabled={busy || !selectedBackup}
                                      className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                                    >
                                      <Database className="h-4 w-4" />
                                      Preparar recuperación
                                    </button>
                                  </div>
                                </div>

                                {backupStatus && (
                                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-3">
                                      <div className="text-[11px] uppercase tracking-wider text-zinc-500">
                                        Directorio
                                      </div>
                                      <div className="mt-1 break-all font-mono text-xs text-zinc-300">
                                        {String(backupStatus.backup_dir ?? '-')}
                                      </div>
                                    </div>
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-3">
                                      <div className="text-[11px] uppercase tracking-wider text-zinc-500">
                                        Total respaldos
                                      </div>
                                      <div className="mt-1 text-lg font-black text-white">
                                        {String(backupStatus.backup_count ?? 0)}
                                      </div>
                                    </div>
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-3">
                                      <div className="text-[11px] uppercase tracking-wider text-zinc-500">
                                        Último respaldo
                                      </div>
                                      <div className="mt-1 font-mono text-xs text-zinc-300">
                                        {String(backupStatus.latest_backup ?? 'sin respaldo')}
                                      </div>
                                    </div>
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-3">
                                      <div className="text-[11px] uppercase tracking-wider text-zinc-500">
                                        Restore soportado
                                      </div>
                                      <div className="mt-1 text-sm font-bold text-zinc-100">
                                        {backupStatus.restore_supported ? 'Sí' : 'No'}
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {backups.length > 0 && (
                                  <div className="mt-4 space-y-3">
                                    <label className="block">
                                      <span className="mb-1 block text-xs text-zinc-400">
                                        Respaldo a preparar
                                      </span>
                                      <select
                                        className="w-full rounded-xl border border-zinc-800 bg-zinc-950/80 px-4 py-3 text-sm text-zinc-200 focus:border-blue-500 focus:outline-none"
                                        value={selectedBackup}
                                        onChange={(e) => setSelectedBackup(e.target.value)}
                                      >
                                        <option value="">Selecciona un respaldo</option>
                                        {backups.map((backup, index) => (
                                          <option
                                            key={String(backup.name ?? index)}
                                            value={String(backup.name ?? '')}
                                          >
                                            {String(backup.name ?? '-')}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden">
                                      <div className="max-h-48 overflow-auto divide-y divide-zinc-800">
                                        {backups.map((backup, index) => (
                                          <div
                                            key={String(backup.name ?? index)}
                                            className="px-4 py-3 text-sm"
                                          >
                                            <div className="font-mono text-zinc-200">
                                              {String(backup.name ?? '-')}
                                            </div>
                                            <div className="mt-1 text-xs text-zinc-500">
                                              {String(backup.modified_at ?? '-')} •{' '}
                                              {String(backup.size_bytes ?? 0)} bytes
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {restorePlan && (
                                  <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
                                      <h5 className="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-500">
                                        Pasos sugeridos
                                      </h5>
                                      <ol className="space-y-2 text-sm text-zinc-300">
                                        {Array.isArray(restorePlan.steps) &&
                                          restorePlan.steps.map((step, index) => (
                                            <li
                                              key={`${index}-${String(step)}`}
                                              className="flex gap-2"
                                            >
                                              <span className="font-mono text-zinc-500">
                                                {index + 1}.
                                              </span>
                                              <span>{String(step)}</span>
                                            </li>
                                          ))}
                                      </ol>
                                    </div>
                                    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
                                      <h5 className="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-500">
                                        Comandos de referencia
                                      </h5>
                                      <pre className="overflow-x-auto text-xs font-mono text-blue-300">
                                        {Array.isArray(restorePlan.commands)
                                          ? restorePlan.commands
                                              .map((command) => String(command))
                                              .join('\n')
                                          : ''}
                                      </pre>
                                    </div>
                                  </div>
                                )}
                              </div>

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
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* HARDWARE: BUSINESS */}
              {activeTab === 'business' && hw && (
                <div className="animate-fade-in-up space-y-6">
                  <Card title="Datos del negocio en ticket">
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
                      <Field label="Razón social fiscal (opcional)">
                        <input
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.business.legal_name}
                          onChange={(e) =>
                            setHw({
                              ...hw,
                              business: { ...hw.business, legal_name: e.target.value }
                            })
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
                          list="regimen-fiscal-suggestions"
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.business.regimen}
                          placeholder="Ej. 601 - General de Ley PM, 606 - RIF, 626 - RESICO"
                          onChange={(e) =>
                            setHw({ ...hw, business: { ...hw.business, regimen: e.target.value } })
                          }
                        />
                        <datalist id="regimen-fiscal-suggestions">
                          <option value="601 - General de Ley Personas Morales" />
                          <option value="603 - Personas Morales con Fines no Lucrativos" />
                          <option value="606 - Régimen de Incorporación Fiscal (RIF)" />
                          <option value="612 - Personas Físicas con Actividades Empresariales y Profesionales" />
                          <option value="620 - Sociedades Cooperativas de Producción" />
                          <option value="621 - Incorporación Fiscal" />
                          <option value="622 - Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras" />
                          <option value="625 - Ingresos a través de Plataformas Tecnológicas" />
                          <option value="626 - Régimen Simplificado de Confianza (RESICO)" />
                        </datalist>
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
                      <Field label="Mensaje de agradecimiento o políticas (pie de ticket)" full>
                        <input
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.business.footer}
                          placeholder="Ej. ¡Gracias por su compra! Cambios solo con ticket."
                          maxLength={500}
                          onChange={(e) =>
                            setHw({ ...hw, business: { ...hw.business, footer: e.target.value } })
                          }
                        />
                      </Field>
                    </div>

                    {/* Vista previa del ticket (mismo orden que escpos) */}
                    <div className="mt-8 pt-6 border-t border-zinc-800">
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-3">
                        Vista previa del ticket
                      </p>
                      <div
                        className="mx-auto bg-[#f5f5f0] text-zinc-900 rounded-lg border border-zinc-400 shadow-inner overflow-hidden"
                        style={{ maxWidth: '320px' }}
                      >
                        <div className="p-4 font-mono text-[11px] leading-tight text-center min-h-[140px] flex flex-col items-center justify-start gap-0.5">
                          {hw.business.name ? (
                            <div className="font-bold text-sm whitespace-pre-wrap break-words max-w-full">
                              {hw.business.name}
                            </div>
                          ) : (
                            <div className="text-zinc-500 italic">Nombre del negocio</div>
                          )}
                          {hw.business.legal_name ? (
                            <div className="whitespace-pre-wrap break-words max-w-full">
                              {hw.business.legal_name}
                            </div>
                          ) : null}
                          {hw.printer.mode === 'fiscal' &&
                            (hw.business.rfc || hw.business.regimen) && (
                              <>
                                {hw.business.rfc ? <div>RFC: {hw.business.rfc}</div> : null}
                                {hw.business.regimen ? <div>{hw.business.regimen}</div> : null}
                              </>
                            )}
                          {hw.business.address ? (
                            <div className="whitespace-pre-wrap break-words max-w-full">
                              {hw.business.address}
                            </div>
                          ) : null}
                          {hw.business.phone ? <div>Tel: {hw.business.phone}</div> : null}
                          <div
                            className="w-full border-t border-zinc-500 my-1"
                            style={{ borderStyle: 'dashed' }}
                          />
                          <div className="text-zinc-500 text-[10px]">— Vista previa —</div>
                          <div
                            className="w-full border-t border-zinc-500 my-1"
                            style={{ borderStyle: 'dashed' }}
                          />
                          {hw.business.footer ? (
                            <div className="whitespace-pre-wrap break-words max-w-full mt-1">
                              {hw.business.footer}
                            </div>
                          ) : (
                            <div className="text-zinc-500 italic mt-1">
                              Mensaje de agradecimiento
                            </div>
                          )}
                        </div>
                      </div>
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
                        Actualizar diseño de ticket
                      </button>
                    </div>
                  </Card>
                </div>
              )}

              {/* HARDWARE: PRINTER */}
              {activeTab === 'printer' && hw && (
                <div className="animate-fade-in-up space-y-6">
                  <Card title="Impresora térmica predeterminada (CUPS)">
                    <div className="flex gap-4 mb-6">
                      <button
                        onClick={handleDiscover}
                        disabled={busy}
                        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 text-zinc-300 text-sm font-bold hover:bg-zinc-700 transition-colors"
                      >
                        <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Desplegar
                        red de impresoras
                      </button>
                      <button
                        onClick={handleTestPrint}
                        disabled={busy}
                        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm font-bold hover:bg-zinc-700 transition-colors"
                      >
                        Hacer prueba de impresión
                      </button>
                    </div>

                    {printers.length > 0 && (
                      <div className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
                        <table className="w-full text-sm border-collapse">
                          <thead className="sticky top-0 bg-zinc-900/80 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500 font-bold z-10">
                            <tr>
                              <th className="px-4 py-2 text-left">Impresora lógica</th>
                              <th className="px-4 py-2 text-left">Conexión</th>
                              <th className="px-4 py-2 text-left">Sistema</th>
                              <th className="px-4 py-2"></th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-800/50">
                            {printers.map((p) => (
                              <tr key={p.name} className="hover:bg-zinc-800/40 transition-colors">
                                <td className="px-4 py-2 font-mono font-medium">{p.name}</td>
                                <td className="px-4 py-2">
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
                                <td className="px-4 py-2 text-zinc-500">
                                  {p.is_default ? 'Por defecto' : ''}
                                </td>
                                <td className="px-4 py-2 text-right">
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
                      <Field label="ID impresora CUPS asignada">
                        <input
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-mono text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.printer.name}
                          onChange={(e) =>
                            setHw({ ...hw, printer: { ...hw.printer, name: e.target.value } })
                          }
                        />
                      </Field>
                      <Field label="Bobina y margen">
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
                          <option value={58}>Rollo 58mm (32 caracteres)</option>
                          <option value={80}>Rollo 80mm (48 caracteres)</option>
                        </select>
                      </Field>
                      <Field label="Modo operativo">
                        <select
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.printer.mode}
                          onChange={(e) =>
                            setHw({ ...hw, printer: { ...hw.printer, mode: e.target.value } })
                          }
                        >
                          <option value="basic">Ticket básico (simplificado)</option>
                          <option value="fiscal">Ticket fiscal (incluye RFC y desglose)</option>
                        </select>
                      </Field>
                      <Field label="Patrón de corte (guillotina)">
                        <select
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 font-semibold text-sm focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.printer.cut_type}
                          onChange={(e) =>
                            setHw({ ...hw, printer: { ...hw.printer, cut_type: e.target.value } })
                          }
                        >
                          <option value="partial">Corte parcial (recomendado)</option>
                          <option value="full">Corte completo directo</option>
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
                        onChange={(v) =>
                          setHw({ ...hw, printer: { ...hw.printer, auto_print: v } })
                        }
                      />
                    </div>

                    {/* Vista previa del ticket según papel y modo */}
                    <div className="mt-8 pt-6 border-t border-zinc-800">
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-2">
                        Vista previa del ticket
                      </p>
                      <p className="text-zinc-500 text-sm mb-3">
                        Papel {hw.printer.paper_width}mm · Modo{' '}
                        {hw.printer.mode === 'fiscal' ? 'fiscal' : 'básico'}
                        {hw.printer.paper_width === 58 && ' (32 caracteres)'}
                        {hw.printer.paper_width === 80 && ' (48 caracteres)'}
                      </p>
                      <div
                        className="mx-auto bg-[#f5f5f0] text-zinc-900 rounded-lg border border-zinc-400 shadow-inner overflow-hidden transition-all duration-200"
                        style={{
                          maxWidth: hw.printer.paper_width === 58 ? '240px' : '320px'
                        }}
                      >
                        <div
                          className={`p-4 font-mono leading-tight text-center min-h-[120px] flex flex-col items-center justify-start gap-0.5 transition-all ${
                            hw.printer.paper_width === 58 ? 'text-[10px]' : 'text-[11px]'
                          }`}
                        >
                          {hw.business.name ? (
                            <div
                              className={`font-bold whitespace-pre-wrap break-words max-w-full ${
                                hw.printer.paper_width === 58 ? 'text-xs' : 'text-sm'
                              }`}
                            >
                              {hw.business.name}
                            </div>
                          ) : (
                            <div className="text-zinc-500 italic">Nombre del negocio</div>
                          )}
                          {hw.business.legal_name ? (
                            <div className="whitespace-pre-wrap break-words max-w-full">
                              {hw.business.legal_name}
                            </div>
                          ) : null}
                          {hw.printer.mode === 'fiscal' &&
                            (hw.business.rfc || hw.business.regimen) && (
                              <>
                                {hw.business.rfc ? <div>RFC: {hw.business.rfc}</div> : null}
                                {hw.business.regimen ? <div>{hw.business.regimen}</div> : null}
                              </>
                            )}
                          {hw.business.address ? (
                            <div className="whitespace-pre-wrap break-words max-w-full">
                              {hw.business.address}
                            </div>
                          ) : null}
                          {hw.business.phone ? <div>Tel: {hw.business.phone}</div> : null}
                          <div
                            className="w-full border-t border-zinc-500 my-1"
                            style={{ borderStyle: 'dashed' }}
                          />
                          <div className="text-zinc-500 text-[10px]">— Vista previa —</div>
                          <div
                            className="w-full border-t border-zinc-500 my-1"
                            style={{ borderStyle: 'dashed' }}
                          />
                          {hw.business.footer ? (
                            <div className="whitespace-pre-wrap break-words max-w-full mt-1">
                              {hw.business.footer}
                            </div>
                          ) : (
                            <div className="text-zinc-500 italic mt-1">
                              Mensaje de agradecimiento
                            </div>
                          )}
                        </div>
                      </div>
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
                        Guardar perfil impresora
                      </button>
                    </div>
                  </Card>
                </div>
              )}

              {/* HARDWARE: SCANNER */}
              {activeTab === 'scanner' && hw && (
                <div className="animate-fade-in-up space-y-6">
                  <Card title="Comportamiento del escáner de barras">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <Field label="Carácter inicial de barrido (Prefijo)">
                        <input
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.scanner.prefix}
                          placeholder="Normalmente sin prefijo"
                          onChange={(e) =>
                            setHw({ ...hw, scanner: { ...hw.scanner, prefix: e.target.value } })
                          }
                        />
                      </Field>
                      <Field label="Carácter de cierre (sufijo)">
                        <input
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-950/80 py-3 px-4 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                          value={hw.scanner.suffix}
                          placeholder="Generalmente \n o \r"
                          onChange={(e) =>
                            setHw({ ...hw, scanner: { ...hw.scanner, suffix: e.target.value } })
                          }
                        />
                      </Field>
                      <Field label="Tolerancia humana (ms entre teclas)">
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
                        label="Utilizar modo escáner dedicado"
                        checked={hw.scanner.enabled}
                        onChange={(v) => setHw({ ...hw, scanner: { ...hw.scanner, enabled: v } })}
                      />
                      <Toggle
                        label="Agregar producto al carrito automáticamente"
                        checked={hw.scanner.auto_submit}
                        onChange={(v) =>
                          setHw({ ...hw, scanner: { ...hw.scanner, auto_submit: v } })
                        }
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
                        Ajustar escáner
                      </button>
                    </div>
                  </Card>
                </div>
              )}

              {/* HARDWARE: DRAWER */}
              {activeTab === 'drawer' && hw && (
                <div className="animate-fade-in-up space-y-6">
                  <Card title="Gatillo de apertura (cajón RJ11)">
                    <div className="flex gap-4 mb-6">
                      <button
                        onClick={handleTestDrawer}
                        disabled={busy}
                        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 text-zinc-300 text-sm font-bold hover:bg-zinc-700 transition-colors"
                      >
                        <DoorOpen className="w-5 h-5 text-amber-500" /> Confirmar puente serial /
                        EXP
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                      <Field label="Nombre de impresora emisora del cajón">
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
                        label="Permitir interactuar con el cajón"
                        checked={hw.drawer.enabled}
                        onChange={(v) => setHw({ ...hw, drawer: { ...hw.drawer, enabled: v } })}
                      />
                      <Toggle
                        label="Soltar caja al cobrar en efectivo"
                        checked={hw.drawer.auto_open_cash}
                        onChange={(v) =>
                          setHw({ ...hw, drawer: { ...hw.drawer, auto_open_cash: v } })
                        }
                      />
                      <Toggle
                        label="Soltar caja tras validación tarjeta"
                        checked={hw.drawer.auto_open_card}
                        onChange={(v) =>
                          setHw({ ...hw, drawer: { ...hw.drawer, auto_open_card: v } })
                        }
                      />
                      <Toggle
                        label="Soltar caja tras validación transferencia"
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
                        Guardar comportamiento
                      </button>
                    </div>
                  </Card>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
