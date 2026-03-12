import type { ReactElement } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, User, LogIn, RefreshCw, Server, Settings, Wifi } from 'lucide-react'
import { autoDiscoverBackend, checkNeedsFirstUser, loadRuntimeConfig, saveRuntimeConfig } from './posApi'
import { TITAN_APP_LABEL, TITAN_RELEASE_LABEL } from './runtimeEnv'

type AgentStatusView = {
  configLoaded: boolean
  backendHealthy: boolean
  controlPlaneUrl: string | null
  localApiUrl: string
  branchId: number | null
  ownerSessionReady: boolean
  ownerAccessMode: 'owner-session' | 'install-token' | 'unavailable'
  companionUrl: string | null
  companionEntryUrl: string | null
  ownerSessionUrl: string | null
  ownerApiBaseUrl: string | null
  quickLinks: {
    ownerPortfolio: string | null
    ownerDevices: string | null
    ownerRemote: string | null
  }
  lastBackendError: string | null
  currentAppVersion: string | null
  appVersion: string | null
  backendVersion: string | null
  appUpdateAvailable: boolean
  backendUpdateAvailable: boolean
  availableBackendVersion: string | null
  licenseType: string | null
  licenseStatus: string
  licenseMessage: string | null
  licenseDaysRemaining: number | null
  licenseValidSignature: boolean
  desktopUpdateStatus: 'idle' | 'available' | 'downloading' | 'staged' | 'applying' | 'error'
  desktopUpdateMessage: string | null
  desktopUpdateVersion: string | null
  desktopUpdateError: string | null
  desktopUpdateReady: boolean
  desktopRollbackAvailable: boolean
  desktopRollbackVersion: string | null
  desktopRollbackMessage: string | null
  backendUpdateStatus: 'idle' | 'available' | 'applying' | 'error'
  backendUpdateMessage: string | null
  backendUpdateVersion: string | null
  backendUpdateError: string | null
  backendRollbackAvailable: boolean
  backendRollbackVersion: string | null
  backendRollbackMessage: string | null
}

function getUpdateStatusLabel(status: AgentStatusView['desktopUpdateStatus']): string {
  switch (status) {
    case 'idle':
      return 'sin actividad'
    case 'available':
      return 'disponible'
    case 'downloading':
      return 'descargando'
    case 'staged':
      return 'lista para aplicar'
    case 'applying':
      return 'aplicando'
    case 'error':
      return 'con error'
    default:
      return 'desconocido'
  }
}

