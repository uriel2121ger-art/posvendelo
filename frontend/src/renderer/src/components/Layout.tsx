import type { ReactElement, ReactNode } from 'react'
import TopNavbar from './TopNavbar'

export default function Layout({ children }: { children: ReactNode }): ReactElement {
  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-slate-200 overflow-hidden font-sans">
      <TopNavbar />
      <main className="flex-1 overflow-hidden relative flex flex-col">{children}</main>
    </div>
  )
}
