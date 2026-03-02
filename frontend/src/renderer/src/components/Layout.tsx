import type { ReactElement, ReactNode } from 'react'
import Sidebar from './Sidebar'

export default function Layout({ children }: { children: ReactNode }): ReactElement {
  return (
    <div className="flex h-screen bg-zinc-950 text-slate-200 overflow-hidden font-sans">
      <Sidebar />
      <main className="flex-1 overflow-hidden relative flex flex-col">
        {children}
      </main>
    </div>
  )
}
