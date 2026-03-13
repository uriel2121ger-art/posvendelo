import type { ReactElement } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Building2,
  ChartColumn,
  CreditCard,
  FileSpreadsheet,
  LockKeyhole,
  LogOut,
  PackageSearch,
  Radio,
  RefreshCw,
  ShieldCheck
} from 'lucide-react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import {
  clearToken,
  createRemoteRequest,
  discoverCloud,
  getMe,
  getOwnerAudit,
  getOwnerCommercial,
  getOwnerEvents,
  getOwnerHealthSummary,
  getPortfolio,
  getStoredToken,
  listNotifications,
  listRemoteRequests,
  loginCloud,
  logoutCloud,
  registerBranch,
  registerCloud,
  saveToken,
  type CloudMe
} from './lib/api'

type Section = 'dashboard' | 'sucursales' | 'solicitudes' | 'ventas' | 'productos' | 'fiscal' | 'auditoria'

type OwnerState = {
  me: CloudMe | null
  portfolio: Record<string, unknown> | null
  health: Record<string, unknown> | null
  notifications: Array<Record<string, unknown>>
  remoteRequests: Array<Record<string, unknown>>
  events: Array<Record<string, unknown>>
  commercial: Record<string, unknown> | null
  audit: Array<Record<string, unknown>>
}

const initialState: OwnerState = {
  me: null,
  portfolio: null,
  health: null,
  notifications: [],
  remoteRequests: [],
  events: [],
  commercial: null,
  audit: []
}

function formatDate(value: unknown): string {
  if (typeof value !== 'string' || !value) return 'Sin dato'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('es-MX')
}

function formatMoney(value: unknown): string {
  const amount = Number(value ?? 0)
  return amount.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' })
}

