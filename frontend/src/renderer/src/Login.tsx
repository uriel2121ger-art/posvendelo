import type { ReactElement } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, User, LogIn } from 'lucide-react'
import { autoDiscoverBackend, loadRuntimeConfig, saveRuntimeConfig } from './posApi'

export default function Login(): ReactElement {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [discovering, setDiscovering] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

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
        localStorage.setItem('titan.user', username.trim())
        const role = String(body.role ?? body.data?.role ?? 'cashier')
        localStorage.setItem('titan.role', role)
      } catch {
        /* QuotaExceeded */
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
                TITAN POS
              </h1>
              <p className="text-zinc-400 text-sm">Inicia sesión para continuar</p>
            </div>

            <h2 className="text-2xl font-bold text-zinc-100 mb-8 flex items-center justify-center gap-3">
              <User className="w-6 h-6 text-blue-500" />
              Acceso a Caja
            </h2>

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
              </div>

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

            <p className="mt-8 text-center text-xs text-zinc-400 font-medium">
              {discovering ? (
                <span className="text-blue-400 animate-pulse">Buscando servidor...</span>
              ) : (
                <>V 0.1.0 • TITAN POS DEMO</>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
