import type { ReactElement } from 'react'
import { useRef, useState } from 'react'
import TopNavbar from './components/TopNavbar'
import {
  loadRuntimeConfig,
  getUserRole,
  generateCFDI,
  generateGlobalCFDI,
  processReturn,
  getReturnsSummary,
  parseXML,
  runAudit,
  getShadowAuditView,
  getShadowRealView,
  getShadowDiscrepancy,
  reconcileShadow,
  createGhostTransfer,
  receiveGhostTransfer,
  getPendingGhostTransfers,
  getFederationOperational,
  getFederationFiscal,
  createGhostWallet,
  addWalletPoints,
  redeemWalletPoints,
  getWalletStats,
  getExtractionAvailable,
  createExtractionPlan,
  getOptimalExtraction,
  getCryptoAvailable,
  convertCrypto,
  getCryptoWealth,
  supplierAnalyze,
  verifyStealthPin,
  configureStealthPins,
  surgicalDelete,
  triggerPanic,
  triggerFakeScreen,
  runShaper
} from './posApi'

type SubTab =
  | 'facturacion'
  | 'inventario'
  | 'logistica'
  | 'federation'
  | 'auditoria'
  | 'wallet'
  | 'crypto'
  | 'seguridad'

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const inputCls =
  'w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal'
const btnPrimary =
  'flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50'
const btnSecondary =
  'flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50'
const btnDanger =
  'flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 transition-all disabled:opacity-50'
const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1'

