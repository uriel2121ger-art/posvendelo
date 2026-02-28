import type { ReactElement } from 'react'
import TopNavbar from './components/TopNavbar'
import { useCallback, useEffect, useState } from 'react'
import { Printer, ScanBarcode, DoorOpen, Building2, RefreshCw } from 'lucide-react'
import {
  type RuntimeConfig,
  type HardwareConfig,
  type CupsPrinter,
  loadRuntimeConfig,
  getHardwareConfig,
  updateHardwareConfig,
  discoverPrinters,
  testPrint,
  testDrawer
} from './posApi'

const HW_CACHE_KEY = 'titan.hwConfig'

function saveToCache(cfg: HardwareConfig): void {
  try {
    localStorage.setItem(HW_CACHE_KEY, JSON.stringify(cfg))
  } catch {
    /* quota exceeded */
  }
}

export default function HardwareTab(): ReactElement {
  const [config] = useState<RuntimeConfig>(loadRuntimeConfig)
  const [hw, setHw] = useState<HardwareConfig | null>(null)
  const [printers, setPrinters] = useState<CupsPrinter[]>([])
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [section, setSection] = useState<'printer' | 'business' | 'scanner' | 'drawer'>('printer')

  const load = useCallback(async () => {
    try {
      const data = await getHardwareConfig(config)
      setHw(data)
      saveToCache(data)
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`)
    }
  }, [config])

  useEffect(() => {
    load()
  }, [load])

  const handleSave = async (sec: typeof section, body: Record<string, unknown>) => {
    setBusy(true)
    setMsg('')
    try {
      await updateHardwareConfig(config, sec, body)
      await load()
      setMsg('Guardado correctamente')
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleDiscover = async () => {
    setBusy(true)
    setMsg('')
    try {
      const list = await discoverPrinters(config)
      setPrinters(list)
      setMsg(`${list.length} impresora(s) detectada(s)`)
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleTestPrint = async () => {
    setBusy(true)
    setMsg('')
    try {
      await testPrint(config)
      setMsg('Ticket de prueba enviado')
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleTestDrawer = async () => {
    setBusy(true)
    setMsg('')
    try {
      await testDrawer(config)
      setMsg('Cajon de prueba abierto')
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  if (!hw) {
    return (
      <div className="flex flex-col min-h-screen bg-zinc-950 text-slate-200">
        <TopNavbar />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-zinc-500">Cargando configuracion de hardware...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-screen bg-zinc-950 text-slate-200">
      <TopNavbar />
      <div className="flex-1 overflow-y-auto p-4 md:p-6 max-w-4xl mx-auto w-full">
        <h1 className="text-xl font-bold mb-4">Configuracion de Hardware</h1>

        {msg && (
          <div
            className={`mb-4 px-4 py-2 rounded text-sm font-medium ${
              msg.startsWith('Error') ? 'bg-rose-900/40 text-rose-300' : 'bg-emerald-900/40 text-emerald-300'
            }`}
          >
            {msg}
          </div>
        )}

        {/* Section tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {[
            { key: 'printer' as const, label: 'Impresora', icon: Printer },
            { key: 'business' as const, label: 'Negocio', icon: Building2 },
            { key: 'scanner' as const, label: 'Scanner', icon: ScanBarcode },
            { key: 'drawer' as const, label: 'Cajon', icon: DoorOpen }
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setSection(tab.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded font-medium transition-colors ${
                section === tab.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* PRINTER SECTION */}
        {section === 'printer' && (
          <div className="space-y-4">
            <Card title="Impresora de Tickets">
              <div className="flex gap-2 mb-4">
                <button onClick={handleDiscover} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 text-sm font-medium hover:bg-zinc-700 disabled:opacity-50 transition-colors">
                  <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} />
                  Detectar Impresoras
                </button>
                <button onClick={handleTestPrint} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 text-sm font-medium hover:bg-zinc-700 disabled:opacity-50 transition-colors">
                  Imprimir Prueba
                </button>
              </div>

              {printers.length > 0 && (
                <div className="mb-4 border border-zinc-700 rounded overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-800">
                      <tr>
                        <th className="px-3 py-2 text-left">Nombre</th>
                        <th className="px-3 py-2 text-left">Estado</th>
                        <th className="px-3 py-2 text-left">Default</th>
                        <th className="px-3 py-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {printers.map((p) => (
                        <tr key={p.name} className="border-t border-zinc-800">
                          <td className="px-3 py-2 font-mono">{p.name}</td>
                          <td className="px-3 py-2">
                            <span className={p.enabled ? 'text-emerald-400' : 'text-rose-400'}>
                              {p.status}
                            </span>
                          </td>
                          <td className="px-3 py-2">{p.is_default ? 'Si' : ''}</td>
                          <td className="px-3 py-2">
                            <button
                              onClick={() =>
                                handleSave('printer', { receipt_printer_name: p.name })
                              }
                              className="text-xs text-blue-400 hover:text-blue-300"
                            >
                              Seleccionar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label="Impresora seleccionada">
                  <input
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                    value={hw.printer.name}
                    onChange={(e) => setHw({ ...hw, printer: { ...hw.printer, name: e.target.value } })}
                  />
                </Field>
                <Field label="Ancho de papel">
                  <select
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                    value={hw.printer.paper_width}
                    onChange={(e) => {
                      const w = Number(e.target.value)
                      setHw({
                        ...hw,
                        printer: { ...hw.printer, paper_width: w, char_width: w === 58 ? 32 : 48 }
                      })
                    }}
                  >
                    <option value={58}>58mm (32 chars)</option>
                    <option value={80}>80mm (48 chars)</option>
                  </select>
                </Field>
                <Field label="Modo">
                  <select
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                    value={hw.printer.mode}
                    onChange={(e) =>
                      setHw({ ...hw, printer: { ...hw.printer, mode: e.target.value } })
                    }
                  >
                    <option value="basic">Basico</option>
                    <option value="fiscal">Fiscal (con IVA/RFC)</option>
                  </select>
                </Field>
                <Field label="Tipo de corte">
                  <select
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                    value={hw.printer.cut_type}
                    onChange={(e) =>
                      setHw({ ...hw, printer: { ...hw.printer, cut_type: e.target.value } })
                    }
                  >
                    <option value="partial">Parcial</option>
                    <option value="full">Completo</option>
                  </select>
                </Field>
                <Toggle
                  label="Impresora habilitada"
                  checked={hw.printer.enabled}
                  onChange={(v) => setHw({ ...hw, printer: { ...hw.printer, enabled: v } })}
                />
                <Toggle
                  label="Auto-imprimir al cobrar"
                  checked={hw.printer.auto_print}
                  onChange={(v) => setHw({ ...hw, printer: { ...hw.printer, auto_print: v } })}
                />
              </div>
              <div className="mt-4">
                <button
                  disabled={busy}
                  onClick={() =>
                    handleSave('printer', {
                      receipt_printer_name: hw.printer.name,
                      receipt_printer_enabled: hw.printer.enabled,
                      receipt_paper_width: hw.printer.paper_width,
                      receipt_char_width: hw.printer.char_width,
                      receipt_auto_print: hw.printer.auto_print,
                      receipt_mode: hw.printer.mode,
                      receipt_cut_type: hw.printer.cut_type
                    })
                  }
                  className="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-500 disabled:opacity-50 transition-colors"
                >
                  Guardar Impresora
                </button>
              </div>
            </Card>
          </div>
        )}

        {/* BUSINESS SECTION */}
        {section === 'business' && (
          <Card title="Datos del Negocio">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Nombre del negocio">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.name}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, name: e.target.value } })
                  }
                />
              </Field>
              <Field label="Razon social" full>
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.legal_name}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, legal_name: e.target.value } })
                  }
                />
              </Field>
              <Field label="RFC">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.rfc}
                  maxLength={13}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, rfc: e.target.value.toUpperCase() } })
                  }
                />
              </Field>
              <Field label="Regimen fiscal">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.regimen}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, regimen: e.target.value } })
                  }
                />
              </Field>
              <Field label="Telefono">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.phone}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, phone: e.target.value } })
                  }
                />
              </Field>
              <Field label="Direccion" full>
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.address}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, address: e.target.value } })
                  }
                />
              </Field>
              <Field label="Pie de ticket" full>
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.business.footer}
                  onChange={(e) =>
                    setHw({ ...hw, business: { ...hw.business, footer: e.target.value } })
                  }
                />
              </Field>
            </div>
            <div className="mt-4">
              <button
                disabled={busy}
                onClick={() =>
                  handleSave('business', {
                    business_name: hw.business.name,
                    business_legal_name: hw.business.legal_name,
                    business_address: hw.business.address,
                    business_rfc: hw.business.rfc,
                    business_regimen: hw.business.regimen,
                    business_phone: hw.business.phone,
                    business_footer: hw.business.footer
                  })
                }
                className="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-500 disabled:opacity-50 transition-colors"
              >
                Guardar Datos del Negocio
              </button>
            </div>
          </Card>
        )}

        {/* SCANNER SECTION */}
        {section === 'scanner' && (
          <Card title="Lector de Codigo de Barras">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Toggle
                label="Scanner habilitado"
                checked={hw.scanner.enabled}
                onChange={(v) => setHw({ ...hw, scanner: { ...hw.scanner, enabled: v } })}
              />
              <Toggle
                label="Auto-submit al escanear"
                checked={hw.scanner.auto_submit}
                onChange={(v) => setHw({ ...hw, scanner: { ...hw.scanner, auto_submit: v } })}
              />
              <Field label="Prefijo">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.scanner.prefix}
                  placeholder="ej: ~"
                  onChange={(e) =>
                    setHw({ ...hw, scanner: { ...hw.scanner, prefix: e.target.value } })
                  }
                />
              </Field>
              <Field label="Sufijo">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm font-mono focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.scanner.suffix}
                  placeholder="ej: \\n"
                  onChange={(e) =>
                    setHw({ ...hw, scanner: { ...hw.scanner, suffix: e.target.value } })
                  }
                />
              </Field>
              <Field label="Velocidad minima (ms)">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  type="number"
                  min={10}
                  max={500}
                  value={hw.scanner.min_speed_ms}
                  onChange={(e) =>
                    setHw({
                      ...hw,
                      scanner: { ...hw.scanner, min_speed_ms: Number(e.target.value) || 50 }
                    })
                  }
                />
              </Field>
            </div>
            <p className="text-xs text-zinc-500 mt-2">
              Si el intervalo entre teclas es menor a la velocidad minima, se considera input de
              scanner (no humano).
            </p>
            <div className="mt-4">
              <button
                disabled={busy}
                onClick={() =>
                  handleSave('scanner', {
                    scanner_enabled: hw.scanner.enabled,
                    scanner_prefix: hw.scanner.prefix,
                    scanner_suffix: hw.scanner.suffix,
                    scanner_min_speed_ms: hw.scanner.min_speed_ms,
                    scanner_auto_submit: hw.scanner.auto_submit
                  })
                }
                className="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-500 disabled:opacity-50 transition-colors"
              >
                Guardar Scanner
              </button>
            </div>
          </Card>
        )}

        {/* DRAWER SECTION */}
        {section === 'drawer' && (
          <Card title="Cajon de Dinero">
            <div className="flex gap-2 mb-4">
              <button onClick={handleTestDrawer} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 text-sm font-medium hover:bg-zinc-700 disabled:opacity-50 transition-colors">
                <DoorOpen className="w-4 h-4" />
                Probar Cajon
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Toggle
                label="Cajon habilitado"
                checked={hw.drawer.enabled}
                onChange={(v) => setHw({ ...hw, drawer: { ...hw.drawer, enabled: v } })}
              />
              <Field label="Impresora del cajon">
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2 px-3 text-sm focus:border-blue-500 focus:outline-none transition-all"
                  value={hw.drawer.printer_name}
                  onChange={(e) =>
                    setHw({ ...hw, drawer: { ...hw.drawer, printer_name: e.target.value } })
                  }
                />
              </Field>
              <Toggle
                label="Abrir con pago en efectivo"
                checked={hw.drawer.auto_open_cash}
                onChange={(v) => setHw({ ...hw, drawer: { ...hw.drawer, auto_open_cash: v } })}
              />
              <Toggle
                label="Abrir con pago en tarjeta"
                checked={hw.drawer.auto_open_card}
                onChange={(v) => setHw({ ...hw, drawer: { ...hw.drawer, auto_open_card: v } })}
              />
              <Toggle
                label="Abrir con transferencia"
                checked={hw.drawer.auto_open_transfer}
                onChange={(v) =>
                  setHw({ ...hw, drawer: { ...hw.drawer, auto_open_transfer: v } })
                }
              />
            </div>
            <div className="mt-4">
              <button
                disabled={busy}
                onClick={() =>
                  handleSave('drawer', {
                    cash_drawer_enabled: hw.drawer.enabled,
                    printer_name: hw.drawer.printer_name,
                    cash_drawer_auto_open_cash: hw.drawer.auto_open_cash,
                    cash_drawer_auto_open_card: hw.drawer.auto_open_card,
                    cash_drawer_auto_open_transfer: hw.drawer.auto_open_transfer
                  })
                }
                className="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-500 disabled:opacity-50 transition-colors"
              >
                Guardar Cajon
              </button>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reusable sub-components
// ---------------------------------------------------------------------------

function Card({ title, children }: { title: string; children: React.ReactNode }): ReactElement {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <h2 className="text-lg font-bold mb-4 text-zinc-200">{title}</h2>
      {children}
    </div>
  )
}

function Field({
  label,
  children,
  full
}: {
  label: string
  children: React.ReactNode
  full?: boolean
}): ReactElement {
  return (
    <label className={`block ${full ? 'md:col-span-2' : ''}`}>
      <span className="text-xs text-zinc-400 mb-1 block">{label}</span>
      {children}
    </label>
  )
}

function Toggle({
  label,
  checked,
  onChange
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}): ReactElement {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none py-1">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors ${
          checked ? 'bg-blue-600' : 'bg-zinc-700'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
      <span className="text-sm text-zinc-300">{label}</span>
    </label>
  )
}
