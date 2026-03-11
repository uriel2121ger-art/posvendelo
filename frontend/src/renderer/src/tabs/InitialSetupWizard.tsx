import { useEffect, useState, type ReactElement } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  completeInitialSetup,
  discoverPrinters,
  getInitialSetupStatus,
  loadRuntimeConfig,
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
  receipt_auto_print: boolean
  scanner_enabled: boolean
  cash_drawer_enabled: boolean
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
  receipt_auto_print: false,
  scanner_enabled: false,
  cash_drawer_enabled: false
}

export default function InitialSetupWizard(): ReactElement {
  const navigate = useNavigate()
  const [cfg] = useState<RuntimeConfig>(loadRuntimeConfig)
  const [form, setForm] = useState<SetupForm>(DEFAULT_FORM)
  const [printers, setPrinters] = useState<CupsPrinter[]>([])
  const [checking, setChecking] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

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
        // On API failure, keep wizard available so user can still intentar guardar.
      } finally {
        if (!cancelled) setChecking(false)
      }
      await loadPrinters()
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [cfg, navigate])

  const submit = async (): Promise<void> => {
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
      receipt_auto_print: form.receipt_auto_print,
      scanner_enabled: form.scanner_enabled,
      cash_drawer_enabled: form.cash_drawer_enabled
    }

    setBusy(true)
    try {
      await completeInitialSetup(cfg, payload)
      setMessage('Configuración inicial guardada. Ya puedes operar el POS.')
      navigate('/configuraciones', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (checking) {
    return <div className="p-6 text-zinc-300">Verificando instalación inicial...</div>
  }

  return (
    <div className="mx-auto max-w-3xl p-6 text-zinc-100">
      <h1 className="text-2xl font-black">Asistente inicial de POSVENDELO</h1>
      <p className="mt-2 text-sm text-zinc-400">
        Completa estos datos una sola vez. Se guardan en la base de datos y después los verás en
        Configuraciones.
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
      </div>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
      {message && <p className="mt-4 text-sm text-emerald-400">{message}</p>}

      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={busy}
          className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60"
        >
          {busy ? 'Guardando...' : 'Guardar configuración inicial'}
        </button>
      </div>
    </div>
  )
}