export default function FiscalTab(): ReactElement {
  const [tab, setTab] = useState<SubTab>('facturacion')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Panel fiscal: facturacion, auditoria y operaciones avanzadas.')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const role = getUserRole()
  const canAdmin = role === 'owner' || role === 'admin'
  const fileRef = useRef<HTMLInputElement>(null)

  // --- Facturacion state ---
  const [cfdiSaleId, setCfdiSaleId] = useState('')
  const [cfdiRfc, setCfdiRfc] = useState('')
  const [cfdiName, setCfdiName] = useState('')
  const [cfdiRegimen, setCfdiRegimen] = useState('')
  const [cfdiUso, setCfdiUso] = useState('G03')
  const [cfdiFormaPago, setCfdiFormaPago] = useState('01')
  const [cfdiZip, setCfdiZip] = useState('')
  const [globalPeriod, setGlobalPeriod] = useState('daily')
  const [globalDate, setGlobalDate] = useState(new Date().toISOString().slice(0, 10))
  const [retSaleId, setRetSaleId] = useState('')
  const [retItems, setRetItems] = useState('')
  const [retReason, setRetReason] = useState('')
  const [retBy, setRetBy] = useState('')

  // --- Shadow inventory state ---
  const [reconProductId, setReconProductId] = useState('')
  const [reconFiscalStock, setReconFiscalStock] = useState('')

  // --- Logistica state ---
  const [ghostOrigin, setGhostOrigin] = useState('')
  const [ghostDest, setGhostDest] = useState('')
  const [ghostItems, setGhostItems] = useState('')
  const [ghostUserId, setGhostUserId] = useState('')
  const [ghostNotes, setGhostNotes] = useState('')
  const [recvCode, setRecvCode] = useState('')
  const [recvUserId, setRecvUserId] = useState('')
  const [ghostBranch, setGhostBranch] = useState('')

  // --- Auditoria state ---
  const [supProductId, setSupProductId] = useState('')
  const [supQty, setSupQty] = useState('')
  const [supPriceA, setSupPriceA] = useState('')
  const [supPriceB, setSupPriceB] = useState('')

  // --- Wallet state ---
  const [walletSeed, setWalletSeed] = useState('')
  const [wpHashId, setWpHashId] = useState('')
  const [wpSaleAmount, setWpSaleAmount] = useState('')
  const [wrHashId, setWrHashId] = useState('')
  const [wrAmount, setWrAmount] = useState('')
  const [extTarget, setExtTarget] = useState('')

  // --- Crypto state ---
  const [cryptoAmount, setCryptoAmount] = useState('')
  const [cryptoCoin, setCryptoCoin] = useState('USDT')
  const [cryptoWallet, setCryptoWallet] = useState('')
  const [cryptoCover, setCryptoCover] = useState('')

  // --- Seguridad state ---
  const [stealthPin, setStealthPin] = useState('')
  const [confNormal, setConfNormal] = useState('')
  const [confDuress, setConfDuress] = useState('')
  const [confWipe, setConfWipe] = useState('')
  const [sdSaleIds, setSdSaleIds] = useState('')
  const [sdConfirm, setSdConfirm] = useState('')
  const [fakeType, setFakeType] = useState('maintenance')

  async function wrap(fn: () => Promise<Record<string, unknown>>): Promise<void> {
    setBusy(true)
    setResult(null)
    try {
      const data = await fn()
      setResult(data)
      setMessage('Operacion completada.')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const cfg = (): ReturnType<typeof loadRuntimeConfig> => loadRuntimeConfig()

  const tabs: { key: SubTab; label: string }[] = [
    { key: 'facturacion', label: 'Facturacion' },
    { key: 'inventario', label: 'Inv. Fiscal' },
    { key: 'logistica', label: 'Logistica' },
    { key: 'federation', label: 'Federation' },
    { key: 'auditoria', label: 'Auditoria' },
    { key: 'wallet', label: 'Wallet' },
    { key: 'crypto', label: 'Crypto' },
    { key: 'seguridad', label: 'Seguridad' }
  ]

  function renderFacturacion(): ReactElement {
    return (
      <div className="space-y-6">
        {/* CFDI Individual */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">CFDI Individual</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input className={inputCls} placeholder="Sale ID" value={cfdiSaleId} onChange={(e) => setCfdiSaleId(e.target.value)} />
            <input className={inputCls} placeholder="RFC Cliente" maxLength={13} value={cfdiRfc} onChange={(e) => setCfdiRfc(e.target.value.toUpperCase())} />
            <input className={inputCls} placeholder="Nombre Cliente" maxLength={300} value={cfdiName} onChange={(e) => setCfdiName(e.target.value)} />
            <input className={inputCls} placeholder="Regimen Fiscal" value={cfdiRegimen} onChange={(e) => setCfdiRegimen(e.target.value)} />
            <input className={inputCls} placeholder="Uso CFDI (G03)" value={cfdiUso} onChange={(e) => setCfdiUso(e.target.value)} />
            <input className={inputCls} placeholder="Forma Pago (01)" value={cfdiFormaPago} onChange={(e) => setCfdiFormaPago(e.target.value)} />
            <input className={inputCls} placeholder="Codigo Postal" maxLength={5} value={cfdiZip} onChange={(e) => setCfdiZip(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !cfdiSaleId.trim()}
              onClick={() => void wrap(() => generateCFDI(cfg(), {
                sale_id: cfdiSaleId.trim(),
                customer_rfc: cfdiRfc.trim(),
                customer_name: cfdiName.trim(),
                regimen: cfdiRegimen.trim(),
                uso_cfdi: cfdiUso.trim(),
                forma_pago: cfdiFormaPago.trim(),
                zip: cfdiZip.trim()
              }))}
            >
              Generar CFDI
            </button>
          </div>
        </div>

        {/* CFDI Global */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">CFDI Global</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <select className={inputCls} value={globalPeriod} onChange={(e) => setGlobalPeriod(e.target.value)}>
              <option value="daily">Diario</option>
              <option value="weekly">Semanal</option>
              <option value="monthly">Mensual</option>
            </select>
            <input className={inputCls} type="date" value={globalDate} onChange={(e) => setGlobalDate(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy}
              onClick={() => void wrap(() => generateGlobalCFDI(cfg(), { period_type: globalPeriod, date: globalDate }))}
            >
              Generar Global
            </button>
          </div>
        </div>

        {/* Devoluciones */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Devolucion</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input className={inputCls} placeholder="Sale ID" value={retSaleId} onChange={(e) => setRetSaleId(e.target.value)} />
            <input className={inputCls} placeholder='Items JSON [{"sku":"X","qty":1}]' value={retItems} onChange={(e) => setRetItems(e.target.value)} />
            <input className={inputCls} placeholder="Razon" value={retReason} onChange={(e) => setRetReason(e.target.value)} />
            <input className={inputCls} placeholder="Procesado por" value={retBy} onChange={(e) => setRetBy(e.target.value)} />
          </div>
          <div className="flex gap-2 mt-2">
            <button
              className={btnPrimary}
              disabled={busy || !retSaleId.trim()}
              onClick={() => {
                let items: unknown[] = []
                try { const parsed = JSON.parse(retItems); if (Array.isArray(parsed)) items = parsed } catch { /* empty */ }
                void wrap(() => processReturn(cfg(), {
                  sale_id: retSaleId.trim(),
                  items,
                  reason: retReason.trim(),
                  processed_by: retBy.trim()
                }))
              }}
            >
              Procesar Devolucion
            </button>
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() => void wrap(() => getReturnsSummary(cfg()))}
            >
              Resumen Devoluciones
            </button>
          </div>
        </div>

        {/* XML Upload */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Parsear XML</h3>
          <div className="flex gap-2">
            <input ref={fileRef} type="file" accept=".xml" className={inputCls} />
            <button
              className={btnPrimary}
              disabled={busy}
              onClick={() => {
                const file = fileRef.current?.files?.[0]
                if (!file) { setMessage('Selecciona un archivo XML.'); return }
                void wrap(() => parseXML(cfg(), file))
              }}
            >
              Parsear
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderInventarioFiscal(): ReactElement {
    return (
      <div className="space-y-4">
        <div className="flex gap-2 flex-wrap">
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getShadowAuditView(cfg()))}>
            Vista SAT
          </button>
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getShadowRealView(cfg()))}>
            Vista Real
          </button>
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getShadowDiscrepancy(cfg()))}>
            Discrepancias
          </button>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Reconciliar</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input className={inputCls} placeholder="Product ID" value={reconProductId} onChange={(e) => setReconProductId(e.target.value)} />
            <input className={inputCls} placeholder="Stock Fiscal" type="number" value={reconFiscalStock} onChange={(e) => setReconFiscalStock(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !reconProductId.trim()}
              onClick={() => void wrap(() => reconcileShadow(cfg(), {
                product_id: Number(reconProductId.trim()),
                fiscal_stock: toNumber(reconFiscalStock)
              }))}
            >
              Reconciliar
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderLogistica(): ReactElement {
    return (
      <div className="space-y-6">
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Crear Transferencia</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input className={inputCls} placeholder="Origen" value={ghostOrigin} onChange={(e) => setGhostOrigin(e.target.value)} />
            <input className={inputCls} placeholder="Destino" value={ghostDest} onChange={(e) => setGhostDest(e.target.value)} />
            <input className={inputCls} placeholder='Items JSON [{"sku":"X","qty":1}]' value={ghostItems} onChange={(e) => setGhostItems(e.target.value)} />
            <input className={inputCls} placeholder="User ID" value={ghostUserId} onChange={(e) => setGhostUserId(e.target.value)} />
            <input className={inputCls} placeholder="Notas" value={ghostNotes} onChange={(e) => setGhostNotes(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !ghostOrigin.trim()}
              onClick={() => {
                let items: unknown[] = []
                try { items = JSON.parse(ghostItems) } catch { /* empty */ }
                void wrap(() => createGhostTransfer(cfg(), {
                  origin: ghostOrigin.trim(),
                  destination: ghostDest.trim(),
                  items,
                  user_id: ghostUserId.trim(),
                  notes: ghostNotes.trim()
                }))
              }}
            >
              Crear
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Recibir Transferencia</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input className={inputCls} placeholder="Codigo Transferencia" value={recvCode} onChange={(e) => setRecvCode(e.target.value)} />
            <input className={inputCls} placeholder="User ID" value={recvUserId} onChange={(e) => setRecvUserId(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !recvCode.trim()}
              onClick={() => void wrap(() => receiveGhostTransfer(cfg(), {
                transfer_code: recvCode.trim(),
                user_id: Number(recvUserId.trim())
              }))}
            >
              Recibir
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Transferencias Pendientes</h3>
          <div className="flex gap-2">
            <input className={inputCls} placeholder="Sucursal (opcional)" value={ghostBranch} onChange={(e) => setGhostBranch(e.target.value)} />
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() => void wrap(() => getPendingGhostTransfers(cfg(), ghostBranch.trim() || undefined))}
            >
              Cargar
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderFederation(): ReactElement {
    return (
      <div className="space-y-4">
        <div className="flex gap-2 flex-wrap">
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getFederationOperational(cfg()))}>
            Dashboard Operacional
          </button>
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getFederationFiscal(cfg()))}>
            Inteligencia Fiscal
          </button>
        </div>
        {!canAdmin && (
          <p className="text-xs text-zinc-500">Acciones de lockdown/release solo para admin/owner.</p>
        )}
      </div>
    )
  }

  function renderAuditoria(): ReactElement {
    return (
      <div className="space-y-6">
        <div className="flex gap-2 flex-wrap">
          <button className={btnPrimary} disabled={busy || !canAdmin} onClick={() => void wrap(() => runAudit(cfg()))}>
            Ejecutar Auditoria
          </button>
          <button className={btnSecondary} disabled={busy || !canAdmin} onClick={() => void wrap(() => runShaper(cfg()))}>
            Ejecutar Shaper
          </button>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Analisis Proveedor</h3>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
            <input className={inputCls} placeholder="Product ID" value={supProductId} onChange={(e) => setSupProductId(e.target.value)} />
            <input className={inputCls} placeholder="Cantidad" type="number" value={supQty} onChange={(e) => setSupQty(e.target.value)} />
            <input className={inputCls} placeholder="Precio A" type="number" value={supPriceA} onChange={(e) => setSupPriceA(e.target.value)} />
            <input className={inputCls} placeholder="Precio B" type="number" value={supPriceB} onChange={(e) => setSupPriceB(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !supProductId.trim()}
              onClick={() => void wrap(() => supplierAnalyze(cfg(), {
                product_id: supProductId.trim(),
                quantity: toNumber(supQty),
                price_a: toNumber(supPriceA),
                price_b: toNumber(supPriceB)
              }))}
            >
              Analizar
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderWallet(): ReactElement {
    return (
      <div className="space-y-6">
        {/* Wallet */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Ghost Wallet</h3>
          <div className="flex gap-2 mb-3">
            <input className={inputCls} placeholder="Seed (opcional)" value={walletSeed} onChange={(e) => setWalletSeed(e.target.value)} />
            <button className={btnPrimary} disabled={busy} onClick={() => void wrap(() => createGhostWallet(cfg(), walletSeed.trim() || undefined))}>
              Crear Wallet
            </button>
            <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getWalletStats(cfg()))}>
              Stats
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
            <input className={inputCls} placeholder="Hash ID" value={wpHashId} onChange={(e) => setWpHashId(e.target.value)} />
            <input className={inputCls} placeholder="Sale Amount" type="number" value={wpSaleAmount} onChange={(e) => setWpSaleAmount(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !wpHashId.trim()}
              onClick={() => void wrap(() => addWalletPoints(cfg(), {
                hash_id: wpHashId.trim(),
                sale_amount: toNumber(wpSaleAmount)
              }))}
            >
              Agregar Puntos
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input className={inputCls} placeholder="Hash ID" value={wrHashId} onChange={(e) => setWrHashId(e.target.value)} />
            <input className={inputCls} placeholder="Monto a redimir" type="number" value={wrAmount} onChange={(e) => setWrAmount(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !wrHashId.trim()}
              onClick={() => void wrap(() => redeemWalletPoints(cfg(), {
                hash_id: wrHashId.trim(),
                amount: toNumber(wrAmount)
              }))}
            >
              Redimir
            </button>
          </div>
        </div>

        {/* Extraccion */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Extraccion</h3>
          <div className="flex gap-2 mb-3 flex-wrap">
            <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getExtractionAvailable(cfg()))}>
              Disponible
            </button>
            <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getOptimalExtraction(cfg()))}>
              Optimo
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input className={inputCls} placeholder="Monto objetivo" type="number" value={extTarget} onChange={(e) => setExtTarget(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !extTarget.trim()}
              onClick={() => void wrap(() => createExtractionPlan(cfg(), { target_amount: toNumber(extTarget) }))}
            >
              Crear Plan
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderCrypto(): ReactElement {
    return (
      <div className="space-y-6">
        <div className="flex gap-2 flex-wrap">
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getCryptoAvailable(cfg()))}>
            Fondos Disponibles
          </button>
          <button className={btnSecondary} disabled={busy} onClick={() => void wrap(() => getCryptoWealth(cfg()))}>
            Wealth Total
          </button>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Conversion</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input className={inputCls} placeholder="Monto MXN" type="number" value={cryptoAmount} onChange={(e) => setCryptoAmount(e.target.value)} />
            <select className={inputCls} value={cryptoCoin} onChange={(e) => setCryptoCoin(e.target.value)}>
              <option value="USDT">USDT</option>
              <option value="USDC">USDC</option>
              <option value="DAI">DAI</option>
            </select>
            <input className={inputCls} placeholder="Wallet Address" value={cryptoWallet} onChange={(e) => setCryptoWallet(e.target.value)} />
            <input className={inputCls} placeholder="Descripcion cobertura" value={cryptoCover} onChange={(e) => setCryptoCover(e.target.value)} />
          </div>
          <button
            className={`${btnPrimary} mt-2`}
            disabled={busy || !cryptoAmount.trim()}
            onClick={() => {
              if (!window.confirm('¿Confirmar conversion crypto? Esta operacion es irreversible.')) return
              void wrap(() => convertCrypto(cfg(), {
                amount_mxn: toNumber(cryptoAmount),
                stablecoin: cryptoCoin,
                wallet_address: cryptoWallet.trim(),
                cover_description: cryptoCover.trim()
              }))
            }}
          >
            Convertir
          </button>
        </div>
      </div>
    )
  }

  function renderSeguridad(): ReactElement {
    return (
      <div className="space-y-6">
        {!canAdmin && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
            Acceso restringido. Solo admin/owner puede ejecutar operaciones de seguridad.
          </div>
        )}

        {/* Stealth PIN */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Stealth PIN</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
            <input className={inputCls} placeholder="PIN" type="password" value={stealthPin} onChange={(e) => setStealthPin(e.target.value)} />
            <button
              className={btnPrimary}
              disabled={busy || !stealthPin.trim() || !canAdmin}
              onClick={() => void wrap(() => verifyStealthPin(cfg(), { pin: stealthPin.trim() }))}
            >
              Verificar PIN
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input className={inputCls} placeholder="PIN Normal" type="password" value={confNormal} onChange={(e) => setConfNormal(e.target.value)} />
            <input className={inputCls} placeholder="PIN Duress" type="password" value={confDuress} onChange={(e) => setConfDuress(e.target.value)} />
            <input className={inputCls} placeholder="PIN Wipe" type="password" value={confWipe} onChange={(e) => setConfWipe(e.target.value)} />
            <button
              className={btnDanger}
              disabled={busy || !canAdmin}
              onClick={() => {
                if (!window.confirm('¿Reconfigurar PINs de seguridad?')) return
                void wrap(() => configureStealthPins(cfg(), {
                  normal_pin: confNormal.trim(),
                  duress_pin: confDuress.trim(),
                  wipe_pin: confWipe.trim()
                }))
              }}
            >
              Configurar PINs
            </button>
          </div>
        </div>

        {/* Surgical Delete */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-rose-400">Eliminacion Quirurgica</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input className={inputCls} placeholder="Sale IDs (comma separated)" value={sdSaleIds} onChange={(e) => setSdSaleIds(e.target.value)} />
            <input className={inputCls} placeholder="Frase de confirmacion" value={sdConfirm} onChange={(e) => setSdConfirm(e.target.value)} />
            <button
              className={btnDanger}
              disabled={busy || !sdSaleIds.trim() || !sdConfirm.trim() || !canAdmin}
              onClick={() => {
                if (!window.confirm('ADVERTENCIA: Esta accion elimina ventas permanentemente. ¿Continuar?')) return
                if (!window.confirm('SEGUNDA CONFIRMACION: ¿Estas absolutamente seguro?')) return
                const ids = sdSaleIds.split(',').map((s) => s.trim()).filter(Boolean)
                void wrap(() => surgicalDelete(cfg(), { sale_ids: ids, confirm_phrase: sdConfirm.trim() }))
              }}
            >
              Eliminar
            </button>
          </div>
        </div>

        {/* Evasion */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-rose-400">Evasion</h3>
          <div className="flex gap-2 flex-wrap">
            <button
              className={btnDanger}
              disabled={busy || !canAdmin}
              onClick={() => {
                if (!window.confirm('PANIC: ¿Activar modo de emergencia?')) return
                if (!window.confirm('CONFIRMAR PANIC: Esta accion es irreversible.')) return
                void wrap(() => triggerPanic(cfg(), { immediate: true }))
              }}
            >
              PANIC
            </button>
            <select className={inputCls + ' max-w-[200px]'} value={fakeType} onChange={(e) => setFakeType(e.target.value)}>
              <option value="maintenance">Mantenimiento</option>
              <option value="update">Actualizacion</option>
              <option value="error">Error</option>
            </select>
            <button
              className={btnDanger}
              disabled={busy || !canAdmin}
              onClick={() => {
                if (!window.confirm('¿Activar pantalla falsa?')) return
                void wrap(() => triggerFakeScreen(cfg(), { screen_type: fakeType }))
              }}
            >
              Fake Screen
            </button>
          </div>
        </div>
      </div>
    )
  }

  const tabRenderers: Record<SubTab, () => ReactElement> = {
    facturacion: renderFacturacion,
    inventario: renderInventarioFiscal,
    logistica: renderLogistica,
    federation: renderFederation,
    auditoria: renderAuditoria,
    wallet: renderWallet,
    crypto: renderCrypto,
    seguridad: renderSeguridad
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      <TopNavbar />

      {/* Sub-tab bar */}
      <div className="flex items-center gap-1 border-b border-zinc-800 bg-zinc-900 p-2 overflow-x-auto shrink-0">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`px-4 py-2 rounded font-medium text-sm transition-colors ${
              tab === t.key
                ? 'bg-zinc-800 shadow-sm border border-zinc-700 font-bold text-blue-400'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
            }`}
            onClick={() => { setTab(t.key); setResult(null) }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {tabRenderers[tab]()}

        {/* Result viewer */}
        {result && (
          <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="flex items-center justify-between mb-2">
              <p className={labelCls}>Resultado</p>
              <button className="text-xs text-zinc-500 hover:text-zinc-300" onClick={() => setResult(null)}>
                Cerrar
              </button>
            </div>
            <pre className="max-h-80 overflow-auto rounded border border-zinc-800 bg-zinc-950 p-3 text-xs font-mono text-zinc-300">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
