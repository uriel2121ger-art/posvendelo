import type { ReactElement } from 'react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Server } from 'lucide-react'
import { loadRuntimeConfig, saveRuntimeConfig } from './posApi'
import { POS_API_URL } from './runtimeEnv'

export default function ConfigurarServidor({ onServerConfigured }: { onServerConfigured?: () => void } = {}): ReactElement {
  const navigate = useNavigate()
  const cfg = loadRuntimeConfig()
  const [baseUrl, setBaseUrl] = useState(cfg.baseUrl || '')
  const [terminalId, setTerminalId] = useState(cfg.terminalId)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSave = (): void => {
    setError('')
    setMessage('')
    const url = baseUrl.trim()
    if (!url) {
      setError('Escribe la dirección del servidor (ej. http://192.168.1.10:8000).')
      return
    }
    try {
      new URL(url)
    } catch {
      setError(`Dirección inválida. Ejemplo: ${POS_API_URL}`)
      return
    }
    if ((url.match(/https?:\/\//g) || []).length > 1) {
      setError('Solo una dirección. Borra el campo y escribe una sola URL.')
      return
    }
    if (!Number.isFinite(terminalId) || terminalId < 1) {
      setError('El ID de terminal debe ser un número mayor o igual a 1.')
      return
    }
    saveRuntimeConfig({ ...cfg, baseUrl: url, terminalId })
    setMessage('Guardado. Volviendo...')
    setTimeout(() => {
      onServerConfigured?.()
      navigate('/login', { replace: true })
    }, 600)
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6 bg-zinc-950 text-slate-200 font-sans">
      <div className="w-full max-w-md flex flex-col bg-zinc-900/95 border border-zinc-800/80 rounded-3xl shadow-2xl overflow-hidden p-8">
        <div className="flex items-center gap-3 mb-6">
          <Server className="w-8 h-8 text-blue-500" />
          <h1 className="text-xl font-bold text-zinc-100">Configurar servidor</h1>
        </div>
        <p className="text-sm text-zinc-400 mb-6">
          Indica la dirección de la PC donde está instalado el nodo (backend) de la sucursal. En app
          móvil no hay detección automática; debes poner la IP o nombre de la máquina y el puerto.
        </p>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
              Dirección del servidor
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value)
                setError('')
              }}
              placeholder="http://192.168.1.10:8000"
              className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3 px-4 text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
              autoComplete="off"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
              ID de terminal (1, 2, 3…)
            </label>
            <input
              type="number"
              min={1}
              value={terminalId}
              onChange={(e) => setTerminalId(parseInt(e.target.value, 10) || 1)}
              className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3 px-4 text-zinc-100 focus:border-blue-500 focus:outline-none"
            />
          </div>
          {error && <p className="text-sm text-rose-400">{error}</p>}
          {message && <p className="text-sm text-emerald-400">{message}</p>}
        </div>
        <div className="mt-8 flex flex-col gap-3">
          <button
            type="button"
            onClick={handleSave}
            className="w-full rounded-xl bg-blue-500 hover:bg-blue-400 py-3 px-4 font-bold text-white"
          >
            Guardar y volver al inicio de sesión
          </button>
          <button
            type="button"
            onClick={() => navigate('/login', { replace: true })}
            className="w-full rounded-xl border border-zinc-600 py-3 px-4 font-medium text-zinc-300 hover:bg-zinc-800 flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Volver al inicio de sesión
          </button>
        </div>
      </div>
    </div>
  )
}
