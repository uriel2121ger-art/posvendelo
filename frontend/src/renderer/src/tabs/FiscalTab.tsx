import type { ReactElement } from 'react'
import { useRef, useState } from 'react'
import { useConfirm } from '../components/ConfirmDialog'
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
  getShadowDualStock,
  shadowAdd,
  shadowSell,
  createGhostTransfer,
  receiveGhostTransfer,
  getPendingGhostTransfers,
  getGhostTransferSlip,
  getFederationOperational,
  getFederationFiscal,
  getFederationWealth,
  federationLockdown,
  federationRelease,
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
  triggerDeadDrive,
  runShaper
} from '../posApi'
import FiscalDashboardPanel from './fiscal/FiscalDashboardPanel'
import FiscalCostosPanel from './fiscal/FiscalCostosPanel'
import FiscalExtraccionesPanel from './fiscal/FiscalExtraccionesPanel'
import FiscalDocumentosPanel from './fiscal/FiscalDocumentosPanel'
import FiscalAnalyticsPanel from './fiscal/FiscalAnalyticsPanel'
import FiscalOperacionesPanel from './fiscal/FiscalOperacionesPanel'

type SubTab =
  | 'facturacion'
  | 'dashboard'
  | 'inventario'
  | 'costos'
  | 'logistica'
  | 'federation'
  | 'extracciones'
  | 'documentos'
  | 'auditoria'
  | 'analytics'
  | 'wallet'
  | 'crypto'
  | 'operaciones'
  | 'seguridad'

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const inputCls =
  'w-full rounded-lg border border-zinc-800 bg-zinc-900/80 py-2 px-3 text-sm font-medium text-zinc-200 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition placeholder:text-zinc-600'
const btnPrimary =
  'flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-bold text-sm text-white hover:bg-blue-500 transition disabled:opacity-50'
const btnSecondary =
  'flex items-center justify-center gap-2 rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-2 font-bold text-sm text-zinc-300 hover:bg-zinc-700 hover:text-white transition disabled:opacity-50'
const btnDanger =
  'flex items-center justify-center gap-2 rounded-lg bg-rose-500/20 border border-rose-500/40 px-4 py-2 font-bold text-sm text-rose-400 hover:bg-rose-500/30 transition disabled:opacity-50'
const cardCls = 'rounded-xl border border-zinc-800 bg-zinc-900/50 p-4'
const labelCls = 'text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2'

