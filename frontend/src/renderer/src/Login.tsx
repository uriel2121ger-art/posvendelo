import type { ReactElement } from 'react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, User, Terminal as TerminalIcon, LogIn } from 'lucide-react'
import { loadRuntimeConfig, saveRuntimeConfig } from './posApi'

export default function Login(): ReactElement {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault()
    setError('')

    if (!username.trim() || !password.trim()) {
      setError('Por favor, ingresa tu usuario y contraseña.')
      return
    }

    setLoading(true)

    try {
      const cfg = loadRuntimeConfig()
      const res = await fetch(`${cfg.baseUrl}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password: password.trim() })
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Error de conexión' }))
        setError(body.detail || body.error || 'Credenciales incorrectas. Intenta de nuevo.')
        return
      }

      const body = await res.json()
      const token = body.token || body.access_token || ''

      if (!token) {
        setError('Respuesta del servidor sin token. Contacta al administrador.')
        return
      }

      saveRuntimeConfig({ ...cfg, token })
      localStorage.setItem('titan.user', username.trim())
      navigate('/terminal')
    } catch (err) {
      setError(
        err instanceof TypeError
          ? 'No se puede conectar al servidor. Verifica que esté encendido.'
          : 'Error inesperado. Intenta de nuevo.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8 bg-zinc-950 text-slate-200 font-sans selection:bg-blue-500/30 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-900/10 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-purple-900/10 blur-[120px] rounded-full pointer-events-none"></div>

      <div className="z-10 w-full max-w-4xl flex flex-col md:flex-row bg-zinc-900/60 border border-zinc-800/80 rounded-3xl shadow-2xl overflow-hidden backdrop-blur-md">
        {/* Left Side: Branding / Info */}
        <div className="hidden md:flex flex-col flex-1 p-12 bg-gradient-to-br from-zinc-900 to-zinc-950 border-r border-zinc-800/80 justify-center relative overflow-hidden">
          <div className="absolute inset-0 bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(255,255,255,0.02)_10px,rgba(255,255,255,0.02)_20px)]"></div>

          <div className="relative z-10">
            <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-zinc-800/50 border border-zinc-700/50 shadow-inner mb-8">
              <TerminalIcon className="w-10 h-10 text-blue-400" />
            </div>

            <h1 className="text-4xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent mb-4">
              TITAN POS
            </h1>
            <p className="text-zinc-400 text-lg font-medium leading-relaxed max-w-sm">
              Sistema de gestión integral para abarrotes. Ingresa tus credenciales para iniciar tu
              turno.
            </p>

            <div className="mt-12 flex items-center gap-4 text-xs font-mono text-zinc-500">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div> Servidor Online
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div> Base de Datos Local
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Login Form */}
        <div className="flex-1 p-8 sm:p-12 flex flex-col justify-center items-center relative">
          <div className="w-full max-w-sm">
            <div className="text-center mb-10 md:hidden">
              <h1 className="text-3xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent mb-2">
                TITAN POS
              </h1>
              <p className="text-zinc-400 text-sm">Inicia sesión para continuar</p>
            </div>

            <h2 className="text-2xl font-bold text-zinc-100 mb-8 flex items-center gap-3">
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
                    type="text"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value)
                      setError('')
                    }}
                    placeholder="Nombre de usuario"
                    autoComplete="username"
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
                    type="password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value)
                      setError('')
                    }}
                    placeholder="••••••••"
                    className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/50 py-3.5 pl-12 pr-4 text-xl font-mono tracking-widest focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600"
                    autoFocus
                  />
                </div>
                {error && (
                  <p className="mt-2 text-sm text-rose-400 font-medium animate-pulse">{error}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={loading || password.length === 0 || username.trim().length === 0}
                className="w-full flex justify-center items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 px-4 py-4 font-bold text-white shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all hover:-translate-y-0.5 mt-8 relative z-10"
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

            <p className="mt-8 text-center text-xs text-zinc-600 font-medium">
              V 0.1.0 • TITAN POS DEMO
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
