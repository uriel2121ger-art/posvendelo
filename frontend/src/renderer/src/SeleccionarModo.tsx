import type { ReactElement } from 'react'
import { useState } from 'react'
import { Monitor, Wifi } from 'lucide-react'

type Props = {
  onModeSelected: (mode: 'principal' | 'client') => void | Promise<void>
}

export default function SeleccionarModo({ onModeSelected }: Props): ReactElement {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const handleSelect = async (mode: 'principal' | 'client'): Promise<void> => {
    setBusy(true)
    setError('')
    try {
      // onModeSelected handles the full flow including IPC file write.
      // For 'principal': ensureBackend runs first; mode persisted only on success.
      // For 'client': mode persisted immediately, then navigates.
      await onModeSelected(mode)
    } catch {
      setError('No se pudo configurar el servidor. Verifica tu conexión a internet e intenta de nuevo.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-slate-200 p-8">
      <div className="max-w-2xl w-full text-center">
        <h1 className="text-3xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent mb-2">
          POSVENDELO
        </h1>
        <h2 className="text-xl font-bold text-zinc-300 mb-2">¿Cómo se usará esta PC?</h2>
        <p className="text-zinc-500 mb-8">Selecciona el modo de operación para esta terminal</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {/* PC Principal */}
          <button
            disabled={busy}
            onClick={() => void handleSelect('principal')}
            className="group relative rounded-2xl border-2 border-zinc-700 bg-zinc-900 p-8 text-left transition-all hover:border-blue-500 hover:bg-zinc-800/80 disabled:opacity-50"
          >
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-blue-600/20 text-blue-400 group-hover:bg-blue-600/30">
              <Monitor className="h-7 w-7" />
            </div>
            <h3 className="text-lg font-bold text-zinc-100 mb-2">PC principal</h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Esta PC será el servidor de la sucursal. Instala la base de datos y el sistema completo.
            </p>
            <div className="mt-4 text-xs text-zinc-600">
              Requiere conexión a internet para la primera configuración
            </div>
          </button>

          {/* Caja secundaria */}
          <button
            disabled={busy}
            onClick={() => void handleSelect('client')}
            className="group relative rounded-2xl border-2 border-zinc-700 bg-zinc-900 p-8 text-left transition-all hover:border-emerald-500 hover:bg-zinc-800/80 disabled:opacity-50"
          >
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-emerald-600/20 text-emerald-400 group-hover:bg-emerald-600/30">
              <Wifi className="h-7 w-7" />
            </div>
            <h3 className="text-lg font-bold text-zinc-100 mb-2">Caja secundaria</h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Esta PC se conecta a otro servidor en la red. No necesita base de datos.
            </p>
            <div className="mt-4 text-xs text-zinc-600">
              Necesitas la dirección IP del servidor principal
            </div>
          </button>
        </div>

        {busy && (
          <div className="mt-8 flex items-center justify-center gap-3">
            <div className="w-5 h-5 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
            <span className="text-zinc-400 text-sm">Configurando...</span>
          </div>
        )}
        {error && (
          <p className="mt-6 text-rose-400 text-sm">{error}</p>
        )}
      </div>
    </div>
  )
}
