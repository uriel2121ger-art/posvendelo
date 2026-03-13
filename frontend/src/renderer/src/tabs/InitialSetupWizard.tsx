import { useEffect, useState, type ReactElement } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  activateCloud,
  completeInitialSetup,
  discoverPrinters,
  getCloudStatus,
  getInitialSetupStatus,
  loadRuntimeConfig,
  type CloudStatus,
  type CupsPrinter,
  type InitialSetupPayload,
  type RuntimeConfig
} from '../posApi'

type SetupForm = {
  business_name: string
  business_legal_name: string
  business_address: string
  business_rfc: string
  business_regimen: string
  business_phone: string
  business_footer: string
  receipt_printer_name: string
  receipt_printer_enabled: boolean
  receipt_paper_width: 58 | 80
  receipt_auto_print: boolean
  scanner_enabled: boolean
  cash_drawer_enabled: boolean
  cash_drawer_auto_open_cash: boolean
}

const DEFAULT_FORM: SetupForm = {
  business_name: '',
  business_legal_name: '',
  business_address: '',
  business_rfc: '',
  business_regimen: '',
  business_phone: '',
  business_footer: 'Gracias por su compra',
  receipt_printer_name: '',
  receipt_printer_enabled: false,
  receipt_paper_width: 80,
  receipt_auto_print: false,
  scanner_enabled: false,
  cash_drawer_enabled: false,
  cash_drawer_auto_open_cash: true
}

type InitialSetupWizardProps = {
  onSetupCompleted?: () => void
}

