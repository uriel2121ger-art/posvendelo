import type { ReactElement } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ShoppingCart,
  Users,
  Box,
  ClipboardList,
  Settings,
  FileText,
  LogOut,
  Clock,
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Receipt
} from 'lucide-react'

export default function TopNavbar(): ReactElement {
  const location = useLocation()
  const navigate = useNavigate()

  const navItems = [
    { path: '/terminal', label: 'Ventas', icon: ShoppingCart },
    { path: '/clientes', label: 'Clientes', icon: Users },
    { path: '/productos', label: 'Productos', icon: Box },
    { path: '/inventario', label: 'Inventario', icon: ClipboardList },
    { path: '/turnos', label: 'Turnos', icon: Clock },
    { path: '/reportes', label: 'Reportes', icon: BarChart3 },
    { path: '/historial', label: 'Historial', icon: FileText },
    { path: '/configuraciones', label: 'Ajustes', icon: Settings },
    { path: '/estadisticas', label: 'Stats', icon: TrendingUp },
    { path: '/mermas', label: 'Mermas', icon: AlertTriangle },
    { path: '/gastos', label: 'Gastos', icon: Receipt }
  ]

  return (
    <div className="flex items-center gap-1 bg-zinc-900 border-b border-zinc-800 p-2 overflow-x-auto shrink-0 select-none">
      {navItems.map((item) => {
        const isActive = location.pathname === item.path
        return (
          <Link
            key={item.path}
            to={item.path}
            className={`flex items-center gap-2 px-4 py-2 rounded font-medium transition-colors ${
              isActive
                ? 'bg-zinc-800 shadow-sm border border-zinc-700 font-bold text-blue-400'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
            }`}
          >
            <item.icon className="w-5 h-5" /> {item.label}
          </Link>
        )
      })}

      <div className="ml-auto flex items-center gap-4 bg-zinc-950 px-4 py-1.5 rounded-full border border-zinc-800">
        <div className="text-xs text-zinc-500 text-right">
          <div>Le atiende:</div>
          <div className="font-bold text-zinc-300">{(() => { try { return localStorage.getItem('titan.user') || 'Usuario' } catch { return 'Usuario' } })()}</div>
        </div>
        <button
          onClick={() => {
            const hasPending = (() => {
              try {
                const raw = localStorage.getItem('titan.pendingTickets')
                if (!raw) return false
                const arr = JSON.parse(raw)
                return Array.isArray(arr) && arr.length > 0
              } catch { return false }
            })()
            const hasShift = (() => { try { return Boolean(localStorage.getItem('titan.currentShift')) } catch { return false } })()
            const warnings: string[] = []
            if (hasPending) warnings.push('Hay tickets pendientes sin cobrar.')
            if (hasShift) warnings.push('Hay un turno abierto.')
            const msg = warnings.length
              ? `${warnings.join(' ')} ¿Cerrar sesion de todas formas?`
              : '¿Cerrar sesion?'
            if (!window.confirm(msg)) return
            try {
              ;['titan.token', 'titan.user', 'titan.currentShift'].forEach(
                (k) => localStorage.removeItem(k)
              )
            } catch { /* storage inaccessible — proceed with redirect */ }
            window.location.hash = '#/login'
            window.location.reload()
          }}
          className="text-rose-500/80 hover:text-rose-400 transition-colors"
          title="Cerrar Sesion"
        >
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}
