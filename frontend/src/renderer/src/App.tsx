import type { ReactElement, FormEvent } from 'react'
import {
  Component,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ErrorInfo,
  type ReactNode
} from 'react'
import { HashRouter, Navigate, Route, Routes, useNavigate, Outlet } from 'react-router-dom'
import { loadRuntimeConfig, createCashMovement, openDrawerForSale, pullTable } from './posApi'
import CustomersTab from './tabs/CustomersTab'
import DashboardStatsTab from './tabs/DashboardStatsTab'
import ExpensesTab from './tabs/ExpensesTab'
import HistoryTab from './tabs/HistoryTab'
import InventoryTab from './tabs/InventoryTab'
import Login from './Login'
import MermasTab from './tabs/MermasTab'
import ProductsTab from './tabs/ProductsTab'
import ReportsTab from './tabs/ReportsTab'
import SettingsTab from './tabs/SettingsTab'
import ShiftsTab from './tabs/ShiftsTab'
import EmployeesTab from './tabs/EmployeesTab'
import FiscalTab from './tabs/FiscalTab'
import RemoteTab from './tabs/RemoteTab'
import Terminal from './tabs/Terminal'
import ShiftStartupModal from './tabs/ShiftStartupModal'
import { ConfirmProvider } from './components/ConfirmDialog'
import Layout from './components/Layout'
import CompanionLayout from './components/CompanionLayout'
import { useFocusTrap } from './hooks/useFocusTrap'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, info)
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-slate-200 p-8">
          <div className="max-w-md text-center">
            <h1 className="text-2xl font-bold text-rose-400 mb-4">Error inesperado</h1>
            <p className="text-zinc-400 mb-6">{this.state.error.message}</p>
            <button
              onClick={() => {
                this.setState({ error: null })
                window.location.hash = '#/'
              }}
              className="px-6 py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-500 transition-all"
            >
              Volver al inicio
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

class TabErrorBoundary extends Component<
  { children: ReactNode; tabName: string },
  { error: Error | null }
> {
  constructor(props: { children: ReactNode; tabName: string }) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`TabErrorBoundary [${this.props.tabName}] caught:`, error, info)
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-slate-200 p-8">
          <div className="max-w-md text-center">
            <h1 className="text-2xl font-bold text-rose-400 mb-4">Error en {this.props.tabName}</h1>
            <p className="text-zinc-400 mb-4">{this.state.error.message}</p>
            <p className="text-zinc-500 text-sm mb-6">
              Las demás pestañas siguen funcionando. Puedes navegar con las teclas F1-F11.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => this.setState({ error: null })}
                className="px-6 py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-500 transition-all"
              >
                Reintentar
              </button>
              <button
                onClick={() => {
                  this.setState({ error: null })
                  window.location.hash = '#/terminal'
                }}
                className="px-6 py-3 rounded-xl bg-zinc-700 text-white font-bold hover:bg-zinc-600 transition-all"
              >
                Ir a Terminal
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function _isTokenStructureValid(token: string): boolean {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false
    const payload = JSON.parse(atob(parts[1]))
    if (!payload.sub || !payload.role) return false
    // Check expiry
    if (payload.exp && payload.exp * 1000 < Date.now()) return false
    return true
  } catch {
    return false
  }
}

function RequireAuth({ children }: { children: ReactElement }): ReactElement {
  let token: string | null = null
  try {
    token = localStorage.getItem('titan.token')
  } catch {
    /* storage error */
  }
  if (!token || !_isTokenStructureValid(token)) {
    // Clear invalid/expired token
    try {
      localStorage.removeItem('titan.token')
      localStorage.removeItem('titan.role')
    } catch {
      /* ignore */
    }
    return <Navigate to="/login" replace />
  }
  return children
}

/* ── Helpers for global modals ────────────────────────────── */

type CashMovModalState = 'hidden' | 'in' | 'out'

import { readCurrentShift as readShiftSnap } from './types/shiftTypes'
import { toNumber } from './utils/numbers'

type PriceCheckProduct = {
  sku: string
  name: string
  price: number
  priceWholesale?: number
  stock?: number
}

function normalizePriceCheckProduct(raw: Record<string, unknown>): PriceCheckProduct | null {
  const sku = String(raw.sku ?? raw.code ?? raw.codigo ?? '').trim()
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!sku || !name) return null
  const priceFields = [raw.price, raw.sale_price, raw.precio, raw.cost]
  const price = toNumber(priceFields.find((v) => v != null && toNumber(v) > 0) ?? 0)
  const pw = toNumber(raw.price_wholesale ?? raw.priceWholesale ?? 0)
  return { sku, name, price, priceWholesale: pw > 0 ? pw : undefined, stock: toNumber(raw.stock) }
}

