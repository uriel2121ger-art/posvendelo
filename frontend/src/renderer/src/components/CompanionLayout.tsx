import type { ReactElement, ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { Activity, Radio } from 'lucide-react'

function CompanionLink({
  to,
  label,
  children
}: {
  to: string
  label: string
  children: ReactNode
}): ReactElement {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex flex-col items-center justify-center gap-1 rounded-2xl px-4 py-3 text-xs font-bold transition-all ${
          isActive
            ? 'bg-emerald-500 text-zinc-950'
            : 'bg-zinc-900/70 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100'
        }`
      }
    >
      {children}
      <span>{label}</span>
    </NavLink>
  )
}

export default function CompanionLayout({ children }: { children: ReactNode }): ReactElement {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-slate-200">
      <header className="sticky top-0 z-20 border-b border-zinc-900 bg-zinc-950/95 px-4 py-4 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-black uppercase tracking-[0.3em] text-emerald-500">
              TITAN COMPANION
            </p>
            <h1 className="truncate text-lg font-bold text-white">Control remoto de sucursal</h1>
          </div>
          <div className="rounded-full border border-zinc-800 bg-zinc-900 px-3 py-1 text-[11px] font-mono text-zinc-400">
            Companion MVP
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">{children}</main>

      <nav className="sticky bottom-0 z-20 border-t border-zinc-900 bg-zinc-950/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto grid w-full max-w-5xl grid-cols-2 gap-3">
          <CompanionLink to="/companion/remoto" label="Remoto">
            <Radio className="h-5 w-5" />
          </CompanionLink>
          <CompanionLink to="/companion/estadisticas" label="Estadísticas">
            <Activity className="h-5 w-5" />
          </CompanionLink>
        </div>
      </nav>
    </div>
  )
}
