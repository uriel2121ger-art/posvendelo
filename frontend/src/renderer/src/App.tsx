import type { ReactElement } from 'react'
import { Component, useEffect, type ErrorInfo, type ReactNode } from 'react'
import { HashRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
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

import {
  ShoppingCart,
  Users,
  Box,
  ClipboardList,
  Settings,
  FileText,
  History,
  Clock,
  TrendingUp,
  AlertTriangle,
  Receipt
} from 'lucide-react'

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

function Dashboard(): ReactElement {
  const modules = [
    {
      title: 'Ventas (F1)',
      subtitle: 'Punto de Venta',
      icon: ShoppingCart,
      color: 'text-emerald-400',
      bg: 'bg-emerald-400/10',
      path: '/terminal'
    },
    {
      title: 'Clientes (F2)',
      subtitle: 'Directorio',
      icon: Users,
      color: 'text-blue-400',
      bg: 'bg-blue-400/10',
      path: '/clientes'
    },
    {
      title: 'Productos (F3)',
      subtitle: 'Catálogo',
      icon: Box,
      color: 'text-purple-400',
      bg: 'bg-purple-400/10',
      path: '/productos'
    },
    {
      title: 'Inventario (F4)',
      subtitle: 'Stock',
      icon: ClipboardList,
      color: 'text-amber-400',
      bg: 'bg-amber-400/10',
      path: '/inventario'
    },
    {
      title: 'Turnos (F5)',
      subtitle: 'Caja',
      icon: Clock,
      color: 'text-rose-400',
      bg: 'bg-rose-400/10',
      path: '/turnos'
    },
    {
      title: 'Reportes (F6)',
      subtitle: 'Estadísticas',
      icon: FileText,
      color: 'text-indigo-400',
      bg: 'bg-indigo-400/10',
      path: '/reportes'
    },
    {
      title: 'Historial (F7)',
      subtitle: 'Tickets',
      icon: History,
      color: 'text-cyan-400',
      bg: 'bg-cyan-400/10',
      path: '/historial'
    },
    {
      title: 'Ajustes (F8)',
      subtitle: 'Sistema',
      icon: Settings,
      color: 'text-zinc-400',
      bg: 'bg-zinc-400/10',
      path: '/configuraciones'
    },
    {
      title: 'Estadísticas (F9)',
      subtitle: 'Dashboard',
      icon: TrendingUp,
      color: 'text-teal-400',
      bg: 'bg-teal-400/10',
      path: '/estadisticas'
    },
    {
      title: 'Mermas (F10)',
      subtitle: 'Control',
      icon: AlertTriangle,
      color: 'text-orange-400',
      bg: 'bg-orange-400/10',
      path: '/mermas'
    },
    {
      title: 'Gastos (F11)',
      subtitle: 'Egresos',
      icon: Receipt,
      color: 'text-pink-400',
      bg: 'bg-pink-400/10',
      path: '/gastos'
    }
  ]

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8 bg-zinc-950 text-slate-200 font-sans selection:bg-blue-500/30 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-[500px] bg-blue-900/10 blur-[120px] rounded-full pointer-events-none"></div>

      <div className="z-10 w-full max-w-5xl">
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-zinc-900/50 border border-zinc-800/50 shadow-2xl mb-6">
            <h1 className="text-5xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent drop-shadow-sm">
              TITAN POS
            </h1>
          </div>
          <p className="text-zinc-400 text-lg font-medium tracking-wide">
            Selecciona un módulo operativo para comenzar
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {modules.map((mod) => (
            <Link
              key={mod.title}
              to={mod.path}
              className="group flex flex-col items-center justify-center p-8 rounded-2xl bg-zinc-900/40 border border-zinc-800 backdrop-blur-sm hover:bg-zinc-800/60 hover:border-zinc-700 transition-all duration-300 hover:shadow-[0_0_30px_rgba(0,0,0,0.5)] hover:-translate-y-1 relative overflow-hidden text-center"
            >
              {/* Subtle hover gradient background */}
              <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>

              <div
                className={`p-4 rounded-xl ${mod.bg} mb-4 group-hover:scale-110 transition-transform duration-300`}
              >
                <mod.icon className={`w-8 h-8 ${mod.color}`} />
              </div>

              <h3 className="text-xl font-bold text-zinc-100 mb-1 group-hover:text-white transition-colors">
                {mod.title}
              </h3>
              <span className="text-sm font-medium text-zinc-500 group-hover:text-zinc-400 transition-colors">
                {mod.subtitle}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

function RoutedApp(): ReactElement {
  const navigate = useNavigate()

  useEffect((): (() => void) => {
    const onKeyDown = (event: KeyboardEvent): void => {
      if (!localStorage.getItem('titan.token')) return
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
      <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
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