/* ── Cash Movement Modal (F7 / F8) ──────────────────────── */

function CashMovementModal({
  mode,
  onClose
}: {
  mode: 'in' | 'out'
  onClose: () => void
}): ReactElement {
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const amountRef = useRef<HTMLInputElement>(null)
  const modalRef = useRef<HTMLFormElement>(null)

  useFocusTrap(modalRef, !success)

  useEffect(() => {
    amountRef.current?.focus()
  }, [])

  useEffect(() => {
    const onEsc = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onEsc, true)
    return () => window.removeEventListener('keydown', onEsc, true)
  }, [onClose])

  const handleSubmit = useCallback(
    async (e: FormEvent): Promise<void> => {
      e.preventDefault()
      const num = parseFloat(amount)
      if (!Number.isFinite(num) || num <= 0) {
        setError('Ingresa un monto válido.')
        return
      }
      const shift = readShiftSnap()
      if (!shift?.backendTurnId) {
        setError('No hay turno abierto. Abre uno en la pestaña Turnos.')
        return
      }
      setBusy(true)
      setError('')
      try {
        const cfg = loadRuntimeConfig()
        await createCashMovement(cfg, shift.backendTurnId, {
          movement_type: mode === 'in' ? 'cash_in' : 'cash_out',
          amount: num,
          reason: reason.trim() || (mode === 'in' ? 'Entrada de efectivo' : 'Retiro de efectivo')
        })
        // Auto-open cash drawer (fire-and-forget)
        try {
          const hwRaw = localStorage.getItem('titan.hwConfig')
          if (hwRaw) {
            const hwCfg = JSON.parse(hwRaw) as { drawer?: { enabled?: boolean } }
            if (hwCfg.drawer?.enabled) {
              openDrawerForSale(cfg).catch(() => {})
            }
          }
        } catch {
          /* hw config parse error — non-fatal */
        }
        // Show success briefly before closing
        setSuccess(true)
        setTimeout(() => onClose(), 1500)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setBusy(false)
      }
    },
    [amount, reason, mode, onClose]
  )

  const title = mode === 'in' ? 'Entrada de efectivo' : 'Retiro de efectivo'
  const fKey = mode === 'in' ? 'F7' : 'F8'
  const accent = mode === 'in' ? 'emerald' : 'rose'

  if (success) {
    const successMsg =
      mode === 'in'
        ? `Entrada de $${parseFloat(amount).toFixed(2)} registrada`
        : `Retiro de $${parseFloat(amount).toFixed(2)} registrado`
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="w-full max-w-sm rounded-2xl border border-emerald-700 bg-zinc-900 p-8 shadow-2xl text-center">
          <div className="text-5xl mb-4">&#9989;</div>
          <h2 className="text-lg font-bold text-emerald-400 mb-2">Operación exitosa</h2>
          <p className="text-zinc-300 font-semibold mb-1">{successMsg}</p>
          <p className="text-zinc-500 text-sm">Cajón de dinero abierto</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <form
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => void handleSubmit(e)}
        className="w-full max-w-sm rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl"
      >
        <h2 className={`text-lg font-bold text-${accent}-400 mb-4 flex items-center gap-2`}>
          {title}
          <kbd className="ml-auto rounded bg-zinc-800 border border-zinc-700 px-2 py-0.5 font-mono text-xs text-zinc-400">
            {fKey}
          </kbd>
        </h2>
        <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">
          Monto
        </label>
        <input
          ref={amountRef}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2.5 px-3 text-sm font-semibold mb-3 focus:border-blue-500 focus:outline-none"
          type="number"
          min={0.01}
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="$0.00"
        />
        <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">
          Motivo
        </label>
        <input
          className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2.5 px-3 text-sm font-semibold mb-4 focus:border-blue-500 focus:outline-none"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={mode === 'in' ? 'Fondo de caja' : 'Pago a proveedor'}
        />
        {error && <p className="text-rose-400 text-sm mb-3">{error}</p>}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-rose-600 bg-rose-600 py-2.5 font-bold text-white hover:bg-rose-500 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={busy}
            className="flex-1 rounded-xl bg-emerald-600 py-2.5 font-bold text-white hover:bg-emerald-500 transition-colors disabled:opacity-40"
          >
            {busy ? 'Registrando...' : 'Registrar'}
          </button>
        </div>
      </form>
    </div>
  )
}

/* ── Price Checker Modal (F9) ────────────────────────────── */

