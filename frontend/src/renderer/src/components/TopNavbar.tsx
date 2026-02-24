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
  LayoutDashboard,
  Clock,
  BarChart3
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
    { path: '/configuraciones', label: 'Ajustes', icon: Settings }
  ]

  return (
    <div className="flex items-center gap-1 bg-zinc-900 border-b border-zinc-800 p-2 overflow-x-auto shrink-0 select-none">
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 px-3 py-2 mr-2 rounded font-bold transition-colors text-white hover:bg-zinc-800"
        title="Volver al Menú Principal"
      >
        <LayoutDashboard className="w-5 h-5 text-indigo-400" />
      </button>
      <div className="w-px h-6 bg-zinc-800 mx-1"></div>

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
          <div className="font-bold text-zinc-300">Admin</div>
        </div>
        <Link
          to="/"
          className="text-rose-500/80 hover:text-rose-400 transition-colors"
          title="Cerrar Sesion"
        >
          <LogOut className="w-5 h-5" />
        </Link>
      </div>
    </div>
  )
}