function AuthScreen(): ReactElement {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Inicia sesión con tu cuenta cloud.')
  const [discoverInfo, setDiscoverInfo] = useState<string>('')
  const [form, setForm] = useState({
    email: '',
    password: '',
    fullName: '',
    businessName: '',
    branchName: 'Sucursal Principal',
    linkCode: ''
  })

  useEffect(() => {
    void discoverCloud()
      .then((data) => setDiscoverInfo(data.cp_url))
      .catch(() => setDiscoverInfo(''))
  }, [])

  async function handleSubmit(): Promise<void> {
    setBusy(true)
    try {
      const response =
        mode === 'login'
          ? await loginCloud(form.email, form.password)
          : await registerCloud({
              email: form.email,
              password: form.password,
              full_name: form.fullName || undefined,
              business_name: form.businessName || undefined,
              branch_name: form.branchName || undefined,
              link_code: form.linkCode || undefined
            })
      saveToken(response.session_token)
      navigate('/app', { replace: true })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo autenticar')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="eyebrow">Nube PosVendelo</div>
        <h1>{mode === 'login' ? 'Monitorea tus sucursales' : 'Activa tu cuenta cloud'}</h1>
        <p className="auth-copy">
          Acceso remoto multi-sucursal con confirmación local en el nodo. Mismo stack para PWA y desktop.
        </p>
        {discoverInfo && <p className="auth-discover">Control Plane: {discoverInfo}</p>}
        <div className="auth-switch">
          <button className={mode === 'login' ? 'is-active' : ''} onClick={() => setMode('login')}>
            Iniciar sesión
          </button>
          <button className={mode === 'register' ? 'is-active' : ''} onClick={() => setMode('register')}>
            Crear cuenta
          </button>
        </div>
        <div className="auth-fields">
          <input
            value={form.email}
            onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
            placeholder="Correo"
          />
          <input
            value={form.password}
            onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
            placeholder="Contraseña"
            type="password"
          />
          {mode === 'register' && (
            <>
              <input
                value={form.fullName}
                onChange={(event) => setForm((prev) => ({ ...prev, fullName: event.target.value }))}
                placeholder="Nombre completo"
              />
              <input
                value={form.businessName}
                onChange={(event) => setForm((prev) => ({ ...prev, businessName: event.target.value }))}
                placeholder="Empresa o razón comercial"
              />
              <input
                value={form.branchName}
                onChange={(event) => setForm((prev) => ({ ...prev, branchName: event.target.value }))}
                placeholder="Sucursal principal"
              />
              <input
                value={form.linkCode}
                onChange={(event) => setForm((prev) => ({ ...prev, linkCode: event.target.value }))}
                placeholder="Código de vinculación opcional"
              />
            </>
          )}
        </div>
        <button className="primary-button" disabled={busy} onClick={() => void handleSubmit()}>
          {busy ? 'Procesando...' : mode === 'login' ? 'Entrar' : 'Crear cuenta'}
        </button>
        <p className="auth-message">{message}</p>
      </section>
    </main>
  )
}

function OwnerShell(): ReactElement {
  const navigate = useNavigate()
  const [section, setSection] = useState<Section>('dashboard')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [state, setState] = useState<OwnerState>(initialState)
  const [priceForm, setPriceForm] = useState({ branchId: '', sku: '', newPrice: '' })
  const [newBranchName, setNewBranchName] = useState('')

  // ── Desktop update banner (ownerUpdates IPC) ──
  type OwnerUpdateStatus = 'available' | 'downloading' | 'staged' | 'applying' | 'error' | null
  const [updateStatus, setUpdateStatus] = useState<OwnerUpdateStatus>(null)
  const [updateVersion, setUpdateVersion] = useState<string | null>(null)
  const [updateMessage, setUpdateMessage] = useState<string | null>(null)

  const ownerUpdates = typeof window !== 'undefined'
    ? (window as Window & { ownerUpdates?: {
        getStatus: () => Promise<{ status: string; availableVersion?: string | null; lastError?: string | null }>
        checkForUpdate: () => Promise<unknown>
        downloadUpdate: () => Promise<unknown>
        applyUpdate: () => Promise<unknown>
        discardUpdate: () => Promise<unknown>
      } }).ownerUpdates
    : undefined

  useEffect(() => {
    if (!ownerUpdates) return
    let cancelled = false
    const poll = (): void => {
      ownerUpdates.getStatus().then((st) => {
        if (cancelled) return
        if (st.status === 'idle' || st.status === 'checking') {
          setUpdateStatus(null)
        } else {
          setUpdateStatus(st.status as OwnerUpdateStatus)
          setUpdateVersion(st.availableVersion ?? null)
          setUpdateMessage(st.lastError ?? null)
        }
      }).catch(() => {})
    }
    poll()
    const id = setInterval(poll, 60_000)
    return () => { cancelled = true; clearInterval(id) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleOwnerDownload = useCallback(() => {
    ownerUpdates?.downloadUpdate().catch(() => {})
  }, [ownerUpdates])
  const handleOwnerInstall = useCallback(() => {
    ownerUpdates?.applyUpdate().catch(() => {})
  }, [ownerUpdates])
  const handleOwnerDiscard = useCallback(() => {
    ownerUpdates?.discardUpdate().catch(() => {})
  }, [ownerUpdates])

  // ── Android APK update banner (Capacitor) ──
  const isCapacitor = typeof window !== 'undefined' &&
    'Capacitor' in window &&
    typeof (window.Capacitor as { isNativePlatform?: () => boolean })?.isNativePlatform === 'function' &&
    (window.Capacitor as { isNativePlatform: () => boolean }).isNativePlatform()

  const [apkStatus, setApkStatus] = useState<OwnerUpdateStatus>(null)
  const [apkVersion, setApkVersion] = useState<string | null>(null)
  const [apkDownloadUrl, setApkDownloadUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!isCapacitor) return
    let cancelled = false
    const check = async (): Promise<void> => {
      try {
        const { checkApkUpdate } = await import('./lib/apkUpdater')
        const cpUrl = localStorage.getItem('owner.controlPlaneUrl') ?? ''
        const token = localStorage.getItem('owner.installToken') ?? ''
        const currentVersion = localStorage.getItem('owner.appVersion') ?? '0.0.0'
        if (!cpUrl || !token) return
        const info = await checkApkUpdate(cpUrl, token, currentVersion)
        if (cancelled) return
        if (info.available) {
          setApkStatus('available')
          setApkVersion(info.version)
          setApkDownloadUrl(info.downloadUrl)
        } else {
          setApkStatus(null)
        }
      } catch { /* ignore */ }
    }
    void check()
    const id = setInterval(() => void check(), 5 * 60_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [isCapacitor])

  const handleApkInstall = useCallback(() => {
    if (!apkDownloadUrl) return
    setApkStatus('downloading')
    import('./lib/apkUpdater')
      .then(({ downloadAndInstallApk }) => downloadAndInstallApk(apkDownloadUrl))
      .catch(() => setApkStatus('error'))
  }, [apkDownloadUrl])

  const branches = useMemo(() => {
    const data = state.portfolio?.branches
    return Array.isArray(data) ? (data as Array<Record<string, unknown>>) : []
  }, [state.portfolio])
  const commercialLicense =
    state.commercial && typeof state.commercial.license === 'object' && state.commercial.license
      ? (state.commercial.license as Record<string, unknown>)
      : null
  const commercialHealth =
    state.commercial && typeof state.commercial.health === 'object' && state.commercial.health
      ? (state.commercial.health as Record<string, unknown>)
      : null

  async function loadAll(): Promise<void> {
    setBusy(true)
    try {
      const [me, portfolio, health, notifications, remoteRequests, events, commercial, audit] =
        await Promise.all([
          getMe(),
          getPortfolio(),
          getOwnerHealthSummary(),
          listNotifications(),
          listRemoteRequests(),
          getOwnerEvents(),
          getOwnerCommercial(),
          getOwnerAudit()
        ])
      setState({ me, portfolio, health, notifications, remoteRequests, events, commercial, audit })
      setMessage('')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'No se pudieron cargar los datos'
      setMessage(errorMessage)
      if (errorMessage.toLowerCase().includes('401')) {
        clearToken()
        navigate('/', { replace: true })
      }
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void loadAll()
  }, [])

  async function handleLogout(): Promise<void> {
    try {
      await logoutCloud()
    } catch {
      /* ignore logout API errors */
    } finally {
      clearToken()
      navigate('/', { replace: true })
    }
  }

  async function handleCreateRequest(): Promise<void> {
    setBusy(true)
    try {
      await createRemoteRequest({
        branch_id: Number(priceForm.branchId),
        request_type: 'update_product_price',
        payload: {
          sku: priceForm.sku.trim(),
          new_price: Number(priceForm.newPrice)
        },
        approval_mode: 'local_confirmation'
      })
      setPriceForm({ branchId: '', sku: '', newPrice: '' })
      setMessage('Solicitud remota enviada al nodo.')
      await loadAll()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo crear la solicitud remota')
    } finally {
      setBusy(false)
    }
  }

  async function handleRegisterBranch(): Promise<void> {
    if (!newBranchName.trim()) return
    setBusy(true)
    try {
      const response = await registerBranch(newBranchName.trim())
      setNewBranchName('')
      setMessage(`Sucursal creada. Install token: ${response.install_token}`)
      await loadAll()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo crear la sucursal')
    } finally {
      setBusy(false)
    }
  }

  const navItems: Array<{ id: Section; label: string; icon: typeof Radio }> = [
    { id: 'dashboard', label: 'Dashboard', icon: ChartColumn },
    { id: 'sucursales', label: 'Sucursales', icon: Building2 },
    { id: 'solicitudes', label: 'Solicitudes', icon: LockKeyhole },
    { id: 'ventas', label: 'Ventas', icon: CreditCard },
    { id: 'productos', label: 'Productos', icon: PackageSearch },
    { id: 'fiscal', label: 'Fiscal', icon: FileSpreadsheet },
    { id: 'auditoria', label: 'Auditoría', icon: ShieldCheck }
  ]

  return (
    <div className="owner-shell">
      <aside className="owner-sidebar">
        <div>
          <div className="eyebrow">App Dueño</div>
          <h2>{state.me?.tenant.name ?? 'Nube PosVendelo'}</h2>
          <p>{state.me?.cloud_user.email ?? 'sin sesión'}</p>
        </div>
        <nav className="owner-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={section === item.id ? 'is-active' : ''}
              onClick={() => setSection(item.id)}
            >
              <item.icon size={16} />
              {item.label}
            </button>
          ))}
        </nav>
        <button className="ghost-button" onClick={() => void handleLogout()}>
          <LogOut size={16} />
          Cerrar sesión
        </button>
      </aside>

      <main className="owner-main">
        <header className="topbar">
          <div>
            <h1>{navItems.find((item) => item.id === section)?.label ?? 'Dashboard'}</h1>
            <p>
              {state.me?.summary.branches_total ?? 0} sucursales • {state.me?.summary.online ?? 0} en
              línea
            </p>
          </div>
          <button className="ghost-button" disabled={busy} onClick={() => void loadAll()}>
            <RefreshCw size={16} className={busy ? 'spin' : ''} />
            Actualizar
          </button>
        </header>

        {message && <div className="banner">{message}</div>}

        {ownerUpdates && updateStatus && (
          <div
            className="banner"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px',
              ...(updateStatus === 'error'
                ? { borderColor: 'rgba(239,68,68,0.24)', background: 'rgba(239,68,68,0.12)', color: '#fca5a5' }
                : updateStatus === 'staged'
                  ? { borderColor: 'rgba(34,197,94,0.24)', background: 'rgba(34,197,94,0.12)', color: '#86efac' }
                  : { borderColor: 'rgba(59,130,246,0.24)', background: 'rgba(59,130,246,0.12)', color: '#93c5fd' })
            }}
          >
            {updateStatus === 'available' && (
              <>
                <span>Actualización v{updateVersion ?? '?'} disponible</span>
                <button className="primary-button" style={{ padding: '2px 12px', fontSize: '12px' }} onClick={handleOwnerDownload}>
                  Descargar
                </button>
              </>
            )}
            {updateStatus === 'downloading' && <span>Descargando actualización...</span>}
            {updateStatus === 'staged' && (
              <>
                <span>Actualización v{updateVersion ?? '?'} lista para instalar</span>
                <button className="primary-button" style={{ padding: '2px 12px', fontSize: '12px' }} onClick={handleOwnerInstall}>
                  Instalar ahora
                </button>
                <button className="ghost-button" style={{ padding: '2px 12px', fontSize: '12px' }} onClick={handleOwnerDiscard}>
                  Descartar
                </button>
              </>
            )}
            {updateStatus === 'applying' && <span>Instalando actualización...</span>}
            {updateStatus === 'error' && (
              <>
                <span>Error al actualizar{updateMessage ? `: ${updateMessage}` : ''}</span>
                <button className="ghost-button" style={{ padding: '2px 12px', fontSize: '12px' }} onClick={handleOwnerDownload}>
                  Reintentar
                </button>
              </>
            )}
          </div>
        )}

        {isCapacitor && apkStatus && (
          <div
            className="banner"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px',
              ...(apkStatus === 'error'
                ? { borderColor: 'rgba(239,68,68,0.24)', background: 'rgba(239,68,68,0.12)', color: '#fca5a5' }
                : { borderColor: 'rgba(59,130,246,0.24)', background: 'rgba(59,130,246,0.12)', color: '#93c5fd' })
            }}
          >
            {apkStatus === 'available' && (
              <>
                <span>Actualización v{apkVersion ?? '?'} disponible</span>
                <button className="primary-button" style={{ padding: '2px 12px', fontSize: '12px' }} onClick={handleApkInstall}>
                  Instalar
                </button>
              </>
            )}
            {apkStatus === 'downloading' && <span>Descargando actualización...</span>}
            {apkStatus === 'error' && (
              <>
                <span>Error al descargar actualización</span>
                <button className="ghost-button" style={{ padding: '2px 12px', fontSize: '12px' }} onClick={handleApkInstall}>
                  Reintentar
                </button>
              </>
            )}
          </div>
        )}

        {section === 'dashboard' && (
          <section className="content-grid">
            <article className="panel metrics-panel">
              <div>
                <span className="metric-label">Ventas del día</span>
                <strong>{formatMoney(state.portfolio?.sales_today_total)}</strong>
              </div>
              <div>
                <span className="metric-label">Offline</span>
                <strong>{Number(state.portfolio?.offline ?? 0)}</strong>
              </div>
              <div>
                <span className="metric-label">Alertas</span>
                <strong>{Number(state.portfolio?.alerts_total ?? 0)}</strong>
              </div>
            </article>
            <article className="panel">
              <h3>Sucursales</h3>
              <div className="stack-list">
                {branches.map((branch) => (
                  <div className="row-card" key={String(branch.id)}>
                    <div>
                      <strong>{String(branch.branch_name ?? branch.name ?? 'Sucursal')}</strong>
                      <p>{String(branch.branch_slug ?? '')}</p>
                    </div>
                    <span className={Number(branch.is_online) ? 'status-ok' : 'status-bad'}>
                      {Number(branch.is_online) ? 'En línea' : 'Fuera de línea'}
                    </span>
                  </div>
                ))}
              </div>
            </article>
            <article className="panel">
              <h3>Notificaciones</h3>
              <div className="stack-list">
                {state.notifications.slice(0, 5).map((notification) => (
                  <div className="row-card" key={String(notification.id)}>
                    <div>
                      <strong>{String(notification.title ?? 'Notificación')}</strong>
                      <p>{String(notification.body ?? '')}</p>
                    </div>
                    <span className="muted">{formatDate(notification.created_at)}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        )}

        {section === 'sucursales' && (
          <section className="content-grid">
            <article className="panel">
              <h3>Alta de sucursal</h3>
              <div className="inline-form">
                <input
                  value={newBranchName}
                  onChange={(event) => setNewBranchName(event.target.value)}
                  placeholder="Nombre de la nueva sucursal"
                />
                <button className="primary-button" disabled={busy} onClick={() => void handleRegisterBranch()}>
                  Crear
                </button>
              </div>
            </article>
            <article className="panel">
              <h3>Portfolio actual</h3>
              <div className="stack-list">
                {branches.map((branch) => (
                  <div className="row-card" key={String(branch.id)}>
                    <div>
                      <strong>{String(branch.branch_name ?? branch.name ?? 'Sucursal')}</strong>
                      <p>Ventas hoy: {formatMoney(branch.sales_today)}</p>
                    </div>
                    <span className="muted">Último heartbeat: {formatDate(branch.last_seen)}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        )}

        {section === 'solicitudes' && (
          <section className="content-grid">
            <article className="panel">
              <h3>Cambio remoto de precio</h3>
              <div className="stack-form">
                <select
                  value={priceForm.branchId}
                  onChange={(event) => setPriceForm((prev) => ({ ...prev, branchId: event.target.value }))}
                >
                  <option value="">Selecciona sucursal</option>
                  {branches.map((branch) => (
                    <option key={String(branch.id)} value={String(branch.id)}>
                      {String(branch.branch_name ?? branch.name)}
                    </option>
                  ))}
                </select>
                <input
                  value={priceForm.sku}
                  onChange={(event) => setPriceForm((prev) => ({ ...prev, sku: event.target.value }))}
                  placeholder="SKU del producto"
                />
                <input
                  value={priceForm.newPrice}
                  onChange={(event) => setPriceForm((prev) => ({ ...prev, newPrice: event.target.value }))}
                  placeholder="Nuevo precio"
                  type="number"
                />
                <button className="primary-button" disabled={busy} onClick={() => void handleCreateRequest()}>
                  Enviar solicitud
                </button>
              </div>
            </article>
            <article className="panel">
              <h3>Historial de solicitudes</h3>
              <div className="stack-list">
                {state.remoteRequests.map((request) => (
                  <div className="row-card" key={String(request.id)}>
                    <div>
                      <strong>{String(request.request_type ?? 'request')}</strong>
                      <p>{String(request.branch_name ?? request.branch_slug ?? 'Sucursal')}</p>
                    </div>
                    <span className="muted">{String(request.status ?? 'queued')}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        )}

        {section === 'ventas' && (
          <section className="content-grid">
            <article className="panel">
              <h3>Resumen operativo</h3>
              <p>
                Esta vista ya recibe ventas del día por sucursal. El detalle histórico se activará con el
                sync medio/pesado del nodo.
              </p>
              <div className="stack-list">
                {branches.map((branch) => (
                  <div className="row-card" key={String(branch.id)}>
                    <div>
                      <strong>{String(branch.branch_name ?? branch.name)}</strong>
                      <p>{formatMoney(branch.sales_today)}</p>
                    </div>
                    <span className="muted">{Number(branch.is_online) ? 'Lista' : 'Sin conexión'}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        )}

        {section === 'productos' && (
          <section className="content-grid">
            <article className="panel">
              <h3>Consulta bajo demanda</h3>
              <p>
                El catálogo completo no se precarga. Esta pantalla queda lista para buscar por SKU,
                código de barras o nombre cuando el sync pesado del control-plane esté habilitado.
              </p>
            </article>
          </section>
        )}

        {section === 'fiscal' && (
          <section className="content-grid">
            <article className="panel">
              <h3>Estado comercial y fiscal</h3>
              <p>Licencia actual: {String(commercialLicense?.license_type ?? 'sin dato')}</p>
              <p>Recordatorios: {JSON.stringify(commercialHealth?.reminder_types ?? [])}</p>
            </article>
          </section>
        )}

        {section === 'auditoria' && (
          <section className="content-grid">
            <article className="panel">
              <h3>Eventos recientes</h3>
              <div className="stack-list">
                {state.events.slice(0, 10).map((event, index) => (
                  <div className="row-card" key={String(event.event_type ?? index)}>
                    <div>
                      <strong>{String(event.event_type ?? 'evento')}</strong>
                      <p>{String(event.message ?? '')}</p>
                    </div>
                    <span className="muted">{formatDate(event.occurred_at)}</span>
                  </div>
                ))}
              </div>
            </article>
            <article className="panel">
              <h3>Auditoría</h3>
              <div className="stack-list">
                {state.audit.slice(0, 10).map((item) => (
                  <div className="row-card" key={String(item.id)}>
                    <div>
                      <strong>{String(item.action ?? 'audit')}</strong>
                      <p>{String(item.branch_name ?? item.entity_id ?? '')}</p>
                    </div>
                    <span className="muted">{formatDate(item.created_at)}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        )}
      </main>
    </div>
  )
}

function App(): ReactElement {
  const hasToken = Boolean(getStoredToken())

  return (
    <Routes>
      <Route path="/" element={hasToken ? <Navigate to="/app" replace /> : <AuthScreen />} />
      <Route path="/app" element={hasToken ? <OwnerShell /> : <Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
