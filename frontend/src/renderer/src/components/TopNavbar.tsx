import type { ReactElement } from 'react'
import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useConfirm } from './ConfirmDialog'
import { getLicenseStatus, loadRuntimeConfig } from '../posApi'
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
  LogOut,
  MoreHorizontal,
  Receipt,
  MonitorDot
} from 'lucide-react'

type NavItem = { path: string; label: string; icon: typeof ShoppingCart }

const navGroups: NavItem[][] = [
  [{ path: '/terminal', label: 'Ventas', icon: ShoppingCart }],
  [
    { path: '/productos', label: 'Productos', icon: Box },
    { path: '/clientes', label: 'Clientes', icon: Users },
    { path: '/inventario', label: 'Inventario', icon: ClipboardList }
  ],
  [
    { path: '/turnos', label: 'Turnos', icon: Clock },
    { path: '/historial', label: 'Historial', icon: FileText },
    { path: '/mermas', label: 'Mermas', icon: PackageX }
  ],
  [
    { path: '/reportes', label: 'Reportes', icon: BarChart3 },
    { path: '/estadisticas', label: 'Estadísticas', icon: LayoutDashboard }
  ],
  [
    { path: '/gastos', label: 'Gastos', icon: Receipt },
    { path: '/empleados', label: 'Empleados', icon: UserCog },
    { path: '/remoto', label: 'Remoto', icon: Radio },
    { path: '/fiscal', label: 'Fiscal', icon: Landmark },
    { path: '/hardware', label: 'Dispositivos', icon: MonitorDot },
    { path: '/configuraciones', label: 'Ajustes', icon: Settings }
  ]
]

/** Rutas que siempre se muestran en la barra principal. */
const PRIMARY_PATHS = new Set([
  '/terminal',
  '/productos',
  '/clientes',
  '/inventario',
  '/turnos',
  '/historial',
  '/reportes',
  '/configuraciones'
])

const allItems = navGroups.flat()
const primaryItems = allItems.filter((item) => PRIMARY_PATHS.has(item.path))
const moreItemsByGroup = navGroups
  .map((group) => group.filter((item) => !PRIMARY_PATHS.has(item.path)))
  .filter((g) => g.length > 0)