function PriceCheckerModal({ onClose }: { onClose: () => void }): ReactElement {
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState<PriceCheckProduct[]>([])
  const [loaded, setLoaded] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)

  useFocusTrap(modalRef, true)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const onEsc = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onEsc, true)
    return () => window.removeEventListener('keydown', onEsc, true)
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    const cfg = loadRuntimeConfig()
    if (!cfg.token) return
    pullTable('products', cfg)
      .then((raw) => {
        if (cancelled) return
        setProducts(
          raw.map(normalizePriceCheckProduct).filter((p): p is PriceCheckProduct => p !== null)
        )
        setLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const results = useMemo((): PriceCheckProduct[] => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return products
      .filter((p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q))
      .slice(0, 10)
  }, [products, query])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl"
      >
        <h2 className="text-lg font-bold text-blue-400 mb-4 flex items-center gap-2">
          Verificador de precios
          <kbd className="ml-auto rounded bg-zinc-800 border border-zinc-700 px-2 py-0.5 font-mono text-xs text-zinc-400">
            F9
          </kbd>
        </h2>
        <input
          ref={inputRef}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2.5 px-3 text-sm font-semibold mb-4 focus:border-blue-500 focus:outline-none"
          value={query}
          // eslint-disable-next-line no-control-regex
          onChange={(e) => setQuery(e.target.value.replace(/[\x00-\x1F\x7F-\x9F]/g, ''))}
          placeholder={loaded ? 'SKU o nombre del producto...' : 'Cargando productos...'}
        />
        {results.length > 0 && (
          <div className="max-h-72 overflow-y-auto space-y-2">
            {results.map((p) => (
              <div key={p.sku} className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
                <div className="font-semibold text-zinc-100 truncate">{p.name}</div>
                <div className="text-xs text-zinc-500 font-mono mt-0.5">SKU: {p.sku}</div>
                <div className="flex items-center gap-4 mt-2">
                  <span className="text-emerald-400 font-bold">${p.price.toFixed(2)}</span>
                  {p.priceWholesale && (
                    <span className="text-amber-400 text-sm">
                      Mayoreo: ${p.priceWholesale.toFixed(2)}
                    </span>
                  )}
                  <span className="text-zinc-500 text-sm ml-auto">{p.stock ?? 0} uds</span>
                </div>
              </div>
            ))}
          </div>
        )}
        {query.trim() && results.length === 0 && loaded && (
          <p className="text-zinc-500 text-sm text-center py-4">Sin resultados</p>
        )}
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-xl border border-zinc-700 bg-zinc-800 py-2.5 font-bold text-zinc-300 hover:bg-zinc-700 transition-colors"
        >
          Cerrar
        </button>
      </div>
    </div>
  )
}

/* ── RoutedApp ───────────────────────────────────────────── */

const IDLE_TIMEOUT_MS = 30 * 60 * 1000 // 30 minutes

