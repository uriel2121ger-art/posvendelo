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

function RequireAuth({ children }: { children: ReactElement }): ReactElement {
  const token = localStorage.getItem('titan.token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

function RoutedApp(): ReactElement {
  const navigate = useNavigate()

  useEffect((): (() => void) => {
    const onKeyDown = (event: KeyboardEvent): void => {
      if (!localStorage.getItem('titan.token')) return
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
      <Route path="/terminal" element={<RequireAuth><Terminal /></RequireAuth>} />
      <Route path="/clientes" element={<RequireAuth><CustomersTab /></RequireAuth>} />
      <Route path="/productos" element={<RequireAuth><ProductsTab /></RequireAuth>} />
      <Route path="/inventario" element={<RequireAuth><InventoryTab /></RequireAuth>} />
      <Route path="/turnos" element={<RequireAuth><ShiftsTab /></RequireAuth>} />
      <Route path="/reportes" element={<RequireAuth><ReportsTab /></RequireAuth>} />
      <Route path="/historial" element={<RequireAuth><HistoryTab /></RequireAuth>} />
      <Route path="/configuraciones" element={<RequireAuth><SettingsTab /></RequireAuth>} />
      <Route path="/estadisticas" element={<RequireAuth><DashboardStatsTab /></RequireAuth>} />
      <Route path="/mermas" element={<RequireAuth><MermasTab /></RequireAuth>} />
      <Route path="/gastos" element={<RequireAuth><ExpensesTab /></RequireAuth>} />
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
