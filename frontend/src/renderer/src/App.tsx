import type { ReactElement } from 'react'
import { Component, useEffect, type ErrorInfo, type ReactNode } from 'react'
import { HashRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import CustomersTab from './CustomersTab'
import DashboardStatsTab from './DashboardStatsTab'
import ExpensesTab from './ExpensesTab'
import HistoryTab from './HistoryTab'
import InventoryTab from './InventoryTab'
import Login from './Login'
import MermasTab from './MermasTab'
import ProductsTab from './ProductsTab'
import ReportsTab from './ReportsTab'
import SettingsTab from './SettingsTab'
import ShiftsTab from './ShiftsTab'
import Terminal from './Terminal'


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
            <h1 className="text-2xl font-bold text-rose-400 mb-4">
              Error en {this.props.tabName}
            </h1>
            <p className="text-zinc-400 mb-4">{this.state.error.message}</p>
            <p className="text-zinc-500 text-sm mb-6">
              Las demas pestanas siguen funcionando. Puedes navegar con las teclas F1-F11.
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

function RequireAuth({ children }: { children: ReactElement }): ReactElement {
  let token: string | null = null
  try { token = localStorage.getItem('titan.token') } catch { /* storage error */ }
  if (!token) return <Navigate to="/login" replace />
  return children
}

function RoutedApp(): ReactElement {
  const navigate = useNavigate()

  useEffect((): (() => void) => {
    const onKeyDown = (event: KeyboardEvent): void => {
      try { if (!localStorage.getItem('titan.token')) return } catch { return }
      const tag = (document.activeElement?.tagName ?? '').toUpperCase()
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      switch (event.key) {
        case 'F1':
          event.preventDefault()
          navigate('/terminal')
          break
        case 'F2':
          event.preventDefault()
          navigate('/clientes')
          break
        case 'F3':
          event.preventDefault()
          navigate('/productos')
          break
        case 'F4':
          event.preventDefault()
          navigate('/inventario')
          break
        case 'F5':
          event.preventDefault()
          navigate('/turnos')
          break
        case 'F6':
          event.preventDefault()
          navigate('/reportes')
          break
        case 'F7':
          event.preventDefault()
          navigate('/historial')
          break
        case 'F8':
          event.preventDefault()
          navigate('/configuraciones')
          break
        case 'F9':
          event.preventDefault()
          navigate('/estadisticas')
          break
        case 'F10':
          event.preventDefault()
          navigate('/mermas')
          break
        case 'F11':
          event.preventDefault()
          navigate('/gastos')
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [navigate])

  return (
    <Routes>
      <Route path="/" element={<RequireAuth><Navigate to="/terminal" replace /></RequireAuth>} />
      <Route path="/login" element={<Login />} />
      <Route path="/terminal" element={<RequireAuth><TabErrorBoundary tabName="Terminal"><Terminal /></TabErrorBoundary></RequireAuth>} />
      <Route path="/clientes" element={<RequireAuth><TabErrorBoundary tabName="Clientes"><CustomersTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/productos" element={<RequireAuth><TabErrorBoundary tabName="Productos"><ProductsTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/inventario" element={<RequireAuth><TabErrorBoundary tabName="Inventario"><InventoryTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/turnos" element={<RequireAuth><TabErrorBoundary tabName="Turnos"><ShiftsTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/reportes" element={<RequireAuth><TabErrorBoundary tabName="Reportes"><ReportsTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/historial" element={<RequireAuth><TabErrorBoundary tabName="Historial"><HistoryTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/configuraciones" element={<RequireAuth><TabErrorBoundary tabName="Configuraciones"><SettingsTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/estadisticas" element={<RequireAuth><TabErrorBoundary tabName="Estadisticas"><DashboardStatsTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/mermas" element={<RequireAuth><TabErrorBoundary tabName="Mermas"><MermasTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="/gastos" element={<RequireAuth><TabErrorBoundary tabName="Gastos"><ExpensesTab /></TabErrorBoundary></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App(): ReactElement {
  return (
    <ErrorBoundary>
      <HashRouter>
        <RoutedApp />
      </HashRouter>
    </ErrorBoundary>
  )
}

export default App