function RoutedApp(): ReactElement {
  const navigate = useNavigate()
  const [cashMovModal, setCashMovModal] = useState<CashMovModalState>('hidden')
  const [priceCheckModal, setPriceCheckModal] = useState(false)
  const [shiftResolved, setShiftResolved] = useState(false)

  // Idle timeout — auto-logout after 30 min of inactivity
  useEffect((): (() => void) => {
    let timer: ReturnType<typeof setTimeout>
    const resetTimer = (): void => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        try {
          const hasToken = localStorage.getItem('titan.token')
          if (!hasToken) return
          localStorage.removeItem('titan.token')
          localStorage.removeItem('titan.role')
          localStorage.removeItem('titan.shiftHistory')
          setShiftResolved(false)
          navigate('/login')
        } catch {
          /* ignore */
        }
      }, IDLE_TIMEOUT_MS)
    }
    const events: string[] = ['mousedown', 'keydown', 'touchstart', 'scroll']
    events.forEach((e) => window.addEventListener(e, resetTimer, { passive: true }))
    resetTimer()
    return () => {
      clearTimeout(timer)
      events.forEach((e) => window.removeEventListener(e, resetTimer))
    }
  }, [navigate])

  // Reset shiftResolved when user logs out (token removed)
  useEffect((): (() => void) => {
    const onStorage = (e: StorageEvent): void => {
      if (e.key === 'titan.token' && !e.newValue) setShiftResolved(false)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Abrir modal consulta precios (F9) desde Terminal u otros componentes
  useEffect((): (() => void) => {
    const onOpen = (): void => setPriceCheckModal(true)
    window.addEventListener('titan-open-price-check', onOpen)
    return () => window.removeEventListener('titan-open-price-check', onOpen)
  }, [])

  useEffect((): (() => void) => {
    const onKeyDown = (event: KeyboardEvent): void => {
      try {
        if (!localStorage.getItem('titan.token')) return
      } catch {
        return
      }
      if (!shiftResolved) return
      // F-keys don't produce text — always handle them even when input is focused
      switch (event.key) {
        case 'F1':
          event.preventDefault()
          event.stopPropagation()
          navigate('/terminal')
          break
        case 'F2':
          event.preventDefault()
          event.stopPropagation()
          navigate('/clientes')
          break
        case 'F3':
          event.preventDefault()
          event.stopPropagation()
          navigate('/productos')
          break
        case 'F4':
          event.preventDefault()
          event.stopPropagation()
          navigate('/inventario')
          break
        case 'F5':
          event.preventDefault()
          event.stopPropagation()
          navigate('/turnos')
          break
        case 'F6':
          event.preventDefault()
          event.stopPropagation()
          navigate('/reportes')
          break
        case 'F7':
          event.preventDefault()
          event.stopPropagation()
          if (window.location.hash === '#/terminal') {
            setCashMovModal('in')
          }
          break
        case 'F8':
          event.preventDefault()
          event.stopPropagation()
          if (window.location.hash === '#/terminal') {
            setCashMovModal('out')
          }
          break
        case 'F9':
          event.preventDefault()
          event.stopPropagation()
          if (window.location.hash === '#/terminal') {
            setPriceCheckModal(true)
          }
          break
        // F10, F11, F12 — handled by Terminal.tsx (capture phase)
        default:
          break
      }
    }
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [navigate, shiftResolved])

  const hasToken = (() => {
    try {
      return Boolean(localStorage.getItem('titan.token'))
    } catch {
      return false
    }
  })()
  const isCompanionRoute = window.location.hash.startsWith('#/companion')

  return (
    <>
      {hasToken && !shiftResolved && !isCompanionRoute && (
        <ShiftStartupModal
          onComplete={() => setShiftResolved(true)}
          onExit={() => {
            const api = (window as Window & { api?: { closeApp?: () => Promise<void> } }).api
            if (typeof api?.closeApp === 'function') {
              void api.closeApp()
            } else {
              try {
                window.close()
              } catch {
                /* en navegador window.close() suele no hacer nada */
              }
            }
          }}
        />
      )}
      {cashMovModal !== 'hidden' && (
        <CashMovementModal mode={cashMovModal} onClose={() => setCashMovModal('hidden')} />
      )}
      {priceCheckModal && <PriceCheckerModal onClose={() => setPriceCheckModal(false)} />}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout>
                <Outlet />
              </Layout>
            </RequireAuth>
          }
        >
          <Route
            path="/companion"
            element={
              <CompanionLayout>
                <Outlet />
              </CompanionLayout>
            }
          >
            <Route path="" element={<Navigate to="/companion/remoto" replace />} />
            <Route
              path="remoto"
              element={
                <TabErrorBoundary tabName="Companion Remoto">
                  <RemoteTab />
                </TabErrorBoundary>
              }
            />
            <Route
              path="estadisticas"
              element={
                <TabErrorBoundary tabName="Companion Estadísticas">
                  <DashboardStatsTab />
                </TabErrorBoundary>
              }
            />
          </Route>
          <Route path="/" element={<Navigate to="/terminal" replace />} />
          <Route
            path="/terminal"
            element={
              <TabErrorBoundary tabName="Terminal">
                <Terminal />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/clientes"
            element={
              <TabErrorBoundary tabName="Clientes">
                <CustomersTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/productos"
            element={
              <TabErrorBoundary tabName="Productos">
                <ProductsTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/inventario"
            element={
              <TabErrorBoundary tabName="Inventario">
                <InventoryTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/turnos"
            element={
              <TabErrorBoundary tabName="Turnos">
                <ShiftsTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/reportes"
            element={
              <TabErrorBoundary tabName="Reportes">
                <ReportsTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/historial"
            element={
              <TabErrorBoundary tabName="Historial">
                <HistoryTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/configuraciones"
            element={
              <TabErrorBoundary tabName="Configuraciones">
                <SettingsTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/estadisticas"
            element={
              <TabErrorBoundary tabName="Estadísticas">
                <DashboardStatsTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/mermas"
            element={
              <TabErrorBoundary tabName="Mermas">
                <MermasTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/gastos"
            element={
              <TabErrorBoundary tabName="Gastos">
                <ExpensesTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/empleados"
            element={
              <TabErrorBoundary tabName="Empleados">
                <EmployeesTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/remoto"
            element={
              <TabErrorBoundary tabName="Remoto">
                <RemoteTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/fiscal"
            element={
              <TabErrorBoundary tabName="Fiscal">
                <FiscalTab />
              </TabErrorBoundary>
            }
          />
          <Route
            path="/hardware"
            element={
              <TabErrorBoundary tabName="Hardware">
                <SettingsTab mode="hardware" initialTab="printer" />
              </TabErrorBoundary>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

function App(): ReactElement {
  return (
    <ErrorBoundary>
      <ConfirmProvider>
        <HashRouter>
          <RoutedApp />
        </HashRouter>
      </ConfirmProvider>
    </ErrorBoundary>
  )
}

export default App
