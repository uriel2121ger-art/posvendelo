import type { ReactElement } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useConfirm } from './ConfirmDialog'
import {
  ShoppingCart,
  Box,
  Users,
  ClipboardList,
  Clock,
  FileText,
  PackageX,
  BarChart3,
  LayoutDashboard,
  UserCog,
  Radio,
  Landmark,
  Settings,
  LogOut
} from 'lucide-react'

type NavItem = { path: string; label: string; icon: typeof ShoppingCart }

const navGroups: NavItem[][] = [
  // Ventas
  [{ path: '/terminal', label: 'Ventas', icon: ShoppingCart }],
  // Catálogo
  [
    { path: '/productos', label: 'Productos', icon: Box },
    { path: '/clientes', label: 'Clientes', icon: Users },
    { path: '/inventario', label: 'Inventario', icon: ClipboardList }
  ],
  // Operación
  [
    { path: '/turnos', label: 'Turnos', icon: Clock },
    { path: '/historial', label: 'Historial', icon: FileText },
    { path: '/mermas', label: 'Mermas', icon: PackageX }
  ],
  // Reportes
  [
    { path: '/reportes', label: 'Reportes', icon: BarChart3 },
    { path: '/estadisticas', label: 'Estadísticas', icon: LayoutDashboard }
  ],
  // Admin
  [
    { path: '/empleados', label: 'Empleados', icon: UserCog },
    { path: '/remoto', label: 'Remoto', icon: Radio },
    { path: '/fiscal', label: 'Fiscal', icon: Landmark },
    { path: '/configuraciones', label: 'Ajustes', icon: Settings }
  ]
]

export default function TopNavbar(): ReactElement {
  const location = useLocation()
  const confirm = useConfirm()

  const userName = (() => {
    try {
      return localStorage.getItem('titan.user') || 'User'
    } catch {
      return 'User'
    }
  })()

  const handleLogout = async (): Promise<void> => {
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

    if (!(await confirm(msg, { variant: 'warning', title: 'Cerrar Sesión' }))) return

    try {
      ;[
        'titan.token',
        'titan.user',
        'titan.role',
        'titan.currentShift',
        'titan.pendingTickets',
        'titan.activeTickets',
        'titan.shiftHistory'
      ].forEach((k) => localStorage.removeItem(k))
    } catch {
      /* ignore */
    }
    window.location.hash = '#/login'
  }

  return (
    <header className="h-14 bg-zinc-950 border-b border-zinc-900 flex items-center select-none shrink-0 z-50 px-2 gap-1">
      {/* Brand */}
      <Link
        to="/terminal"
        title="Inicio"
        className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-[0_0_12px_rgba(79,70,229,0.4)] hover:scale-105 transition-transform active:scale-95 shrink-0"
      >
        T
      </Link>

      {/* Nav groups */}
      <nav className="flex items-center gap-1 flex-1 min-w-0 overflow-x-auto hide-scrollbar">
        {navGroups.map((group, gi) => (
          <div key={gi} className="contents">
            {group.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  title={item.label}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all whitespace-nowrap shrink-0 text-sm font-medium ${
                    isActive
                      ? 'bg-blue-600/10 text-blue-400 shadow-[inset_0_-2px_0_0_rgb(59,130,246)]'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'
                  }`}
                >
                  <item.icon
                    className={`w-4 h-4 shrink-0 ${isActive ? 'drop-shadow-[0_0_6px_rgba(59,130,246,0.5)]' : ''}`}
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                  <span className="hidden lg:inline">{item.label}</span>
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* User + Logout */}
      <div className="flex items-center gap-1.5 shrink-0">
        <div
          className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300 font-bold text-xs uppercase cursor-default"
          title={`Usuario Activo: ${userName}`}
        >
          {userName.slice(0, 2)}
        </div>
        <button
          onClick={handleLogout}
          title="Cerrar Sesión"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-rose-500/80 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
