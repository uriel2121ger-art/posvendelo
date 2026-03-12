import { useEffect, useState, type ReactElement, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Lock, UserPlus } from 'lucide-react'
import { checkNeedsFirstUser, loadRuntimeConfig, saveRuntimeConfig, setupOwnerUser } from '../posApi'

const USERNAME_RE = /^[a-zA-Z0-9_]{3,50}$/

type FirstUserSetupProps = {
  onUserCreated?: () => void
}

export default function FirstUserSetup({ onUserCreated }: FirstUserSetupProps): ReactElement {
  const navigate = useNavigate()
  const [checking, setChecking] = useState(true)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [name, setName] = useState('')

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // On mount: check if setup is actually needed; redirect to login if not.
  useEffect(() => {
    let cancelled = false
    const cfg = loadRuntimeConfig()
    checkNeedsFirstUser(cfg)
      .then((needed) => {
        if (cancelled) return
        if (!needed) {
          navigate('/login', { replace: true })
        }
      })
      .catch(() => {
        // If check fails, allow the form to render so the user can try anyway.
      })
      .finally(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [navigate])

  const validate = (): string | null => {
    if (!USERNAME_RE.test(username)) {
      return 'El usuario debe tener entre 3 y 50 caracteres (letras, números y guión bajo).'
    }
    if (password.length < 8) {
      return 'La contraseña debe tener al menos 8 caracteres.'
    }
    if (password !== confirmPassword) {
      return 'Las contraseñas no coinciden.'
    }
    return null
  }

  const handleSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    setError('')

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setBusy(true)
    try {
      const cfg = loadRuntimeConfig()
      const { token, role } = await setupOwnerUser(cfg, {
        username: username.trim(),
        password,
        name: name.trim() || undefined
      })
      // Persist token using the same pattern as Login.tsx
      saveRuntimeConfig({ ...cfg, token })
      try {
        localStorage.setItem('pos.user', username.trim())
        localStorage.setItem('pos.role', role)
      } catch {
        /* storage full — non-critical */
      }
      // Notificar a RoutedApp que el usuario fue creado ANTES de navegar,
      // para que el guard de redirect no vuelva a redirigir aqui.
      onUserCreated?.()
      navigate('/setup-inicial', { replace: true })
    } catch (err) {
      if (err instanceof Error && err.name === 'ConflictError') {
        navigate('/login', { replace: true })
        return
      }
      setError((err as Error).message || 'Error inesperado. Intenta de nuevo.')
    } finally {
      setBusy(false)
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-300">
        <p className="animate-pulse">Verificando estado del sistema...</p>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8 bg-zinc-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="w-full max-w-md bg-zinc-900/95 border border-zinc-800/80 rounded-3xl shadow-2xl overflow-hidden">
        <div className="p-8 sm:p-12 flex flex-col items-center">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-black tracking-tighter bg-gradient-to-br from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent mb-2">
              POSVENDELO
            </h1>
            <p className="text-zinc-400 text-sm">Bienvenido — primera instalación</p>
          </div>

          <h2 className="text-xl font-bold text-zinc-100 mb-2 flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-blue-500" />
            Crear cuenta de administrador
          </h2>
          <p className="text-zinc-500 text-sm text-center mb-8">
            Este será el dueño del sistema. Solo se configura una vez.
          </p>

          <form
            onSubmit={(e) => void handleSubmit(e)}
            className="w-full space-y-5"
            autoComplete="off"
          >
            {/* Username */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                Usuario *
              </label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value)
                    setError('')
                  }}
                  placeholder="usuario_admin"
                  autoComplete="username"
                  autoFocus
                  className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3.5 pl-12 pr-4 text-base font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600 shadow-sm hover:border-zinc-600"
                />
              </div>
              <p className="mt-1 text-xs text-zinc-600">
                3-50 caracteres: letras, números y guión bajo.
              </p>
            </div>

            {/* Name (optional) */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                Nombre completo <span className="normal-case font-normal text-zinc-600">(opcional)</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Juan García"
                autoComplete="name"
                className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3.5 px-4 text-base font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600 shadow-sm hover:border-zinc-600"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                Contraseña *
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
                  autoComplete="new-password"
                  className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3.5 pl-12 pr-4 text-xl font-mono tracking-widest focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600 shadow-sm hover:border-zinc-600"
                />
              </div>
              <p className="mt-1 text-xs text-zinc-600">Mínimo 8 caracteres.</p>
            </div>

            {/* Confirm password */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
                Confirmar contraseña *
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    setError('')
                  }}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  className="w-full rounded-xl border-2 border-zinc-700 bg-zinc-900/90 py-3.5 pl-12 pr-4 text-xl font-mono tracking-widest focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-white placeholder:text-zinc-600 shadow-sm hover:border-zinc-600"
                />
              </div>
            </div>

            {error && (
              <p className="text-sm text-rose-400 font-medium animate-pulse">{error}</p>
            )}

            <button
              type="submit"
              disabled={
                busy ||
                username.trim().length === 0 ||
                password.length === 0 ||
                confirmPassword.length === 0
              }
              className="w-full flex justify-center items-center gap-2 rounded-xl bg-blue-500 hover:bg-blue-400 disabled:bg-zinc-800 disabled:text-zinc-500 px-4 py-4 font-bold text-white transition-colors mt-4"
            >
              {busy ? (
                <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <UserPlus className="w-5 h-5" />
                  CREAR CUENTA Y CONTINUAR
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