export default function Login(): ReactElement {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [discovering, setDiscovering] = useState(true)
  const [refreshingAgent, setRefreshingAgent] = useState(false)
  const [updatingApp, setUpdatingApp] = useState(false)
  const [error, setError] = useState('')
  const [agentStatus, setAgentStatus] = useState<AgentStatusView | null>(null)
  const navigate = useNavigate()
  const footerLabel = TITAN_RELEASE_LABEL
    ? `V ${TITAN_RELEASE_LABEL} • ${TITAN_APP_LABEL}`
    : TITAN_APP_LABEL

  // Redirigir al wizard si nunca se ha guardado una URL (primera vez o instalador antiguo sin este flujo)
  useEffect(() => {
    try {
      const saved = localStorage.getItem('titan.baseUrl')
      if (saved != null && saved.trim() !== '') return
      navigate('/configurar-servidor', { replace: true })
    } catch {
      navigate('/configurar-servidor', { replace: true })
    }
  }, [navigate])

  // Si no hay token y el sistema no tiene usuarios, redirigir al wizard de primer usuario
  useEffect(() => {
    let cancelled = false
    try {
      const token = localStorage.getItem('titan.token')
      if (token) return // Already logged in — no redirect needed
    } catch {
      /* ignore storage errors */
    }
    const cfg = loadRuntimeConfig()
    checkNeedsFirstUser(cfg)
      .then((needed) => {
        if (!cancelled && needed) {
          navigate('/setup-inicial-usuario', { replace: true })
        }
      })
      .catch(() => {
        /* best-effort — if check fails, stay on login */
      })
    return () => {
      cancelled = true
    }
  }, [navigate])

  const refreshAgentStatus = async (): Promise<void> => {
    const api = (window as Window & { api?: { agent?: { refresh?: () => Promise<unknown> } } }).api
    if (typeof api?.agent?.refresh !== 'function') return

    setRefreshingAgent(true)
    try {
      const raw = (await api.agent.refresh()) as {
        configLoaded?: boolean
        backendHealthy?: boolean
        controlPlaneUrl?: string | null
        localApiUrl?: string
        branchId?: number | null
        ownerSessionReady?: boolean
        ownerAccessMode?: AgentStatusView['ownerAccessMode']
        companionUrl?: string | null
        companionEntryUrl?: string | null
        ownerSessionUrl?: string | null
        ownerApiBaseUrl?: string | null
        quickLinks?: AgentStatusView['quickLinks']
        lastBackendError?: string | null
        currentAppVersion?: string | null
        backendVersion?: string | null
        appUpdateAvailable?: boolean
        backendUpdateAvailable?: boolean
        availableBackendVersion?: string | null
        license?: {
          licenseType?: string | null
          effectiveStatus?: string
          message?: string | null
          daysRemaining?: number | null
          validSignature?: boolean
        }
        desktopUpdate?: {
          status?: AgentStatusView['desktopUpdateStatus']
          message?: string | null
          availableVersion?: string | null
          lastError?: string | null
          rollbackAvailable?: boolean
          rollbackVersion?: string | null
          rollbackMessage?: string | null
        }
        backendUpdate?: {
          status?: AgentStatusView['backendUpdateStatus']
          message?: string | null
          availableVersion?: string | null
          lastError?: string | null
          rollbackAvailable?: boolean
          rollbackVersion?: string | null
          rollbackMessage?: string | null
        }
        manifest?: {
          artifacts?: {
            app?: { version?: string | null } | null
            backend?: { version?: string | null } | null
          }
        } | null
      }
      setAgentStatus({
        configLoaded: Boolean(raw.configLoaded),
        backendHealthy: Boolean(raw.backendHealthy),
        controlPlaneUrl: raw.controlPlaneUrl ?? null,
        localApiUrl: raw.localApiUrl || 'http://127.0.0.1:8000',
        branchId: raw.branchId ?? null,
        ownerSessionReady: raw.ownerSessionReady === true,
        ownerAccessMode: raw.ownerAccessMode ?? 'unavailable',
        companionUrl: raw.companionUrl ?? null,
        companionEntryUrl: raw.companionEntryUrl ?? null,
        ownerSessionUrl: raw.ownerSessionUrl ?? null,
        ownerApiBaseUrl: raw.ownerApiBaseUrl ?? null,
        quickLinks: {
          ownerPortfolio: raw.quickLinks?.ownerPortfolio ?? null,
          ownerDevices: raw.quickLinks?.ownerDevices ?? null,
          ownerRemote: raw.quickLinks?.ownerRemote ?? null
        },
        lastBackendError: raw.lastBackendError ?? null,
        currentAppVersion: raw.currentAppVersion ?? null,
        appVersion: raw.manifest?.artifacts?.app?.version ?? null,
        backendVersion: raw.backendVersion ?? null,
        appUpdateAvailable: Boolean(raw.appUpdateAvailable),
        backendUpdateAvailable: Boolean(raw.backendUpdateAvailable),
        availableBackendVersion:
          raw.availableBackendVersion ?? raw.manifest?.artifacts?.backend?.version ?? null,
        licenseType: raw.license?.licenseType ?? null,
        licenseStatus: raw.license?.effectiveStatus ?? 'missing',
        licenseMessage: raw.license?.message ?? null,
        licenseDaysRemaining:
          typeof raw.license?.daysRemaining === 'number' ? raw.license.daysRemaining : null,
        licenseValidSignature: raw.license?.validSignature !== false,
        desktopUpdateStatus: raw.desktopUpdate?.status ?? 'idle',
        desktopUpdateMessage: raw.desktopUpdate?.message ?? null,
        desktopUpdateVersion:
          raw.desktopUpdate?.availableVersion ?? raw.manifest?.artifacts?.app?.version ?? null,
        desktopUpdateError: raw.desktopUpdate?.lastError ?? null,
        desktopUpdateReady: raw.desktopUpdate?.status === 'staged',
        desktopRollbackAvailable: raw.desktopUpdate?.rollbackAvailable === true,
        desktopRollbackVersion: raw.desktopUpdate?.rollbackVersion ?? null,
        desktopRollbackMessage: raw.desktopUpdate?.rollbackMessage ?? null,
        backendUpdateStatus: raw.backendUpdate?.status ?? 'idle',
        backendUpdateMessage: raw.backendUpdate?.message ?? null,
        backendUpdateVersion:
          raw.backendUpdate?.availableVersion ?? raw.manifest?.artifacts?.backend?.version ?? null,
        backendUpdateError: raw.backendUpdate?.lastError ?? null,
        backendRollbackAvailable: raw.backendUpdate?.rollbackAvailable === true,
        backendRollbackVersion: raw.backendUpdate?.rollbackVersion ?? null,
        backendRollbackMessage: raw.backendUpdate?.rollbackMessage ?? null
      })
    } catch {
      setAgentStatus(null)
    } finally {
      setRefreshingAgent(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    autoDiscoverBackend()
      .then((url) => {
        if (cancelled) return
        if (!url) setError('No se encontró el servidor. Verifica que esté encendido.')
      })
      .finally(() => {
        if (!cancelled) setDiscovering(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void refreshAgentStatus()
  }, [])

  const handlePrepareAppUpdate = async (): Promise<void> => {
    const api = (
      window as Window & {
        api?: { agent?: { prepareAppUpdate?: () => Promise<unknown> } }
      }
    ).api
    if (typeof api?.agent?.prepareAppUpdate !== 'function') return
    setUpdatingApp(true)
    try {
      await api.agent.prepareAppUpdate()
      await refreshAgentStatus()
    } finally {
      setUpdatingApp(false)
    }
  }

  const handleApplyAppUpdate = async (): Promise<void> => {
    const api = (
      window as Window & {
        api?: { agent?: { applyAppUpdate?: () => Promise<unknown> } }
      }
    ).api
    if (typeof api?.agent?.applyAppUpdate !== 'function') return
    setUpdatingApp(true)
    try {
      await api.agent.applyAppUpdate()
      await refreshAgentStatus()
    } finally {
      setUpdatingApp(false)
    }
  }

  const handleDiscardAppUpdate = async (): Promise<void> => {
    const api = (
      window as Window & {
        api?: { agent?: { discardAppUpdate?: () => Promise<unknown> } }
      }
    ).api
    if (typeof api?.agent?.discardAppUpdate !== 'function') return
    setUpdatingApp(true)
    try {
      await api.agent.discardAppUpdate()
      await refreshAgentStatus()
    } finally {
      setUpdatingApp(false)
    }
  }

  const handleRollbackAppUpdate = async (): Promise<void> => {
    const api = (
      window as Window & {
        api?: { agent?: { rollbackAppUpdate?: () => Promise<unknown> } }
      }
    ).api
    if (typeof api?.agent?.rollbackAppUpdate !== 'function') return
    setUpdatingApp(true)
    try {
      await api.agent.rollbackAppUpdate()
      await refreshAgentStatus()
    } finally {
      setUpdatingApp(false)
    }
  }

  const handleApplyBackendUpdate = async (): Promise<void> => {
    const api = (
      window as Window & {
        api?: { agent?: { applyBackendUpdate?: () => Promise<unknown> } }
      }
    ).api
    if (typeof api?.agent?.applyBackendUpdate !== 'function') return
    setUpdatingApp(true)
    try {
      await api.agent.applyBackendUpdate()
      await refreshAgentStatus()
    } finally {
      setUpdatingApp(false)
    }
  }

  const handleRollbackBackendUpdate = async (): Promise<void> => {
    const api = (
      window as Window & {
        api?: { agent?: { rollbackBackendUpdate?: () => Promise<unknown> } }
      }
    ).api
    if (typeof api?.agent?.rollbackBackendUpdate !== 'function') return
    setUpdatingApp(true)
    try {
      await api.agent.rollbackBackendUpdate()
      await refreshAgentStatus()
    } finally {
      setUpdatingApp(false)
    }
  }

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault()
    setError('')

    if (!username.trim() || password.length === 0) {
      setError('Por favor, ingresa tu usuario y contraseña.')
      return
    }

    setLoading(true)

    try {
      const cfg = loadRuntimeConfig()
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 8000)
      let res: Response
      try {
        res = await fetch(`${cfg.baseUrl}/api/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: username.trim(), password }),
          signal: controller.signal
        })
      } finally {
        clearTimeout(timeout)
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Error de conexión' }))
        let msg: string
        if (typeof body.detail === 'string') {
          msg = body.detail
        } else if (Array.isArray(body.detail)) {
          msg = body.detail
            .map((e: Record<string, unknown>) => e.msg ?? '')
            .filter(Boolean)
            .join('; ')
        } else {
          msg = body.error || 'Credenciales incorrectas. Intenta de nuevo.'
        }
        setError(msg || 'Credenciales incorrectas. Intenta de nuevo.')
        return
      }

      const body = await res.json()
      const token = body.token || body.access_token || ''

      if (!token) {
        setError('Respuesta del servidor sin token. Contacta al administrador.')
        return
      }

      saveRuntimeConfig({ ...cfg, token })
      try {
        localStorage.setItem('titan.user', username.trim())
        const role = String(body.role ?? body.data?.role ?? 'cashier')
        localStorage.setItem('titan.role', role)
      } catch {
        /* storage full — non-critical, config already saved */
      }
      navigate('/terminal')
    } catch (err) {
      setError(
        err instanceof TypeError || (err instanceof DOMException && err.name === 'AbortError')
          ? 'No se puede conectar al servidor. Verifica que esté encendido.'
          : 'Error inesperado. Intenta de nuevo.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8 bg-zinc-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="z-10 w-full max-w-md flex flex-col bg-zinc-900/95 border border-zinc-800/80 rounded-3xl shadow-2xl overflow-hidden">
        {/* Login Form */}
        <div className="flex-1 p-8 sm:p-12 flex flex-col justify-center items-center relative">
          <div className="w-full max-w-sm">
            <div className="text-center mb-10 md:hidden">
              <h1 className="text-3xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent mb-2">
                POSVENDELO
              </h1>
              <p className="text-zinc-400 text-sm">Inicia sesión para continuar</p>
            </div>

            <h2 className="text-2xl font-bold text-zinc-100 mb-8 flex items-center justify-center gap-3">
              <User className="w-6 h-6 text-blue-500" />
              Acceso a caja
            </h2>

            {agentStatus && (
              <div className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4 text-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-zinc-300">
                    <Server className="h-4 w-4 text-blue-400" />
                    <span className="font-semibold">Nodo local</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => void refreshAgentStatus()}
                    disabled={refreshingAgent}
                    className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-[11px] font-bold text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${refreshingAgent ? 'animate-spin' : ''}`} />
                    Actualizar
                  </button>
                </div>

                <div className="grid grid-cols-1 gap-2 text-xs text-zinc-400">
                  <div className="flex items-center justify-between gap-3">
                    <span className="inline-flex items-center gap-2">
                      <Wifi
                        className={`h-3.5 w-3.5 ${agentStatus.backendHealthy ? 'text-emerald-400' : 'text-rose-400'}`}
                      />
                      Servidor local
                    </span>
                    <span
                      className={agentStatus.backendHealthy ? 'text-emerald-400' : 'text-rose-400'}
                    >
                      {agentStatus.backendHealthy ? 'Saludable' : 'No disponible'}
                    </span>
                  </div>
                  {!agentStatus.licenseValidSignature && (
                    <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-rose-300">
                      La firma local de la licencia no pudo validarse.
                    </p>
                  )}
                  {agentStatus.licenseMessage && (
                    <p className="rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-300">
                      Estado de licencia disponible. Inicia sesión para revisar el detalle
                      administrativo.
                    </p>
                  )}
                  {agentStatus.controlPlaneUrl && (
                    <p className="rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-300">
                      Acceso dueño:{' '}
                      <span className="font-semibold text-emerald-300">
                        {agentStatus.ownerSessionReady
                          ? 'sesión segura lista'
                          : agentStatus.ownerAccessMode === 'install-token'
                            ? 'preparando sesión delegada'
                            : 'sin companion remoto'}
                      </span>
                      .
                    </p>
                  )}
                  {agentStatus.branchId && (
                    <p className="rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-300">
                      Nodo listo para sucursal{' '}
                      <span className="font-semibold text-zinc-100">#{agentStatus.branchId}</span>.
                    </p>
                  )}
                  {(agentStatus.companionEntryUrl || agentStatus.quickLinks.ownerPortfolio) && (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-300">
                      <p className="font-semibold text-zinc-100">Acceso rápido companion</p>
                      <p className="mt-1 break-all text-[11px] text-zinc-400">
                        {agentStatus.companionEntryUrl ||
                          agentStatus.quickLinks.ownerPortfolio ||
                          agentStatus.companionUrl}
                      </p>
                    </div>
                  )}
                  {(agentStatus.appUpdateAvailable || agentStatus.backendUpdateAvailable) && (
                    <p className="rounded-xl border border-blue-500/20 bg-blue-500/10 px-3 py-2 text-blue-300">
                      Actualización disponible:
                      {agentStatus.appUpdateAvailable ? ' aplicación de escritorio' : ''}
                      {agentStatus.appUpdateAvailable && agentStatus.backendUpdateAvailable
                        ? ' y'
                        : ''}
                      {agentStatus.backendUpdateAvailable ? ' servidor local' : ''}.
                    </p>
                  )}
                  {(agentStatus.appUpdateAvailable || agentStatus.desktopUpdateReady) && (
                    <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 px-3 py-2 text-blue-200">
                      <p>
                        Actualización de la app: {agentStatus.desktopUpdateVersion ?? '-'} /{' '}
                        {getUpdateStatusLabel(agentStatus.desktopUpdateStatus)}
                      </p>
                      {agentStatus.desktopUpdateMessage && (
                        <p className="mt-1 text-xs text-blue-100/90">
                          {agentStatus.desktopUpdateMessage}
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap gap-2">
                        {agentStatus.desktopUpdateStatus !== 'staged' && (
                          <button
                            type="button"
                            onClick={() => void handlePrepareAppUpdate()}
                            disabled={updatingApp}
                            className="rounded-lg border border-blue-400/30 bg-blue-500/10 px-2.5 py-1 text-[11px] font-bold text-blue-100 disabled:opacity-50"
                          >
                            {updatingApp ? 'Preparando...' : 'Descargar actualización'}
                          </button>
                        )}
                        {agentStatus.desktopUpdateReady && (
                          <button
                            type="button"
                            onClick={() => void handleApplyAppUpdate()}
                            disabled={updatingApp}
                            className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-bold text-emerald-100 disabled:opacity-50"
                          >
                            {updatingApp ? 'Abriendo...' : 'Aplicar actualización'}
                          </button>
                        )}
                        {agentStatus.desktopUpdateReady && (
                          <button
                            type="button"
                            onClick={() => void handleDiscardAppUpdate()}
                            disabled={updatingApp}
                            className="rounded-lg border border-zinc-600 bg-zinc-900 px-2.5 py-1 text-[11px] font-bold text-zinc-200 disabled:opacity-50"
                          >
                            Descartar
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                  {agentStatus.backendUpdateAvailable && (
                    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-3 py-2 text-cyan-100">
                      <p>
                        Actualización del servidor local: {agentStatus.backendUpdateVersion ?? '-'}{' '}
                        / {getUpdateStatusLabel(agentStatus.backendUpdateStatus)}
                      </p>
                      {agentStatus.backendUpdateMessage && (
                        <p className="mt-1 text-xs text-cyan-50/90">
                          {agentStatus.backendUpdateMessage}
                        </p>
                      )}
                      <div className="mt-2">
                        <button
                          type="button"
                          onClick={() => void handleApplyBackendUpdate()}
                          disabled={updatingApp || agentStatus.backendUpdateStatus === 'applying'}
                          className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-[11px] font-bold text-cyan-50 disabled:opacity-50"
                        >
                          {updatingApp || agentStatus.backendUpdateStatus === 'applying'
                            ? 'Actualizando...'
                            : 'Actualizar servidor local'}
                        </button>
                      </div>
                    </div>
                  )}
                  {agentStatus.desktopRollbackAvailable && (
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-amber-100">
                      <p>
                        Reversión disponible a{' '}
                        {agentStatus.desktopRollbackVersion ?? 'versión previa'}.
                      </p>
                      {agentStatus.desktopRollbackMessage && (
                        <p className="mt-1 text-xs text-amber-50/90">
                          {agentStatus.desktopRollbackMessage}
                        </p>
                      )}
                      <div className="mt-2">
                        <button
                          type="button"
                          onClick={() => void handleRollbackAppUpdate()}
                          disabled={updatingApp}
                          className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-bold text-amber-50 disabled:opacity-50"
                        >
                          {updatingApp ? 'Revirtiendo...' : 'Volver a versión anterior'}
                        </button>
                      </div>
                    </div>
                  )}
                  {agentStatus.backendRollbackAvailable && (
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-amber-100">
                      <p>
                        Reversión del servidor disponible a{' '}
                        {agentStatus.backendRollbackVersion ?? 'versión previa'}.
                      </p>
                      {agentStatus.backendRollbackMessage && (
                        <p className="mt-1 text-xs text-amber-50/90">
                          {agentStatus.backendRollbackMessage}
                        </p>
                      )}
                      <div className="mt-2">
                        <button
                          type="button"
                          onClick={() => void handleRollbackBackendUpdate()}
                          disabled={updatingApp || agentStatus.backendUpdateStatus === 'applying'}
                          className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-bold text-amber-50 disabled:opacity-50"
                        >
                          {updatingApp || agentStatus.backendUpdateStatus === 'applying'
                            ? 'Revirtiendo...'
                            : 'Volver servidor a versión anterior'}
                        </button>
                      </div>
                    </div>
                  )}
                  {agentStatus.desktopUpdateError && (
                    <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-rose-300">
                      Error en la actualización de la app: {agentStatus.desktopUpdateError}
                    </p>
                  )}
                  {agentStatus.backendUpdateError && (
                    <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-rose-300">
                      Error en la actualización del servidor local: {agentStatus.backendUpdateError}
                    </p>
                  )}
                  {!agentStatus.configLoaded && (
                    <p className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-amber-300">
                      El agente local no tiene bootstrap cargado. Revisa `titan-agent.json` o el
                      instalador.
                    </p>
                  )}
                  {!agentStatus.backendHealthy && (
                    <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-rose-300">
                      El nodo local no pudo validar el backend. Revisa la instalación o el servicio.
                    </p>
                  )}
                </div>
              </div>
            )}

            <form onSubmit={handleLogin} className="w-full space-y-5 relative">
              {/* Username Input */}
              <div className="relative z-20">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  Usuario
                </label>
                <div className="relative group">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 z-10" />
                  <input
                    data-testid="login-username"
                    type="text"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value)
                      setError('')
                    }}
                    placeholder="Nombre de usuario"
                    autoComplete="username"
                    autoFocus
                    className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3.5 pl-12 pr-4 text-lg font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600 shadow-sm hover:border-zinc-600"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="relative z-10">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2 mt-4">
                  Contraseña
                </label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                  <input
                    data-testid="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value)
                      setError('')
                    }}
                    placeholder="••••••••"
                    className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/50 py-3.5 pl-12 pr-4 text-xl font-mono tracking-widest focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600"
                  />
                </div>
{error && (
                <p className="mt-2 text-sm text-rose-400 font-medium animate-pulse">{error}</p>
                )}
                <p className="mt-3 text-xs text-zinc-500">
                  Usuario por defecto: <strong className="text-zinc-400">admin</strong>. La
                  contraseña la tiene quien instaló el nodo (en la PC, archivo INSTALL_SUMMARY.txt).
                </p>
              </div>

              {(error?.includes('servidor') || !agentStatus?.backendHealthy) && (
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => navigate('/configurar-servidor')}
                    className="inline-flex items-center gap-2 rounded-xl border border-zinc-600 bg-zinc-800/80 py-2.5 px-4 text-sm font-medium text-zinc-300 hover:bg-zinc-700 hover:text-white"
                  >
                    <Settings className="w-4 h-4" />
                    Configurar dirección del servidor (IP o nombre de la PC)
                  </button>
                </div>
              )}

              <button
                data-testid="login-submit"
                type="submit"
                disabled={
                  loading || discovering || password.length === 0 || username.trim().length === 0
                }
                className="w-full flex justify-center items-center gap-2 rounded-xl bg-blue-500 hover:bg-blue-400 disabled:bg-zinc-800 disabled:text-zinc-500 px-4 py-4 font-bold text-white transition-colors mt-8 relative z-10"
              >
                {loading ? (
                  <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <>
                    <LogIn className="w-5 h-5" />
                    INGRESAR
                  </>
                )}
              </button>
            </form>

            <p className="mt-6 text-center">
              <button
                type="button"
                onClick={() => navigate('/configurar-servidor')}
                className="text-sm text-zinc-500 hover:text-blue-400 underline underline-offset-2"
              >
                Configurar servidor (IP de la PC del negocio)
              </button>
            </p>
            <p className="mt-4 text-center text-xs text-zinc-400 font-medium">
              {discovering ? (
                <span className="text-blue-400 animate-pulse">Buscando servidor...</span>
              ) : (
                <>{footerLabel}</>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