export default function TopNavbar(): ReactElement {
  const location = useLocation()
  const confirm = useConfirm()
  const [moreOpen, setMoreOpen] = useState(false)
  const [moreOpenPath, setMoreOpenPath] = useState(location.pathname)
  const [licenseBanner, setLicenseBanner] = useState<string | null>(null)
  const moreRef = useRef<HTMLDivElement>(null)
  const isMoreMenuOpen = moreOpen && moreOpenPath === location.pathname

  useEffect(() => {
    if (!isMoreMenuOpen) return
    const close = (e: MouseEvent): void => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false)
      }
    }
    document.addEventListener('click', close, true)
    return () => document.removeEventListener('click', close, true)
  }, [isMoreMenuOpen])

  useEffect(() => {
    let cancelled = false
    void getLicenseStatus(loadRuntimeConfig())
      .then((body) => {
        if (cancelled) return
        const data = (body.data ?? body) as {
          effective_status?: string
          message?: string
          days_remaining?: number | null
        }
        if (data.effective_status === 'grace') {
          setLicenseBanner(data.message ?? 'Licencia mensual en gracia.')
          return
        }
        if (data.effective_status === 'expired') {
          setLicenseBanner(data.message ?? 'Licencia vencida. Operación restringida.')
          return
        }
        if (
          data.effective_status === 'active' &&
          typeof data.days_remaining === 'number' &&
          data.days_remaining >= 0 &&
          data.days_remaining <= 10
        ) {
          setLicenseBanner(`Licencia vence en ${data.days_remaining} día(s).`)
          return
        }
        if (data.effective_status === 'support_expired') {
          setLicenseBanner(data.message ?? 'Soporte vencido; el sistema sigue operando.')
          return
        }
        setLicenseBanner(null)
      })
      .catch(() => {
        if (!cancelled) setLicenseBanner(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const userName = (() => {
    try {
      return localStorage.getItem('titan.user') || 'Usuario'
    } catch {
      return 'Usuario'
    }
  })()

  const handleLogout = async (): Promise<void> => {
    const hasPending = (() => {
      try {
        const user = localStorage.getItem('titan.user')
        const key = user ? `titan.pendingTickets.${user}` : 'titan.pendingTickets'
        const raw = localStorage.getItem(key)
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

    if (!(await confirm(msg, { variant: 'warning', title: 'Cerrar sesión' }))) return

    try {
      // No borrar titan.pendingTickets ni titan.activeTickets (ni sus variantes por usuario):
      // así los borradores y tickets pendientes persisten al cerrar sesión y al expirar el token.
      ;[
        'titan.token',
        'titan.user',
        'titan.role',
        'titan.currentShift',
        'titan.shiftHistory'
      ].forEach((k) => localStorage.removeItem(k))
    } catch {
      /* ignore */
    }
    window.location.hash = '#/login'
  }

  return (
    <div className="shrink-0 z-50">
      {licenseBanner && (
        <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-center text-xs font-semibold text-amber-200">
          {licenseBanner}
        </div>
      )}
      <header className="h-14 bg-zinc-950 border-b border-zinc-900 flex items-center select-none">
        <div className="flex items-center w-full h-full px-3 gap-3 min-w-0">
          {/* Brand */}
          <Link
            to="/terminal"
            title="Inicio"
            className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-[0_0_12px_rgba(79,70,229,0.4)] hover:scale-105 transition-transform active:scale-95 shrink-0"
          >
            T
          </Link>

          {/* Nav: principales + "Más" */}
          <nav className="flex items-center gap-0.5 flex-1 min-w-0 overflow-x-auto overflow-y-hidden hide-scrollbar">
            {primaryItems.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  title={item.label}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all whitespace-nowrap shrink-0 text-sm font-medium ${
                    isActive
                      ? 'bg-blue-600/10 text-blue-400 shadow-[inset_0_-2px_0_0_rgb(59,130,246)]'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'
                  }`}
                >
                  <item.icon
                    className={`w-4 h-4 shrink-0 ${isActive ? 'drop-shadow-[0_0_6px_rgba(59,130,246,0.5)]' : ''}`}
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              )
            })}
            <div className="relative shrink-0" ref={moreRef}>
              <button
                type="button"
                onClick={() => {
                  setMoreOpenPath(location.pathname)
                  setMoreOpen((open) => !open)
                }}
                title="Más opciones"
                className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-sm font-medium ${
                  isMoreMenuOpen ||
                  allItems.some((i) => !PRIMARY_PATHS.has(i.path) && location.pathname === i.path)
                    ? 'bg-blue-600/10 text-blue-400 shadow-[inset_0_-2px_0_0_rgb(59,130,246)]'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'
                }`}
              >
                <MoreHorizontal className="w-4 h-4 shrink-0" strokeWidth={2} />
                <span className="hidden sm:inline">Más</span>
              </button>
              {isMoreMenuOpen && (
                <div
                  className="absolute top-full left-0 mt-1 min-w-[200px] py-2 rounded-xl border border-zinc-800 bg-zinc-900 shadow-xl z-[100]"
                  role="menu"
                >
                  {moreItemsByGroup.map((group, gi) => (
                    <div key={gi} className="contents">
                      {group.map((item) => {
                        const isActive = location.pathname === item.path
                        return (
                          <Link
                            key={item.path}
                            to={item.path}
                            role="menuitem"
                            title={item.label}
                            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                              isActive
                                ? 'bg-blue-600/20 text-blue-400'
                                : 'text-zinc-300 hover:bg-zinc-800 hover:text-white'
                            }`}
                            onClick={() => setMoreOpen(false)}
                          >
                            <item.icon className="w-4 h-4 shrink-0" strokeWidth={2} />
                            {item.label}
                          </Link>
                        )
                      })}
                      {gi < moreItemsByGroup.length - 1 && (
                        <div key={`sep-${gi}`} className="my-1 border-t border-zinc-800" />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </nav>

          {/* Usuario + Cerrar sesión */}
          <div className="flex items-center gap-2 shrink-0 pl-1">
            <div
              className="w-8 h-8 rounded-full bg-zinc-800/80 border border-zinc-700 flex items-center justify-center text-zinc-300 font-bold text-xs uppercase cursor-default"
              title={`Usuario: ${userName}`}
            >
              {userName.slice(0, 2)}
            </div>
            <button
              onClick={handleLogout}
              title="Cerrar sesión"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-rose-500/80 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>
    </div>
  )
}