export default function InitialSetupWizard({ onSetupCompleted }: InitialSetupWizardProps): ReactElement {
  const navigate = useNavigate()
  const [cfg] = useState<RuntimeConfig>(loadRuntimeConfig)
  const [form, setForm] = useState<SetupForm>(DEFAULT_FORM)
  const [printers, setPrinters] = useState<CupsPrinter[]>([])
  const [step, setStep] = useState<1 | 2>(1)
  const [cloudStatus, setCloudStatus] = useState<CloudStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  // Step 2 registration form
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regPasswordConfirm, setRegPasswordConfirm] = useState('')

  const loadPrinters = async (): Promise<void> => {
    try {
      const list = await discoverPrinters(cfg)
      setPrinters(list)
    } catch {
      setPrinters([])
    }
  }

  useEffect(() => {
    let cancelled = false
    const run = async (): Promise<void> => {
      try {
        const status = await getInitialSetupStatus(cfg)
        if (cancelled) return
        if (status.completed) {
          navigate('/terminal', { replace: true })
          return
        }
      } catch {
        // On API failure, keep wizard available.
      } finally {
        if (!cancelled) setChecking(false)
      }
      if (!cancelled) await loadPrinters()
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [cfg, navigate])

  useEffect(() => {
    if (step !== 2) return
    let cancelled = false
    const run = async (): Promise<void> => {
      try {
        const status = await getCloudStatus(cfg)
        if (!cancelled) setCloudStatus(status)
      } catch {
        if (!cancelled) setCloudStatus({ cloud_activated: false, control_plane_connected: false })
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [step, cfg])

  const submitStep1 = async (): Promise<void> => {
    setError('')
    setMessage('')

    const businessName = form.business_name.trim()
    if (businessName.length < 2) {
      setError('El nombre del negocio es obligatorio (mínimo 2 caracteres).')
      return
    }

    const payload: InitialSetupPayload = {
      business_name: businessName,
      business_legal_name: form.business_legal_name.trim() || undefined,
      business_address: form.business_address.trim() || undefined,
      business_rfc: form.business_rfc.trim().toUpperCase() || undefined,
      business_regimen: form.business_regimen.trim() || undefined,
      business_phone: form.business_phone.trim() || undefined,
      business_footer: form.business_footer.trim() || undefined,
      receipt_printer_name: form.receipt_printer_name.trim() || undefined,
      receipt_printer_enabled: form.receipt_printer_enabled,
      receipt_paper_width: form.receipt_paper_width,
      receipt_auto_print: form.receipt_auto_print,
      scanner_enabled: form.scanner_enabled,
      cash_drawer_enabled: form.cash_drawer_enabled,
      cash_drawer_auto_open_cash: form.cash_drawer_auto_open_cash
    }

    setBusy(true)
    try {
      await completeInitialSetup(cfg, payload)
      onSetupCompleted?.()
      setStep(2)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const goToTerminal = (): void => {
    navigate('/terminal', { replace: true })
  }

  const submitRegister = async (): Promise<void> => {
    setError('')
    const email = regEmail.trim().toLowerCase()
    if (!email || !email.includes('@')) {
      setError('Indica un correo válido.')
      return
    }
    if (regPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (regPassword !== regPasswordConfirm) {
      setError('La contraseña y la confirmación no coinciden.')
      return
    }

    setBusy(true)
    try {
      await activateCloud(cfg, {
        email,
        password: regPassword,
        business_name: form.business_name.trim() || undefined
      })
      goToTerminal()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-zinc-400 text-sm">Preparando configuración...</p>
        </div>
      </div>
    )
  }

  if (step === 2) {
    return (
      <div className="mx-auto max-w-3xl p-6 text-zinc-100">
        <h1 className="text-2xl font-black">Registro para monitoreo</h1>
        <p className="mt-2 text-sm text-zinc-400">
          Vincula esta sucursal con una cuenta (correo y contraseña) para verla desde la app del dueño (nodo central).
        </p>

        {cloudStatus === null ? (
          <div className="mt-6 flex items-center justify-center gap-2 text-zinc-400">
            <div className="w-5 h-5 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin" />
            <span>Comprobando conexión con el servidor central...</span>
          </div>
        ) : !cloudStatus.control_plane_connected ? (
          <div className="mt-6 rounded-lg border border-amber-800 bg-amber-950/30 p-4 text-amber-200 text-sm">
            <p>Para registrar desde aquí el nodo debe estar conectado al servidor central.</p>
            <p className="mt-2 text-zinc-400">Podrás completar el registro más tarde en Configuración.</p>
            <button
              type="button"
              onClick={goToTerminal}
              className="mt-4 rounded bg-blue-600 px-4 py-2 font-semibold text-white"
            >
              Ir al punto de venta
            </button>
          </div>
        ) : cloudStatus.cloud_activated ? (
          <div className="mt-6 rounded-lg border border-emerald-800 bg-emerald-950/30 p-4 text-emerald-200 text-sm">
            <p>La sucursal ya está vinculada al servidor central.</p>
            <button
              type="button"
              onClick={goToTerminal}
              className="mt-4 rounded bg-blue-600 px-4 py-2 font-semibold text-white"
            >
              Ir al punto de venta
            </button>
          </div>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
              <label className="text-sm">
                Correo electrónico *
                <input
                  type="email"
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  autoComplete="email"
                />
              </label>
              <label className="text-sm md:col-span-2">
                Contraseña (mínimo 8 caracteres) *
                <input
                  type="password"
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              <label className="text-sm md:col-span-2">
                Confirmar contraseña *
                <input
                  type="password"
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
                  value={regPasswordConfirm}
                  onChange={(e) => setRegPasswordConfirm(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
            </div>
            {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void submitRegister()}
                disabled={busy}
                className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60"
              >
                {busy ? 'Registrando...' : 'Registrar y terminar'}
              </button>
              <button
                type="button"
                onClick={goToTerminal}
                disabled={busy}
                className="rounded border border-zinc-600 px-4 py-2 text-zinc-300 hover:bg-zinc-800"
              >
                Omitir por ahora
              </button>
            </div>
            <p className="mt-3 text-xs text-zinc-500">Podrás completar esto más tarde en Configuración.</p>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl p-6 text-zinc-100">
      <h1 className="text-2xl font-black">Asistente inicial de POSVENDELO</h1>
      <p className="mt-2 text-sm text-zinc-400">
        Completa estos datos una sola vez. Se guardan en la base de datos y después los verás en Configuración.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <label className="text-sm">
          Nombre del negocio *
          <input
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            value={form.business_name}
            onChange={(e) => setForm((prev) => ({ ...prev, business_name: e.target.value }))}
          />
        </label>
        <label className="text-sm">
          Razón social
          <input
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            value={form.business_legal_name}
            onChange={(e) => setForm((prev) => ({ ...prev, business_legal_name: e.target.value }))}
          />
        </label>
        <label className="text-sm">
          RFC
          <input
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 uppercase"
            value={form.business_rfc}
            onChange={(e) => setForm((prev) => ({ ...prev, business_rfc: e.target.value }))}
          />
        </label>
        <label className="text-sm">
          Teléfono
          <input
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            value={form.business_phone}
            onChange={(e) => setForm((prev) => ({ ...prev, business_phone: e.target.value }))}
          />
        </label>
        <label className="text-sm md:col-span-2">
          Dirección
          <input
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            value={form.business_address}
            onChange={(e) => setForm((prev) => ({ ...prev, business_address: e.target.value }))}
          />
        </label>
        <label className="text-sm md:col-span-2">
          Pie de ticket
          <input
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            value={form.business_footer}
            onChange={(e) => setForm((prev) => ({ ...prev, business_footer: e.target.value }))}
          />
        </label>

        <label className="text-sm md:col-span-2">
          Impresora de ticket
          <div className="mt-1 flex gap-2">
            <select
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
              value={form.receipt_printer_name}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, receipt_printer_name: e.target.value }))
              }
            >
              <option value="">Seleccionar impresora (opcional)</option>
              {printers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void loadPrinters()}
              className="rounded border border-zinc-700 px-3 py-2 text-sm"
            >
              Buscar
            </button>
          </div>
        </label>

        <label className="text-sm">
          Ancho de papel del ticket
          <select
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            value={form.receipt_paper_width}
            onChange={(e) =>
              setForm((prev) => ({
                ...prev,
                receipt_paper_width: Number(e.target.value) as 58 | 80
              }))
            }
          >
            <option value={58}>58 mm</option>
            <option value={80}>80 mm</option>
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm md:col-span-2">
          <input
            type="checkbox"
            checked={form.receipt_printer_enabled}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, receipt_printer_enabled: e.target.checked }))
            }
          />
          Habilitar impresión de tickets
        </label>
        <label className="flex items-center gap-2 text-sm md:col-span-2">
          <input
            type="checkbox"
            checked={form.receipt_auto_print}
            onChange={(e) => setForm((prev) => ({ ...prev, receipt_auto_print: e.target.checked }))}
          />
          Imprimir en automático al cobrar
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.scanner_enabled}
            onChange={(e) => setForm((prev) => ({ ...prev, scanner_enabled: e.target.checked }))}
          />
          Habilitar escáner
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.cash_drawer_enabled}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, cash_drawer_enabled: e.target.checked }))
            }
          />
          Habilitar cajón
        </label>
        <label className="flex items-center gap-2 text-sm md:col-span-2">
          <input
            type="checkbox"
            checked={form.cash_drawer_auto_open_cash}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, cash_drawer_auto_open_cash: e.target.checked }))
            }
          />
          Abrir cajón al cobrar en efectivo
        </label>
      </div>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
      {message && <p className="mt-4 text-sm text-emerald-400">{message}</p>}

      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={() => void submitStep1()}
          disabled={busy}
          className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60"
        >
          {busy ? 'Guardando...' : 'Guardar y continuar'}
        </button>
      </div>
    </div>
  )
}
