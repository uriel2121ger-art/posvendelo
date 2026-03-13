import type { ReactElement } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, User, LogIn, Settings, Wifi } from 'lucide-react'
import { autoDiscoverBackend, isElectron, loadRuntimeConfig, saveRuntimeConfig } from './posApi'
import { POS_APP_LABEL, POS_RELEASE_LABEL } from './runtimeEnv'

export default function Login(): ReactElement {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [discovering, setDiscovering] = useState(true)
  const [error, setError] = useState('')
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null)
  const navigate = useNavigate()
  const footerLabel = POS_RELEASE_LABEL
    ? `V ${POS_RELEASE_LABEL} • ${POS_APP_LABEL}`
    : POS_APP_LABEL

  // Redirigir a configurar servidor si no hay URL guardada y no estamos en Electron.
  // Solo Electron puede asumir localhost:8000 (backend Docker local).
  useEffect(() => {
    try {
      const saved = localStorage.getItem('pos.baseUrl')
      if (saved != null && saved.trim() !== '') return
      if (isElectron()) {
        localStorage.setItem('pos.baseUrl', 'http://127.0.0.1:8000')
        return
      }
      navigate('/configurar-servidor', { replace: true })
    } catch {
      navigate('/configurar-servidor', { replace: true })
    }
  }, [navigate])

  // La verificacion de primer usuario (checkNeedsFirstUser) se maneja
  // centralizadamente en RoutedApp. Login no necesita duplicar esa logica.

  // Simple server health check via local agent (Electron only)
  useEffect(() => {
    const api = (window as Window & { api?: { agent?: { refresh?: () => Promise<unknown> } } }).api
    if (typeof api?.agent?.refresh !== 'function') return
    api.agent.refresh()
      .then((raw) => {
        const data = raw as { backendHealthy?: boolean } | null
        setBackendHealthy(Boolean(data?.backendHealthy))
      })
      .catch(() => setBackendHealthy(null))
  }, [])

  useEffect(() => {
    let cancelled = false
    autoDiscoverBackend()
      .then((url) => {
        if (cancelled) return
        if (!url) setError('No se encontró el servidor. Verifica que esté encendido.')
      })
      .finally(() => {
        if (!cancelled) setDiscovering(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault()
    setError('')

    if (!username.trim() || password.length === 0) {
      setError('Por favor, ingresa tu usuario y contraseña.')
      return
    }

    setLoading(true)

    try {
      const cfg = loadRuntimeConfig()
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 8000)
      let res: Response
      try {
        res = await fetch(`${cfg.baseUrl}/api/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: username.trim(), password }),
          signal: controller.signal
        })
      } finally {
        clearTimeout(timeout)
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Error de conexión' }))
        let msg: string
        if (typeof body.detail === 'string') {
          msg = body.detail
        } else if (Array.isArray(body.detail)) {
          msg = body.detail
            .map((e: Record<string, unknown>) => e.msg ?? '')
            .filter(Boolean)
            .join('; ')
        } else {
          msg = body.error || 'Credenciales incorrectas. Intenta de nuevo.'
        }
        setError(msg || 'Credenciales incorrectas. Intenta de nuevo.')
        return
      }

      const body = await res.json()
      const token = body.token || body.access_token || ''

      if (!token) {
        setError('Respuesta del servidor sin token. Contacta al administrador.')
        return
      }

      saveRuntimeConfig({ ...cfg, token })
      try {
        localStorage.setItem('pos.user', username.trim())
        const role = String(body.role ?? body.data?.role ?? 'cashier')
        localStorage.setItem('pos.role', role)
      } catch {
        /* storage full — non-critical, config already saved */
      }
      navigate('/terminal')
    } catch (err) {
      setError(
        err instanceof TypeError || (err instanceof DOMException && err.name === 'AbortError')
          ? 'No se puede conectar al servidor. Verifica que esté encendido.'
          : 'Error inesperado. Intenta de nuevo.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8 bg-zinc-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="z-10 w-full max-w-md flex flex-col bg-zinc-900/95 border border-zinc-800/80 rounded-3xl shadow-2xl overflow-hidden">
        {/* Login Form */}
        <div className="flex-1 p-8 sm:p-12 flex flex-col justify-center items-center relative">
          <div className="w-full max-w-sm">
            <div className="text-center mb-10 md:hidden">
              <h1 className="text-3xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent mb-2">
                POSVENDELO
              </h1>
              <p className="text-zinc-400 text-sm">Inicia sesión para continuar</p>
            </div>

            <h2 className="text-2xl font-bold text-zinc-100 mb-8 flex items-center justify-center gap-3">
              <User className="w-6 h-6 text-blue-500" />
              Acceso a caja
            </h2>

            {/* Simple server indicator — no technical details.
               Full agent/license/bootstrap details are in SettingsTab for admins. */}
            {backendHealthy != null && (
              <div className="mb-4 flex items-center justify-center gap-2 text-xs text-zinc-500">
                <Wifi className={`h-3.5 w-3.5 ${backendHealthy ? 'text-emerald-400' : 'text-rose-400'}`} />
                <span>{backendHealthy ? 'Servidor conectado' : 'Conectando al servidor...'}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="w-full space-y-5 relative">
              {/* Username Input */}
              <div className="relative z-20">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                  Usuario
                </label>
                <div className="relative group">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 z-10" />
                  <input
                    data-testid="login-username"
                    type="text"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value)
                      setError('')
                    }}
                    placeholder="Nombre de usuario"
                    autoComplete="username"
                    autoFocus
                    className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3.5 pl-12 pr-4 text-lg font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600 shadow-sm hover:border-zinc-600"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="relative z-10">
                <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2 mt-4">
                  Contraseña
                </label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                  <input
                    data-testid="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value)
                      setError('')
                    }}
                    placeholder="••••••••"
                    className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/50 py-3.5 pl-12 pr-4 text-xl font-mono tracking-widest focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600"
                  />
                </div>
{error && (
                <p className="mt-2 text-sm text-rose-400 font-medium animate-pulse">{error}</p>
                )}
                <p className="mt-3 text-xs text-zinc-500">
                  Si es la primera vez, crea tu usuario en la pantalla de configuración inicial.
                </p>
              </div>

              {(error?.includes('servidor') || (backendHealthy != null && !backendHealthy)) && (
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => navigate('/configurar-servidor')}
                    className="inline-flex items-center gap-2 rounded-xl border border-zinc-600 bg-zinc-800/80 py-2.5 px-4 text-sm font-medium text-zinc-300 hover:bg-zinc-700 hover:text-white"
                  >
                    <Settings className="w-4 h-4" />
                    Configurar dirección del servidor (IP o nombre de la PC)
                  </button>
                </div>
              )}

              <button
                data-testid="login-submit"
                type="submit"
                disabled={
                  loading || discovering || password.length === 0 || username.trim().length === 0
                }
                className="w-full flex justify-center items-center gap-2 rounded-xl bg-blue-500 hover:bg-blue-400 disabled:bg-zinc-800 disabled:text-zinc-500 px-4 py-4 font-bold text-white transition-colors mt-8 relative z-10"
              >
                {loading ? (
                  <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <>
                    <LogIn className="w-5 h-5" />
                    INGRESAR
                  </>
                )}
              </button>
            </form>

            <p className="mt-6 text-center">
              <button
                type="button"
                onClick={() => navigate('/configurar-servidor')}
                className="text-sm text-zinc-500 hover:text-blue-400 underline underline-offset-2"
              >
                Configurar servidor (IP de la PC del negocio)
              </button>
            </p>
            <p className="mt-4 text-center text-xs text-zinc-400 font-medium">
              {discovering ? (
                <span className="text-blue-400 animate-pulse">Buscando servidor...</span>
              ) : (
                <>{footerLabel}</>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
