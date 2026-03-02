import type { ReactElement } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useConfirm } from './ConfirmDialog'
import {
  ShoppingCart, // Ventas
  Box, // Productos
  ClipboardList, // Inventario
  Users, // Clientes
  Clock, // Turnos
  FileText, // Historial
  BarChart3, // Reportes
  Settings, // Configuraciones
  LogOut
} from 'lucide-react'

// Map of key routes we want visible in the minimal sidebar
const mainNavItems = [
  { path: '/terminal', label: 'Ventas', icon: ShoppingCart },
  { path: '/productos', label: 'Productos', icon: Box },
  { path: '/inventario', label: 'Inventario', icon: ClipboardList },
  { path: '/clientes', label: 'Clientes', icon: Users },
  { path: '/turnos', label: 'Turnos', icon: Clock },
  { path: '/historial', label: 'Historial', icon: FileText },
  { path: '/reportes', label: 'Reportes', icon: BarChart3 },
  { path: '/configuraciones', label: 'Ajustes', icon: Settings },
]

export default function Sidebar(): ReactElement {
  const location = useLocation()
  const confirm = useConfirm()

  const userName = (() => {
    try {
      return localStorage.getItem('titan.user') || 'User'
    } catch {
      return 'User'
    }
  })()

  const handleLogout = async () => {
    const hasPending = (() => {
      try {
        const raw = localStorage.getItem('titan.pendingTickets')
        if (!raw) return false
        const arr = JSON.parse(raw)
        return Array.isArray(arr) && arr.length > 0
      } catch {
        return false
      }
    })()

    const warnings: string[] = []
    if (hasPending) warnings.push('Hay tickets pendientes sin cobrar.')

    const msg = warnings.length
      ? `${warnings.join(' ')} ¿Cerrar sesión de todas formas?`
      : '¿Cerrar sesión de forma segura?'

    if (!await confirm(msg, { variant: 'warning', title: 'Cerrar Sesión' })) return

    try {
      ;['titan.token', 'titan.user', 'titan.role', 'titan.currentShift', 'titan.pendingTickets', 'titan.activeTickets'].forEach((k) =>
        localStorage.removeItem(k)
      )
    } catch {
      /* ignore */
    }
    window.location.hash = '#/login'
  }

  return (
    <aside className="w-20 lg:w-24 bg-zinc-950 border-r border-zinc-900 flex flex-col items-center py-4 select-none shrink-0 z-50">
      {/* Brand Logo / Initials */}
      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-black text-xl shadow-[0_0_15px_rgba(79,70,229,0.4)] mb-8 cursor-default">
        T
      </div>

      <nav className="flex-1 flex flex-col gap-2 w-full px-2 lg:px-3 overflow-y-auto hide-scrollbar">
        {mainNavItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <Link
              key={item.path}
              to={item.path}
              title={item.label}
              className={`flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl transition-all relative group ${
                isActive
                  ? 'bg-blue-600/10 text-blue-500'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'
              }`}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-blue-500 rounded-r-full shadow-[0_0_10px_rgba(59,130,246,0.8)]" />
              )}
              <item.icon className={`w-6 h-6 ${isActive ? 'drop-shadow-[0_0_8px_rgba(59,130,246,0.5)]' : ''}`} strokeWidth={isActive ? 2.5 : 2} />
              <span className="text-[10px] font-bold tracking-wide uppercase opacity-0 lg:opacity-100 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                {item.label}
              </span>
            </Link>
          )
        })}
      </nav>

      {/* Footer / User Profile */}
      <div className="mt-auto w-full px-2 lg:px-3 pt-4 border-t border-zinc-900 flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300 font-bold text-sm uppercase cursor-default" title={`Usuario Activo: ${userName}`}>
          {userName.slice(0, 2)}
        </div>
        <button
          onClick={handleLogout}
          title="Cerrar Sesión"
          className="w-10 h-10 rounded-xl flex items-center justify-center text-rose-500/80 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
        >
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </aside>
  )
}