export default function FiscalTab(): ReactElement {
  const confirm = useConfirm()
  const [tab, setTab] = useState<SubTab>('facturacion')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(
    'Panel fiscal: facturacion, auditoria y operaciones avanzadas.'
  )
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
  const [slipCode, setSlipCode] = useState('')
  const [dualProductId, setDualProductId] = useState('')
  const [shadowAddProductId, setShadowAddProductId] = useState('')
  const [shadowAddQty, setShadowAddQty] = useState('')
  const [shadowAddSource, setShadowAddSource] = useState('')
  const [shadowSellProductId, setShadowSellProductId] = useState('')
  const [shadowSellQty, setShadowSellQty] = useState('')
  const [shadowSellSerie, setShadowSellSerie] = useState('B')
  const [lockdownBranchId, setLockdownBranchId] = useState('')
  const [releaseBranchId, setReleaseBranchId] = useState('')
  const [releaseAuthCode, setReleaseAuthCode] = useState('')
  const [deadDriveDevice, setDeadDriveDevice] = useState('')
  const [deadDriveConfirm, setDeadDriveConfirm] = useState('')

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
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'inventario', label: 'Inv. Fiscal' },
    { key: 'costos', label: 'Costos' },
    { key: 'logistica', label: 'Logistica' },
    { key: 'federation', label: 'Federation' },
    { key: 'extracciones', label: 'Extracciones' },
    { key: 'documentos', label: 'Documentos' },
    { key: 'auditoria', label: 'Auditoria' },
    { key: 'analytics', label: 'Analytics' },
    { key: 'wallet', label: 'Wallet' },
    { key: 'crypto', label: 'Crypto' },
    { key: 'operaciones', label: 'Operaciones' },
    { key: 'seguridad', label: 'Seguridad' }
  ]

  function renderFacturacion(): ReactElement {
    return (
      <div className="space-y-6">
        {/* CFDI Individual */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">CFDI Individual</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              className={inputCls}
              placeholder="Sale ID"
              value={cfdiSaleId}
              onChange={(e) => setCfdiSaleId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="RFC Cliente"
              maxLength={13}
              value={cfdiRfc}
              onChange={(e) => setCfdiRfc(e.target.value.toUpperCase())}
            />
            <input
              className={inputCls}
              placeholder="Nombre Cliente"
              maxLength={300}
              value={cfdiName}
              onChange={(e) => setCfdiName(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Regimen Fiscal"
              value={cfdiRegimen}
              onChange={(e) => setCfdiRegimen(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Uso CFDI (G03)"
              value={cfdiUso}
              onChange={(e) => setCfdiUso(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Forma Pago (01)"
              value={cfdiFormaPago}
              onChange={(e) => setCfdiFormaPago(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Codigo Postal"
              maxLength={5}
              value={cfdiZip}
              onChange={(e) => setCfdiZip(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !cfdiSaleId.trim()}
              onClick={async () => {
                setBusy(true)
                setResult(null)
                try {
                  const data = await generateCFDI(cfg(), {
                    sale_id: cfdiSaleId.trim(),
                    customer_rfc: cfdiRfc.trim(),
                    customer_name: cfdiName.trim(),
                    customer_regime: cfdiRegimen.trim(),
                    uso_cfdi: cfdiUso.trim(),
                    forma_pago: cfdiFormaPago.trim(),
                    customer_zip: cfdiZip.trim()
                  })
                  setResult(data)
                  setMessage(
                    data.success
                      ? `CFDI Timbrado Exitosamente. UUID: ${(data.data as Record<string, unknown>)?.uuid ?? 'Generado'}`
                      : 'CFDI Generado pero sin confirmacion UUID.'
                  )
                } catch (error) {
                  setMessage(`Error CFDI: ${(error as Error).message}`)
                } finally {
                  setBusy(false)
                }
              }}
            >
              Generar CFDI
            </button>
          </div>
        </div>

        {/* CFDI Global */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">CFDI Global</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <select
              className={inputCls}
              value={globalPeriod}
              onChange={(e) => setGlobalPeriod(e.target.value)}
            >
              <option value="daily">Diario</option>
              <option value="weekly">Semanal</option>
              <option value="monthly">Mensual</option>
            </select>
            <input
              className={inputCls}
              type="date"
              value={globalDate}
              onChange={(e) => setGlobalDate(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                setResult(null)
                try {
                  const data = await generateGlobalCFDI(cfg(), {
                    period_type: globalPeriod,
                    date: globalDate
                  })
                  setResult(data)
                  setMessage(
                    data.success
                      ? `CFDI Global Timbrado. UUID: ${(data.data as Record<string, unknown>)?.uuid ?? 'Generado'}`
                      : 'CFDI Global Generado sin confirmacion UUID.'
                  )
                } catch (error) {
                  setMessage(`Error CFDI Global: ${(error as Error).message}`)
                } finally {
                  setBusy(false)
                }
              }}
            >
              Generar Global
            </button>
          </div>
        </div>

        {/* Devoluciones */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Devolucion</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              className={inputCls}
              placeholder="Sale ID"
              value={retSaleId}
              onChange={(e) => setRetSaleId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder='Items JSON [{"sku":"X","qty":1}]'
              value={retItems}
              onChange={(e) => setRetItems(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Razon"
              value={retReason}
              onChange={(e) => setRetReason(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Procesado por"
              value={retBy}
              onChange={(e) => setRetBy(e.target.value)}
            />
          </div>
          <div className="flex gap-2 mt-2">
            <button
              className={btnPrimary}
              disabled={busy || !retSaleId.trim()}
              onClick={() => {
                let items: unknown[] = []
                try {
                  const parsed = JSON.parse(retItems)
                  if (Array.isArray(parsed)) items = parsed
                } catch {
                  /* empty */
                }
                void wrap(() =>
                  processReturn(cfg(), {
                    sale_id: retSaleId.trim(),
                    items,
                    reason: retReason.trim(),
                    processed_by: retBy.trim()
                  })
                )
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
                if (!file) {
                  setMessage('Selecciona un archivo XML.')
                  return
                }
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
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getShadowAuditView(cfg()))}
          >
            Vista SAT
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getShadowRealView(cfg()))}
          >
            Vista Real
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getShadowDiscrepancy(cfg()))}
          >
            Discrepancias
          </button>
          <input
            className={inputCls + ' max-w-[100px]'}
            placeholder="Product ID"
            type="number"
            value={dualProductId}
            onChange={(e) => setDualProductId(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !dualProductId.trim()}
            onClick={() => void wrap(() => getShadowDualStock(cfg(), toNumber(dualProductId)))}
          >
            Stock dual
          </button>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Shadow add</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              className={inputCls}
              placeholder="Product ID"
              type="number"
              value={shadowAddProductId}
              onChange={(e) => setShadowAddProductId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Cantidad"
              type="number"
              value={shadowAddQty}
              onChange={(e) => setShadowAddQty(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Origen (opcional)"
              value={shadowAddSource}
              onChange={(e) => setShadowAddSource(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !shadowAddProductId.trim()}
              onClick={() =>
                void wrap(() =>
                  shadowAdd(cfg(), {
                    product_id: toNumber(shadowAddProductId),
                    quantity: toNumber(shadowAddQty),
                    source: shadowAddSource.trim() || undefined
                  })
                )
              }
            >
              Agregar shadow
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Shadow sell</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              className={inputCls}
              placeholder="Product ID"
              type="number"
              value={shadowSellProductId}
              onChange={(e) => setShadowSellProductId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Cantidad"
              type="number"
              value={shadowSellQty}
              onChange={(e) => setShadowSellQty(e.target.value)}
            />
            <select
              className={inputCls + ' max-w-[80px]'}
              value={shadowSellSerie}
              onChange={(e) => setShadowSellSerie(e.target.value)}
            >
              <option value="A">A</option>
              <option value="B">B</option>
            </select>
            <button
              className={btnPrimary}
              disabled={busy || !shadowSellProductId.trim()}
              onClick={() =>
                void wrap(() =>
                  shadowSell(cfg(), {
                    product_id: toNumber(shadowSellProductId),
                    quantity: toNumber(shadowSellQty),
                    serie: shadowSellSerie
                  })
                )
              }
            >
              Venta shadow
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Reconciliar</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              className={inputCls}
              placeholder="Product ID"
              value={reconProductId}
              onChange={(e) => setReconProductId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Stock Fiscal"
              type="number"
              value={reconFiscalStock}
              onChange={(e) => setReconFiscalStock(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !reconProductId.trim()}
              onClick={() =>
                void wrap(() =>
                  reconcileShadow(cfg(), {
                    product_id: Number(reconProductId.trim()),
                    fiscal_stock: toNumber(reconFiscalStock)
                  })
                )
              }
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
            <input
              className={inputCls}
              placeholder="Origen"
              value={ghostOrigin}
              onChange={(e) => setGhostOrigin(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Destino"
              value={ghostDest}
              onChange={(e) => setGhostDest(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder='Items JSON [{"sku":"X","qty":1}]'
              value={ghostItems}
              onChange={(e) => setGhostItems(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="User ID"
              value={ghostUserId}
              onChange={(e) => setGhostUserId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Notas"
              value={ghostNotes}
              onChange={(e) => setGhostNotes(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !ghostOrigin.trim()}
              onClick={() => {
                let items: unknown[] = []
                try {
                  items = JSON.parse(ghostItems)
                } catch {
                  /* empty */
                }
                void wrap(() =>
                  createGhostTransfer(cfg(), {
                    origin: ghostOrigin.trim(),
                    destination: ghostDest.trim(),
                    items,
                    user_id: ghostUserId.trim(),
                    notes: ghostNotes.trim()
                  })
                )
              }}
            >
              Crear
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Recibir Transferencia</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              className={inputCls}
              placeholder="Codigo Transferencia"
              value={recvCode}
              onChange={(e) => setRecvCode(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="User ID"
              value={recvUserId}
              onChange={(e) => setRecvUserId(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !recvCode.trim()}
              onClick={() =>
                void wrap(() =>
                  receiveGhostTransfer(cfg(), {
                    transfer_code: recvCode.trim(),
                    user_id: Number(recvUserId.trim())
                  })
                )
              }
            >
              Recibir
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Transferencias Pendientes</h3>
          <div className="flex gap-2">
            <input
              className={inputCls}
              placeholder="Sucursal (opcional)"
              value={ghostBranch}
              onChange={(e) => setGhostBranch(e.target.value)}
            />
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() =>
                void wrap(() => getPendingGhostTransfers(cfg(), ghostBranch.trim() || undefined))
              }
            >
              Cargar
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Remisión / Slip</h3>
          <div className="flex gap-2">
            <input
              className={inputCls}
              placeholder="Código transferencia"
              value={slipCode}
              onChange={(e) => setSlipCode(e.target.value)}
            />
            <button
              className={btnSecondary}
              disabled={busy || !slipCode.trim()}
              onClick={() => void wrap(() => getGhostTransferSlip(cfg(), slipCode.trim()))}
            >
              Obtener remisión
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
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getFederationOperational(cfg()))}
          >
            Dashboard Operacional
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getFederationFiscal(cfg()))}
          >
            Inteligencia Fiscal
          </button>
          {canAdmin && (
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() => void wrap(() => getFederationWealth(cfg()))}
            >
              Wealth
            </button>
          )}
        </div>
        {canAdmin && (
          <div className={cardCls}>
            <h3 className="text-sm font-semibold mb-3 text-zinc-400">Lockdown / Release</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <input
                className={inputCls}
                type="number"
                placeholder="Branch ID (lockdown)"
                value={lockdownBranchId}
                onChange={(e) => setLockdownBranchId(e.target.value)}
              />
              <button
                className={btnDanger}
                disabled={busy || !lockdownBranchId.trim()}
                onClick={() =>
                  void wrap(() =>
                    federationLockdown(cfg(), { branch_id: toNumber(lockdownBranchId) })
                  )
                }
              >
                Lockdown
              </button>
              <input
                className={inputCls}
                type="number"
                placeholder="Branch ID (release)"
                value={releaseBranchId}
                onChange={(e) => setReleaseBranchId(e.target.value)}
              />
              <input
                className={inputCls}
                placeholder="Código auth"
                value={releaseAuthCode}
                onChange={(e) => setReleaseAuthCode(e.target.value)}
              />
              <button
                className={btnPrimary}
                disabled={busy || !releaseBranchId.trim() || !releaseAuthCode.trim()}
                onClick={() =>
                  void wrap(() =>
                    federationRelease(cfg(), {
                      branch_id: toNumber(releaseBranchId),
                      auth_code: releaseAuthCode.trim()
                    })
                  )
                }
              >
                Release
              </button>
            </div>
          </div>
        )}
        {!canAdmin && (
          <p className="text-xs text-zinc-500">
            Acciones de lockdown/release solo para admin/owner.
          </p>
        )}
      </div>
    )
  }

  function renderAuditoria(): ReactElement {
    return (
      <div className="space-y-6">
        <div className="flex gap-2 flex-wrap">
          <button
            className={btnPrimary}
            disabled={busy || !canAdmin}
            onClick={() => void wrap(() => runAudit(cfg()))}
          >
            Ejecutar Auditoria
          </button>
          <button
            className={btnSecondary}
            disabled={busy || !canAdmin}
            onClick={() => void wrap(() => runShaper(cfg()))}
          >
            Ejecutar Shaper
          </button>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Analisis Proveedor</h3>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
            <input
              className={inputCls}
              placeholder="Product ID"
              value={supProductId}
              onChange={(e) => setSupProductId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Cantidad"
              type="number"
              value={supQty}
              onChange={(e) => setSupQty(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Precio A"
              type="number"
              value={supPriceA}
              onChange={(e) => setSupPriceA(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Precio B"
              type="number"
              value={supPriceB}
              onChange={(e) => setSupPriceB(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !supProductId.trim()}
              onClick={() =>
                void wrap(() =>
                  supplierAnalyze(cfg(), {
                    product_id: supProductId.trim(),
                    quantity: toNumber(supQty),
                    price_a: toNumber(supPriceA),
                    price_b: toNumber(supPriceB)
                  })
                )
              }
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
            <input
              className={inputCls}
              placeholder="Seed (opcional)"
              value={walletSeed}
              onChange={(e) => setWalletSeed(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy}
              onClick={() =>
                void wrap(() => createGhostWallet(cfg(), walletSeed.trim() || undefined))
              }
            >
              Crear Wallet
            </button>
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() => void wrap(() => getWalletStats(cfg()))}
            >
              Stats
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
            <input
              className={inputCls}
              placeholder="Hash ID"
              value={wpHashId}
              onChange={(e) => setWpHashId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Sale Amount"
              type="number"
              value={wpSaleAmount}
              onChange={(e) => setWpSaleAmount(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !wpHashId.trim()}
              onClick={() =>
                void wrap(() =>
                  addWalletPoints(cfg(), {
                    hash_id: wpHashId.trim(),
                    sale_amount: toNumber(wpSaleAmount)
                  })
                )
              }
            >
              Agregar Puntos
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              className={inputCls}
              placeholder="Hash ID"
              value={wrHashId}
              onChange={(e) => setWrHashId(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Monto a redimir"
              type="number"
              value={wrAmount}
              onChange={(e) => setWrAmount(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !wrHashId.trim()}
              onClick={() =>
                void wrap(() =>
                  redeemWalletPoints(cfg(), {
                    hash_id: wrHashId.trim(),
                    amount: toNumber(wrAmount)
                  })
                )
              }
            >
              Redimir
            </button>
          </div>
        </div>

        {/* Extraccion */}
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Extraccion</h3>
          <div className="flex gap-2 mb-3 flex-wrap">
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() => void wrap(() => getExtractionAvailable(cfg()))}
            >
              Disponible
            </button>
            <button
              className={btnSecondary}
              disabled={busy}
              onClick={() => void wrap(() => getOptimalExtraction(cfg()))}
            >
              Optimo
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              className={inputCls}
              placeholder="Monto objetivo"
              type="number"
              value={extTarget}
              onChange={(e) => setExtTarget(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !extTarget.trim()}
              onClick={() =>
                void wrap(() => createExtractionPlan(cfg(), { target_amount: toNumber(extTarget) }))
              }
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
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getCryptoAvailable(cfg()))}
          >
            Fondos Disponibles
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getCryptoWealth(cfg()))}
          >
            Wealth Total
          </button>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-zinc-400">Conversion</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              className={inputCls}
              placeholder="Monto MXN"
              type="number"
              value={cryptoAmount}
              onChange={(e) => setCryptoAmount(e.target.value)}
            />
            <select
              className={inputCls}
              value={cryptoCoin}
              onChange={(e) => setCryptoCoin(e.target.value)}
            >
              <option value="USDT">USDT</option>
              <option value="USDC">USDC</option>
              <option value="DAI">DAI</option>
            </select>
            <input
              className={inputCls}
              placeholder="Wallet Address"
              value={cryptoWallet}
              onChange={(e) => setCryptoWallet(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Descripcion cobertura"
              value={cryptoCover}
              onChange={(e) => setCryptoCover(e.target.value)}
            />
          </div>
          <button
            className={`${btnPrimary} mt-2`}
            disabled={busy || !cryptoAmount.trim()}
            onClick={async () => {
              if (
                !(await confirm('¿Confirmar conversion crypto? Esta operacion es irreversible.', {
                  variant: 'danger',
                  title: 'Conversion crypto'
                }))
              )
                return
              void wrap(() =>
                convertCrypto(cfg(), {
                  amount_mxn: toNumber(cryptoAmount),
                  stablecoin: cryptoCoin,
                  wallet_address: cryptoWallet.trim(),
                  cover_description: cryptoCover.trim()
                })
              )
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
            <input
              className={inputCls}
              placeholder="PIN"
              type="password"
              value={stealthPin}
              onChange={(e) => setStealthPin(e.target.value)}
            />
            <button
              className={btnPrimary}
              disabled={busy || !stealthPin.trim() || !canAdmin}
              onClick={() => void wrap(() => verifyStealthPin(cfg(), { pin: stealthPin.trim() }))}
            >
              Verificar PIN
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <input
              className={inputCls}
              placeholder="PIN Normal"
              type="password"
              value={confNormal}
              onChange={(e) => setConfNormal(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="PIN Duress"
              type="password"
              value={confDuress}
              onChange={(e) => setConfDuress(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="PIN Wipe"
              type="password"
              value={confWipe}
              onChange={(e) => setConfWipe(e.target.value)}
            />
            <button
              className={btnDanger}
              disabled={busy || !canAdmin}
              onClick={async () => {
                if (
                  !(await confirm('¿Reconfigurar PINs de seguridad?', {
                    variant: 'danger',
                    title: 'Reconfigurar PINs'
                  }))
                )
                  return
                void wrap(() =>
                  configureStealthPins(cfg(), {
                    normal_pin: confNormal.trim(),
                    duress_pin: confDuress.trim(),
                    wipe_pin: confWipe.trim()
                  })
                )
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
            <input
              className={inputCls}
              placeholder="Sale IDs (comma separated)"
              value={sdSaleIds}
              onChange={(e) => setSdSaleIds(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Frase de confirmacion"
              value={sdConfirm}
              onChange={(e) => setSdConfirm(e.target.value)}
            />
            <button
              className={btnDanger}
              disabled={busy || !sdSaleIds.trim() || !sdConfirm.trim() || !canAdmin}
              onClick={async () => {
                if (
                  !(await confirm(
                    'ADVERTENCIA: Esta accion elimina ventas permanentemente. ¿Continuar?',
                    { variant: 'danger', title: 'Eliminacion quirurgica' }
                  ))
                )
                  return
                if (
                  !(await confirm('SEGUNDA CONFIRMACION: ¿Estas absolutamente seguro?', {
                    variant: 'danger',
                    title: 'Confirmar eliminacion'
                  }))
                )
                  return
                const ids = sdSaleIds
                  .split(',')
                  .map((s) => parseInt(s.trim(), 10))
                  .filter((n) => !Number.isNaN(n))
                void wrap(() =>
                  surgicalDelete(cfg(), { sale_ids: ids, confirm_phrase: sdConfirm.trim() })
                )
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
              onClick={async () => {
                if (
                  !(await confirm('PANIC: ¿Activar modo de emergencia?', {
                    variant: 'danger',
                    title: 'PANIC'
                  }))
                )
                  return
                if (
                  !(await confirm('CONFIRMAR PANIC: Esta accion es irreversible.', {
                    variant: 'danger',
                    title: 'Confirmar PANIC'
                  }))
                )
                  return
                void wrap(() => triggerPanic(cfg(), { immediate: true }))
              }}
            >
              PANIC
            </button>
            <select
              className={inputCls + ' max-w-[200px]'}
              value={fakeType}
              onChange={(e) => setFakeType(e.target.value)}
            >
              <option value="maintenance">Mantenimiento</option>
              <option value="update">Actualizacion</option>
              <option value="error">Error</option>
            </select>
            <button
              className={btnDanger}
              disabled={busy || !canAdmin}
              onClick={async () => {
                if (
                  !(await confirm('¿Activar pantalla falsa?', {
                    variant: 'danger',
                    title: 'Pantalla falsa'
                  }))
                )
                  return
                void wrap(() => triggerFakeScreen(cfg(), { screen_type: fakeType }))
              }}
            >
              Fake Screen
            </button>
          </div>
        </div>
        <div className={cardCls}>
          <h3 className="text-sm font-semibold mb-3 text-rose-400">Dead drive</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              className={inputCls}
              placeholder="Dispositivo"
              value={deadDriveDevice}
              onChange={(e) => setDeadDriveDevice(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="Frase confirmación"
              value={deadDriveConfirm}
              onChange={(e) => setDeadDriveConfirm(e.target.value)}
            />
            <button
              className={btnDanger}
              disabled={busy || !deadDriveDevice.trim() || !deadDriveConfirm.trim() || !canAdmin}
              onClick={async () => {
                if (
                  !(await confirm('¿Ejecutar dead-drive? Esta acción es irreversible.', {
                    variant: 'danger',
                    title: 'Dead drive'
                  }))
                )
                  return
                void wrap(() =>
                  triggerDeadDrive(cfg(), {
                    device: deadDriveDevice.trim(),
                    confirm: deadDriveConfirm.trim()
                  })
                )
              }}
            >
              Dead drive
            </button>
          </div>
        </div>
      </div>
    )
  }

  function renderDashboard(): ReactElement {
    return <FiscalDashboardPanel cfg={cfg} busy={busy} wrap={wrap} canAdmin={canAdmin} />
  }

  function renderCostos(): ReactElement {
    return <FiscalCostosPanel cfg={cfg} busy={busy} wrap={wrap} canAdmin={canAdmin} />
  }

  function renderExtracciones(): ReactElement {
    return <FiscalExtraccionesPanel cfg={cfg} busy={busy} wrap={wrap} canAdmin={canAdmin} />
  }

  function renderDocumentos(): ReactElement {
    return <FiscalDocumentosPanel cfg={cfg} busy={busy} wrap={wrap} canAdmin={canAdmin} />
  }

  function renderAnalytics(): ReactElement {
    return <FiscalAnalyticsPanel cfg={cfg} busy={busy} wrap={wrap} canAdmin={canAdmin} />
  }

  function renderOperaciones(): ReactElement {
    return <FiscalOperacionesPanel cfg={cfg} busy={busy} wrap={wrap} canAdmin={canAdmin} />
  }

  const tabRenderers: Record<SubTab, () => ReactElement> = {
    facturacion: renderFacturacion,
    dashboard: renderDashboard,
    inventario: renderInventarioFiscal,
    costos: renderCostos,
    logistica: renderLogistica,
    federation: renderFederation,
    extracciones: renderExtracciones,
    documentos: renderDocumentos,
    auditoria: renderAuditoria,
    analytics: renderAnalytics,
    wallet: renderWallet,
    crypto: renderCrypto,
    operaciones: renderOperaciones,
    seguridad: renderSeguridad
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      {/* Sub-tab bar — mismo estilo que TopNavbar */}
      <div className="flex items-center gap-1 border-b border-zinc-900 bg-zinc-950 px-3 py-2 overflow-x-auto shrink-0 hide-scrollbar">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap shrink-0 ${
              tab === t.key
                ? 'bg-blue-600/10 text-blue-400 shadow-[inset_0_-2px_0_0_rgb(59,130,246)]'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'
            }`}
            onClick={() => {
              setTab(t.key)
              setResult(null)
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content — ancho contenido como Terminal/Clientes */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full p-4 lg:p-6 space-y-6">
          {tabRenderers[tab]()}

          {/* Result viewer */}
          {result && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <p className={labelCls}>Resultado</p>
                <button
                  type="button"
                  className="text-[11px] font-semibold text-zinc-500 hover:text-zinc-300 uppercase tracking-wider transition"
                  onClick={() => setResult(null)}
                >
                  Cerrar
                </button>
              </div>
              <pre className="max-h-72 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-[11px] font-mono text-zinc-300 leading-relaxed">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>

      {/* Barra de mensaje — mismo criterio que pie de Terminal */}
      <div className="shrink-0 border-t border-zinc-900 bg-zinc-950/80 px-4 py-2.5 text-[11px] text-zinc-400">
        {message}
      </div>
    </div>
  )
}
