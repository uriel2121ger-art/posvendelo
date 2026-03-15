import type { ReactElement } from 'react'
import { flushSync } from 'react-dom'

import { useConfirm, usePrompt } from '../components/ConfirmDialog'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Plus,
  Search as SearchIcon,
  ShoppingCart as ShoppingCartIcon,
  CheckCircle2,
  Users,
  X as XIcon,
  Banknote,
  CreditCard,
  FileText,
  Landmark,
  Tag,
  Ticket,
  Wallet
} from 'lucide-react'
import {
  type RuntimeConfig,
  type SaleItemPayload,
  loadRuntimeConfig,
  loadHwConfigFromCache,
  pullTable,
  createSale,
  printReceipt,
  openDrawerForSale,
  getTurnSummary,
  searchSatCodes
} from '../posApi'

import { useFocusTrap } from '../hooks/useFocusTrap'
import { toNumber } from '../utils/numbers'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  priceWholesale?: number
  stock?: number
  minStock?: number
  satClaveProdServ?: string
  satClaveUnidad?: string
}

type CartItem = {
  id?: number | string
  sku: string
  name: string
  price: number
  priceWholesale?: number
  stock?: number
  qty: number
  discountPct: number
  isCommon?: boolean
  commonNote?: string
  satClaveProdServ?: string
  satClaveUnidad?: string
  subtotal: number
}

type PaymentMethod = 'cash' | 'card' | 'transfer' | 'mixed'

type PendingTicket = {
  id: string
  label: string
  customerName: string
  customerId: number | null
  paymentMethod: PaymentMethod
  globalDiscountPct: number
  cart: CartItem[]
  wholesaleMode?: boolean
}

type ActiveTicketMeta = {
  id: string
  label: string
}

type ActiveTicketSnapshot = {
  customerName: string
  customerId: number | null
  paymentMethod: PaymentMethod
  globalDiscountPct: number
  cart: CartItem[]
  selectedCartSku: string | null
  amountReceived: string
  requiereFactura?: boolean
  paymentReference?: string
  mixedCash?: string
  mixedCard?: string
  mixedTransfer?: string
}

const TAX_RATE = 0.16
const PENDING_TICKETS_STORAGE_KEY = 'pos.pendingTickets'
import {
  type ShiftRecord as ShiftState,
  isShiftStorageKey,
  saveCurrentShift,
  readCurrentShift
} from '../types/shiftTypes'
const ACTIVE_TICKETS_STORAGE_KEY = 'pos.activeTickets'
const PRODUCT_CACHE_STORAGE_KEY = 'pos.productsCache'

/** Sufijo por usuario para que los borradores persistan entre sesiones y no se mezclen entre usuarios. */
function getDraftsSuffix(): string {
  try {
    const u = localStorage.getItem('pos.user')
    return u ? `.${u}` : ''
  } catch {
    return ''
  }
}

function getPendingStorageKey(): string {
  return PENDING_TICKETS_STORAGE_KEY + getDraftsSuffix()
}

function getActiveStorageKey(): string {
  return ACTIVE_TICKETS_STORAGE_KEY + getDraftsSuffix()
}

function getProductCacheKey(): string {
  return PRODUCT_CACHE_STORAGE_KEY + getDraftsSuffix()
}

function clampDiscount(value: number): number {
  return Math.max(0, Math.min(100, value))
}

type SavedActiveState = {
  activeTickets: ActiveTicketMeta[]
  activeTicketId: string
  ticketSnapshots: Record<string, ActiveTicketSnapshot>
  ticketCounter: number
}

function createEmptyTicketSnapshot(): ActiveTicketSnapshot {
  return {
    customerName: 'Público General',
    customerId: null,
    paymentMethod: 'cash',
    globalDiscountPct: 0,
    cart: [],
    selectedCartSku: null,
    amountReceived: '',
    requiereFactura: false,
    paymentReference: '',
    mixedCash: '',
    mixedCard: '',
    mixedTransfer: ''
  }
}

function readSavedActiveState(): SavedActiveState | null {
  try {
    const key = getActiveStorageKey()
    let raw = localStorage.getItem(key)
    // Migración: si hay usuario y su clave está vacía, intentar clave global (datos anteriores al cambio)
    if (!raw && getDraftsSuffix()) {
      raw = localStorage.getItem(ACTIVE_TICKETS_STORAGE_KEY)
      if (raw) {
        try {
          localStorage.setItem(key, raw)
          localStorage.removeItem(ACTIVE_TICKETS_STORAGE_KEY)
        } catch {
          /* quota o sin acceso */
        }
      }
    }
    if (!raw) return null
    const parsed = JSON.parse(raw) as SavedActiveState
    if (!parsed || !Array.isArray(parsed.activeTickets) || !parsed.activeTicketId) return null
    return parsed
  } catch {
    return null
  }
}

function readSavedPendingTickets(): PendingTicket[] {
  try {
    const key = getPendingStorageKey()
    let raw = localStorage.getItem(key)
    // Migración: si hay usuario y su clave está vacía, intentar clave global (datos anteriores al cambio)
    if (!raw && getDraftsSuffix()) {
      raw = localStorage.getItem(PENDING_TICKETS_STORAGE_KEY)
      if (raw) {
        try {
          localStorage.setItem(key, raw)
          localStorage.removeItem(PENDING_TICKETS_STORAGE_KEY)
        } catch {
          /* quota o sin acceso */
        }
      }
    }
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    const valid = parsed.filter(
      (t): t is PendingTicket =>
        t != null &&
        typeof (t as PendingTicket).id === 'string' &&
        typeof (t as PendingTicket).label === 'string' &&
        Array.isArray((t as PendingTicket).cart)
    )
    return valid
  } catch {
    return []
  }
}

function calculateLineSubtotal(price: number, qty: number, discountPct: number): number {
  const safeQty = Math.max(1, Math.floor(qty))
  const safeDiscount = clampDiscount(discountPct)
  return Math.round(price * safeQty * (1 - safeDiscount / 100) * 100) / 100
}

function normalizeProduct(raw: Record<string, unknown>): Product | null {
  const sku = String(raw.sku ?? raw.code ?? raw.codigo ?? '').trim()
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!sku || !name) return null
  const priceFields = [raw.price, raw.sale_price, raw.precio, raw.cost]
  const price = toNumber(priceFields.find((v) => v != null && toNumber(v) > 0) ?? 0)
  const priceWholesale = toNumber(raw.price_wholesale ?? raw.priceWholesale ?? 0)
  return {
    id: (raw.id as number | string | undefined) ?? sku,
    sku,
    name,
    price,
    priceWholesale: priceWholesale > 0 ? priceWholesale : undefined,
    stock: toNumber(raw.stock),
    satClaveProdServ: String(raw.sat_clave_prod_serv ?? '').trim() || undefined,
    satClaveUnidad: String(raw.sat_clave_unidad ?? '').trim() || undefined
  }
}

async function fetchProducts(cfg: RuntimeConfig): Promise<Product[]> {
  const raw = await pullTable('products', cfg)
  return raw.map(normalizeProduct).filter((item): item is Product => item !== null)
}

function readCachedProducts(): Product[] {
  try {
    const raw =
      localStorage.getItem(getProductCacheKey()) ?? localStorage.getItem(PRODUCT_CACHE_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((item): item is Record<string, unknown> => item != null && typeof item === 'object')
      .map(normalizeProduct)
      .filter((item): item is Product => item !== null)
  } catch {
    return []
  }
}

function writeCachedProducts(products: Product[]): void {
  try {
    localStorage.setItem(getProductCacheKey(), JSON.stringify(products))
    localStorage.setItem(PRODUCT_CACHE_STORAGE_KEY, JSON.stringify(products))
  } catch {
    /* quota o sin acceso */
  }
}

type MixedAmounts = { cash: number; card: number; transfer: number }

async function syncSale(
  cfg: RuntimeConfig,
  cart: CartItem[],
  _customerName: string,
  paymentMethod: PaymentMethod,
  globalDiscountPct: number,
  amountReceived?: number,
  turnId?: number | null,
  isWholesale?: boolean,
  customerId?: number | null,
  requiereFactura?: boolean,
  mixedAmounts?: MixedAmounts,
  paymentRef?: string
): Promise<Record<string, unknown>> {
  const globalDisc = clampDiscount(globalDiscountPct) / 100
  const items: SaleItemPayload[] = cart.map((item) => {
    // Compound discount: matches how the frontend display calculates totals
    // item.subtotal already has per-item discount applied (price * qty * (1 - itemDisc/100))
    // Then global discount is applied on top: item.subtotal * (1 - globalDisc)
    const fullPrice = Math.round(item.price * item.qty * 100) / 100
    const compoundSubtotal = Math.round(item.subtotal * (1 - globalDisc) * 100) / 100
    const discount = Math.round(Math.max(0, fullPrice - compoundSubtotal) * 100) / 100
    return {
      product_id: item.isCommon ? null : Number(item.id) > 0 ? Number(item.id) : null,
      name: item.name,
      qty: item.qty,
      price: item.price,
      discount,
      is_wholesale: isWholesale ?? false,
      price_includes_tax: true,
      sat_clave_prod_serv: item.satClaveProdServ || (item.isCommon ? '01010101' : undefined),
      sat_clave_unidad: item.satClaveUnidad || (item.isCommon ? 'H87' : undefined)
    }
  })
  // Serie A: factura individual, pago bancarizado (tarjeta/transferencia/mixto).
  // Serie B: efectivo y cliente no pidió factura (público en general).
  const serie: 'A' | 'B' =
    paymentMethod === 'card' ||
    paymentMethod === 'transfer' ||
    paymentMethod === 'mixed' ||
    (requiereFactura ?? false)
      ? 'A'
      : 'B'

  const payload: Parameters<typeof createSale>[1] = {
    items,
    payment_method: paymentMethod,
    customer_id: customerId ?? undefined,
    serie,
    turn_id: turnId ?? undefined,
    requiere_factura: requiereFactura ?? false
  }
  if (paymentMethod === 'cash') {
    payload.cash_received = amountReceived ?? 0
  }
  if (paymentMethod === 'card' && paymentRef != null) {
    payload.card_reference = paymentRef.trim() || undefined
  }
  if (paymentMethod === 'transfer' && paymentRef != null) {
    payload.transfer_reference = paymentRef.trim() || undefined
  }
  if (paymentMethod === 'mixed' && mixedAmounts) {
    payload.mixed_cash = mixedAmounts.cash
    payload.mixed_card = mixedAmounts.card
    payload.mixed_transfer = mixedAmounts.transfer
    payload.mixed_wallet = 0
    payload.mixed_gift_card = 0
  }

  const res = await createSale(cfg, payload)
  const data = (res.data ?? res) as Record<string, unknown>
  return data
}

/* ── Common Product Modal (single form instead of 5 sequential prompts) ── */

type CommonProductResult = {
  name: string
  price: number
  qty: number
  note: string
  satCode: string
  satClaveUnidad: string
}

function CommonProductModal({
  defaultQty,
  onSubmit,
  onClose
}: {
  defaultQty: number
  onSubmit: (result: CommonProductResult) => void
  onClose: () => void
}): ReactElement {
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [cQty, setCQty] = useState(String(Math.max(1, defaultQty)))
  const [note, setNote] = useState('')
  const [satCode, setSatCode] = useState('01010101')
  const [satQuery, setSatQuery] = useState('')
  const [satResults, setSatResults] = useState<{ code: string; description: string }[]>([])
  const [showSatDrop, setShowSatDrop] = useState(false)
  const [error, setError] = useState('')
  const nameRef = useRef<HTMLInputElement>(null)
  const modalRef = useRef<HTMLFormElement>(null)
  const satTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useFocusTrap(modalRef, true)
  useEffect(() => { nameRef.current?.focus() }, [])
  useEffect(() => {
    const onEsc = (e: KeyboardEvent): void => { if (e.key === 'Escape') { e.preventDefault(); onClose() } }
    window.addEventListener('keydown', onEsc, true)
    return () => window.removeEventListener('keydown', onEsc, true)
  }, [onClose])

  const handleSatSearch = (q: string): void => {
    setSatQuery(q)
    if (satTimer.current) clearTimeout(satTimer.current)
    if (q.trim().length >= 2) {
      satTimer.current = setTimeout(() => {
        void (async () => {
          try {
            const cfg = loadRuntimeConfig()
            if (!cfg.token) return
            const results = await searchSatCodes(cfg, q.trim())
            setSatResults(results)
            setShowSatDrop(results.length > 0)
          } catch {
            setSatResults([])
          }
        })()
      }, 300)
    } else {
      setSatResults([])
      setShowSatDrop(false)
    }
  }

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault()
    const trimName = name.trim()
    if (!trimName) { setError('Ingresa un nombre.'); return }
    const numPrice = Number(price)
    if (!Number.isFinite(numPrice) || numPrice <= 0) { setError('Ingresa un precio válido.'); return }
    const numQty = Math.max(1, Math.floor(Number(cQty)))
    if (!Number.isFinite(numQty) || numQty <= 0) { setError('Ingresa una cantidad válida.'); return }
    onSubmit({ name: trimName, price: numPrice, qty: numQty, note: note.trim(), satCode, satClaveUnidad: 'H87' })
  }

  const inputCls = 'w-full bg-zinc-950 border border-zinc-700 rounded-lg py-2.5 px-3 text-sm font-semibold focus:border-blue-500 focus:outline-none'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <form ref={modalRef} onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl">
        <h2 className="text-lg font-bold text-blue-400 mb-4 flex items-center gap-2">
          Producto común
          <kbd className="ml-auto rounded bg-zinc-800 border border-zinc-700 px-2 py-0.5 font-mono text-xs text-zinc-400">
            Ctrl+P
          </kbd>
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">Nombre</label>
            <input ref={nameRef} className={inputCls} value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Servicio de reparación" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">Precio</label>
              <input className={inputCls} type="number" min={0.01} step="0.01" value={price}
                onChange={(e) => setPrice(e.target.value)} placeholder="$0.00" />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">Cantidad</label>
              <input className={inputCls} type="number" min={1} step="1" value={cQty}
                onChange={(e) => setCQty(e.target.value)} placeholder="1" />
            </div>
          </div>
          <div className="relative">
            <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">Clave SAT</label>
            <input className={inputCls} value={satQuery} placeholder="Buscar: bebidas, cremas, 50161800..."
              onChange={(e) => handleSatSearch(e.target.value)}
              onFocus={() => { if (satResults.length > 0) setShowSatDrop(true) }}
              onBlur={() => { setTimeout(() => setShowSatDrop(false), 200) }} />
            {satCode && satCode !== '01010101' && (
              <span className="absolute right-3 top-7 text-xs text-blue-400 font-mono">{satCode}</span>
            )}
            {showSatDrop && satResults.length > 0 && (
              <div className="absolute z-50 w-full mt-1 bg-zinc-900 border border-zinc-700 rounded-xl max-h-36 overflow-y-auto shadow-xl">
                {satResults.map((r) => (
                  <button key={r.code} type="button"
                    onClick={() => { setSatCode(r.code); setSatQuery(`${r.code} - ${r.description}`); setShowSatDrop(false) }}
                    className="w-full text-left px-3 py-2 hover:bg-zinc-800 text-sm transition-colors border-b border-zinc-800 last:border-0">
                    <span className="font-mono text-blue-400">{r.code}</span>
                    <span className="text-zinc-400 ml-2">{r.description}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1">Nota (opcional)</label>
            <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="Descripción adicional..." />
          </div>
        </div>
        {error && <p className="text-rose-400 text-sm mt-2">{error}</p>}
        <div className="flex gap-3 mt-4">
          <button type="button" onClick={onClose}
            className="flex-1 rounded-xl border border-zinc-700 bg-zinc-800 py-2.5 font-bold text-zinc-300 hover:bg-zinc-700 transition-colors">
            Cancelar
          </button>
          <button type="submit"
            className="flex-1 rounded-xl bg-blue-600 py-2.5 font-bold text-white hover:bg-blue-500 transition-colors">
            Agregar
          </button>
        </div>
      </form>
    </div>
  )
}

export default function Terminal(): ReactElement {
  const confirm = useConfirm()
  const prompt = usePrompt()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const lastKeystrokeRef = useRef<number>(Date.now())
  const lastEnterRef = useRef<number>(0)
  const suppressSearchChangeUntilRef = useRef<number>(0)
  const lastSubmittedSearchRef = useRef<string>('')
  const [config] = useState(() => loadRuntimeConfig())
  const [products, setProducts] = useState<Product[]>(() => readCachedProducts())
  // Restore active ticket state from localStorage (navigation persistence)
  const [_savedActive] = useState(() => readSavedActiveState())
  const _snap = _savedActive?.ticketSnapshots?.[_savedActive?.activeTicketId ?? '']
  const [cart, setCart] = useState<CartItem[]>(_snap?.cart ?? [])
  const [customerName, setCustomerName] = useState(_snap?.customerName ?? 'Público General')
  const [customerId, setCustomerId] = useState<number | null>(_snap?.customerId ?? null)
  const [customerPickerOpen, setCustomerPickerOpen] = useState(false)
  const [customerSearch, setCustomerSearch] = useState('')
  const [customerResults, setCustomerResults] = useState<
    Array<{ id: number; name: string; phone?: string }>
  >([])
  const customerPickerRef = useRef<HTMLDivElement | null>(null)
  const customerSearchRef = useRef<HTMLInputElement | null>(null)

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(_snap?.paymentMethod ?? 'cash')
  const [amountReceived, setAmountReceived] = useState(_snap?.amountReceived ?? '')
  const [solicitaFactura, setSolicitaFactura] = useState(_snap?.requiereFactura ?? false)
  const [paymentReference, setPaymentReference] = useState(_snap?.paymentReference ?? '')
  const [mixedCash, setMixedCash] = useState(_snap?.mixedCash ?? '')
  const [mixedCard, setMixedCard] = useState(_snap?.mixedCard ?? '')
  const [mixedTransfer, setMixedTransfer] = useState(_snap?.mixedTransfer ?? '')
  const [globalDiscountPct, setGlobalDiscountPct] = useState(_snap?.globalDiscountPct ?? 0)
  const [pendingTickets, setPendingTickets] = useState<PendingTicket[]>(() =>
    readSavedPendingTickets()
  )
  const [activeTickets, setActiveTickets] = useState<ActiveTicketMeta[]>(
    _savedActive?.activeTickets ?? [{ id: 'active-1', label: 'Activa 1' }]
  )
  const [activeTicketId, setActiveTicketId] = useState(_savedActive?.activeTicketId ?? 'active-1')
  const [ticketSnapshots, setTicketSnapshots] = useState<Record<string, ActiveTicketSnapshot>>(
    _savedActive?.ticketSnapshots ?? {
      'active-1': createEmptyTicketSnapshot()
    }
  )
  const [selectedCartSku, setSelectedCartSku] = useState<string | null>(
    _snap?.selectedCartSku ?? null
  )
  const ticketCounterRef = useRef(_savedActive?.ticketCounter ?? 1)
  const [ticketLabel, setTicketLabel] = useState('')
  const [openNewAfterPending, setOpenNewAfterPending] = useState(false)
  const [qty] = useState(1)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [currentShift, setCurrentShift] = useState<ShiftState | null>(() =>
    readCurrentShift(config.terminalId)
  )
  const [wholesaleMode, setWholesaleMode] = useState(false)
  const [, setMessage] = useState('Cargando productos...')
  const chargingRef = useRef(false)
  const [isCheckoutModalOpen, setIsCheckoutModalOpen] = useState(false)
  const isDiscountModalOpen = false
  const [isCommonModalOpen, setIsCommonModalOpen] = useState(false)
  const isNoteModalOpen = false
  const shouldClearSearchAfterAddRef = useRef(false)

  const checkoutModalRef = useRef<HTMLDivElement>(null)
  useFocusTrap(checkoutModalRef, isCheckoutModalOpen)





  // Click-outside to close customer picker
  useEffect(() => {
    if (!customerPickerOpen) return
    const onClick = (e: MouseEvent): void => {
      if (customerPickerRef.current && !customerPickerRef.current.contains(e.target as Node)) {
        setCustomerPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [customerPickerOpen])

  // Load customers when picker opens
  useEffect(() => {
    if (!customerPickerOpen) return
    let cancelled = false
    pullTable('customers', config)
      .then((raw) => {
        if (cancelled) return
        const mapped = raw
          .filter((c: Record<string, unknown>) => c.is_active !== false && c.is_active !== 0)
          .map((c: Record<string, unknown>) => ({
            id: Number(c.id),
            name: String(c.name ?? '').trim(),
            phone: c.phone ? String(c.phone).trim() : undefined
          }))
          .filter((c) => c.id > 0 && c.name)
        setCustomerResults(mapped)
      })
      .catch(() => {
        if (!cancelled) setCustomerResults([])
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerPickerOpen])

  // Auto-focus search input when picker opens
  useEffect((): void | (() => void) => {
    if (customerPickerOpen) {
      const t = setTimeout(() => customerSearchRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
    setCustomerSearch('')
  }, [customerPickerOpen])

  // Auto-load products on mount + refresh on window focus (fixes stale cache)
  useEffect(() => {
    if (!config.token.trim()) return
    let cancelled = false
    let lastFetch = 0

    function loadProducts(silent?: boolean): void {
      const now = Date.now()
      if (now - lastFetch < 5000) return // throttle: 5s min between fetches
      lastFetch = now
      if (!silent) setBusy(true)
      fetchProducts(config)
        .then((data) => {
          if (cancelled) return
          writeCachedProducts(data)
          setProducts(data)
          if (!silent)
            setMessage(data.length ? `${data.length} productos cargados` : 'Sin productos')
        })
        .catch((err) => {
          if (cancelled) return
          console.warn('[Terminal] Error refrescando productos:', (err as Error).message)
          if (!silent) setMessage((err as Error).message)
        })
        .finally(() => {
          if (!cancelled && !silent) setBusy(false)
        })
    }

    loadProducts()

    // Re-fetch when window regains focus (user returns from Products tab, etc.)
    const onFocus = (): void => {
      loadProducts(true)
    }
    const onVisibility = (): void => {
      if (document.visibilityState === 'visible') loadProducts(true)
    }
    const onProductChange = (): void => {
      loadProducts(true)
    }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pos-products-changed', onProductChange)
    return (): void => {
      cancelled = true
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pos-products-changed', onProductChange)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Recalculate cart prices when wholesale mode toggles
  useEffect(() => {
    setCart((prev) =>
      prev.map((item) => {
        const effectivePrice =
          wholesaleMode && item.priceWholesale
            ? item.priceWholesale
            : (products.find((p) => p.sku === item.sku)?.price ?? item.price)
        if (effectivePrice === item.price) return item
        return {
          ...item,
          price: effectivePrice,
          subtotal: calculateLineSubtotal(effectivePrice, item.qty, item.discountPct)
        }
      })
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wholesaleMode])

  // Los pendientes se cargan en el estado inicial vía readSavedPendingTickets() (clave por usuario).
  // No usar aquí la clave global para no sobrescribir los datos del usuario actual.

  const isFirstPendingPersist = useRef(true)
  useEffect((): void => {
    // Evitar escribir en el primer render; el estado ya viene de readSavedPendingTickets()
    if (isFirstPendingPersist.current) {
      isFirstPendingPersist.current = false
      return
    }
    try {
      localStorage.setItem(getPendingStorageKey(), JSON.stringify(pendingTickets))
    } catch {
      setMessage('Error: no se pudieron guardar tickets pendientes. Almacenamiento lleno.')
    }
  }, [pendingTickets])

  useEffect((): (() => void) => {
    const refreshShift = (): void => setCurrentShift(readCurrentShift(config.terminalId))
    const onStorage = (event: StorageEvent): void => {
      if (isShiftStorageKey(event.key)) refreshShift()
    }
    window.addEventListener('focus', refreshShift)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('focus', refreshShift)
      window.removeEventListener('storage', onStorage)
    }
  }, [config.terminalId])

  // Poll backend every 60s to sync shift counters (multi-terminal visibility)
  useEffect(() => {
    const tid = config.terminalId
    const poll = setInterval(() => {
      const shift = readCurrentShift(tid)
      if (!shift?.backendTurnId) return
      // Use config consistently — not loadRuntimeConfig() which could return a different terminalId
      getTurnSummary(config, shift.backendTurnId)
        .then((raw) => {
          const data = (raw.data ?? raw) as Record<string, unknown>
          const backendCount = Number(data.sales_count ?? 0)
          const backendTotal = Number(data.total_sales ?? 0)
          if (
            backendCount > (shift.salesCount ?? 0) ||
            Math.abs(backendTotal - (shift.totalSales ?? 0)) > 0.01
          ) {
            const updated: ShiftState = {
              ...shift,
              salesCount: backendCount,
              totalSales: Math.round(backendTotal * 100) / 100
            }
            try {
              saveCurrentShift(updated, tid)
            } catch {
              /* storage full */
            }
            setCurrentShift(updated)
          }
        })
        .catch(() => {
          /* network error — skip this cycle */
        })
    }, 60_000)
    return () => clearInterval(poll)
  }, [config])

  const searchableProducts = useMemo(
    (): Product[] => (products.length > 0 ? products : readCachedProducts()),
    [products]
  )

  const filtered = useMemo((): Product[] => {
    const q = query.trim().toLowerCase()
    if (!q) {
      return []
    }
    return searchableProducts
      .filter((p) => p.name.length <= 500)
      .filter((p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q))
      .slice(0, 50)
  }, [query, searchableProducts])

  const totals = useMemo((): {
    subtotalBeforeDiscount: number
    globalDiscountAmount: number
    subtotal: number
    tax: number
    total: number
  } => {
    // Accumulate each line precisely
    const rawSubtotalBeforeDiscount = cart.reduce((acc, item) => acc + item.subtotal, 0)
    // Redondeo final a 2 decimales para la suma de lineas (evita derivas de suma punto flotante repetida)
    const subtotalBeforeDiscount = Math.round(rawSubtotalBeforeDiscount * 100) / 100

    // Calculo del descuento global sobre el acumulado de las lineas
    const globalDiscountAmount =
      Math.round(subtotalBeforeDiscount * (clampDiscount(globalDiscountPct) / 100) * 100) / 100

    // Total con descuento aplicado (IVA ya viene incluido en los precios netos por definicion de este TPV)
    const total = Math.round((subtotalBeforeDiscount - globalDiscountAmount) * 100) / 100

    // Extraccion matematica del IVA desglosado (Total = SubtotalNeto * 1.16)
    // => SubtotalNeto = Total / 1.16
    // => IVA = Total - SubtotalNeto
    const subtotal = Math.round((total / (1 + TAX_RATE)) * 100) / 100
    const tax = Math.round((total - subtotal) * 100) / 100

    return { subtotalBeforeDiscount, globalDiscountAmount, subtotal, tax, total }
  }, [cart, globalDiscountPct])

  // Avisos entre sesiones: productos ya no en catálogo o stock insuficiente (precios ya se actualizan al cargar pendiente)
  const cartWarnings = useMemo((): {
    missingSkus: string[]
    lowStockItems: Array<{ sku: string; name: string; qty: number; currentStock: number }>
  } => {
    const missingSkus: string[] = []
    const lowStockItems: Array<{ sku: string; name: string; qty: number; currentStock: number }> =
      []
    for (const item of cart) {
      if (item.isCommon) continue
      const prod = products.find((p) => p.sku === item.sku)
      if (!prod) {
        missingSkus.push(item.sku)
        continue
      }
      if (typeof prod.stock === 'number' && prod.stock < item.qty) {
        lowStockItems.push({
          sku: item.sku,
          name: item.name,
          qty: item.qty,
          currentStock: prod.stock
        })
      }
    }
    return { missingSkus, lowStockItems }
  }, [cart, products])

  const amountReceivedNum = toNumber(amountReceived)
  const changeDue = Math.max(0, amountReceivedNum - totals.total)
  const pendingAmount = Math.max(0, totals.total - amountReceivedNum)

  const buildCurrentTicketSnapshot = useCallback(
    (): ActiveTicketSnapshot => ({
      customerName,
      customerId,
      paymentMethod,
      globalDiscountPct,
      cart,
      selectedCartSku,
      amountReceived,
      requiereFactura: solicitaFactura,
      paymentReference,
      mixedCash,
      mixedCard,
      mixedTransfer
    }),
    [
      amountReceived,
      cart,
      customerId,
      customerName,
      globalDiscountPct,
      paymentMethod,
      solicitaFactura,
      paymentReference,
      mixedCash,
      mixedCard,
      mixedTransfer,
      selectedCartSku
    ]
  )

  const applyTicketSnapshot = useCallback(
    (snapshot: ActiveTicketSnapshot): void => {
      setCart(snapshot.cart)
      setCustomerName(snapshot.customerName)
      setCustomerId(snapshot.customerId ?? null)
      setPaymentMethod(snapshot.paymentMethod)
      setGlobalDiscountPct(snapshot.globalDiscountPct)
      setSelectedCartSku(snapshot.selectedCartSku)
      setAmountReceived(snapshot.amountReceived)
      setSolicitaFactura(snapshot.requiereFactura ?? false)
      setPaymentReference(snapshot.paymentReference ?? '')
      setMixedCash(snapshot.mixedCash ?? '')
      setMixedCard(snapshot.mixedCard ?? '')
      setMixedTransfer(snapshot.mixedTransfer ?? '')
      setQuery('')
    },
    // setState functions are stable — no deps needed
    []
  )

  const focusSearchInput = useCallback((): void => {
    requestAnimationFrame(() => searchInputRef.current?.focus())
  }, [])

  const clearSearchDomValue = useCallback((): void => {
    if (searchInputRef.current) {
      searchInputRef.current.value = ''
    }
  }, [])

  const clearSearch = useCallback((): void => {
    suppressSearchChangeUntilRef.current = Date.now() + 250
    flushSync(() => {
      setQuery('')
    })
    clearSearchDomValue()
    requestAnimationFrame(() => {
      flushSync(() => {
        setQuery('')
      })
      clearSearchDomValue()
      focusSearchInput()
    })
  }, [clearSearchDomValue, focusSearchInput])

  useEffect(() => {
    if (!shouldClearSearchAfterAddRef.current) return
    shouldClearSearchAfterAddRef.current = false
    flushSync(() => {
      setQuery('')
    })
    clearSearchDomValue()
    focusSearchInput()
  }, [cart, clearSearchDomValue, focusSearchInput])

  const normalizeSearchInput = useCallback((rawValue: string): string => {
    // Strip control chars AND normalize Unicode (prevents Zalgo)
    // eslint-disable-next-line no-control-regex
    const raw = rawValue.replace(/[\x00-\x1F\x7F-\x9F]/g, '')
    return raw
      .normalize('NFC')
      .replace(/[\u0300-\u036f]{3,}/g, '')
      .slice(0, 200)
  }, [])

  const findProductForSearch = useCallback(
    (rawValue: string, now: number): Product | null => {
      const normalizedInput = normalizeSearchInput(rawValue).trim()
      if (!normalizedInput) return null

      let scannerMinSpeed = 50
      let scannerPrefix = ''
      let scannerSuffix = ''
      let isScanner = false
      const hwCfgScan = loadHwConfigFromCache()
      if (hwCfgScan?.scanner?.enabled) {
        scannerMinSpeed = hwCfgScan.scanner.min_speed_ms || 50
        scannerPrefix = hwCfgScan.scanner.prefix || ''
        scannerSuffix = hwCfgScan.scanner.suffix || ''
        const elapsed = now - lastKeystrokeRef.current
        if (elapsed < scannerMinSpeed && normalizedInput.length > 2) {
          isScanner = true
        }
      }

      let searchTerm = normalizedInput
      if (isScanner) {
        if (scannerPrefix && searchTerm.startsWith(scannerPrefix)) {
          searchTerm = searchTerm.slice(scannerPrefix.length)
        }
        if (scannerSuffix && searchTerm.endsWith(scannerSuffix)) {
          searchTerm = searchTerm.slice(0, -scannerSuffix.length)
        }
      }

      const lowered = searchTerm.toLowerCase()
      return (
        searchableProducts.find((p) => p.sku.toLowerCase() === lowered) ??
        searchableProducts.find(
          (p) => p.sku.toLowerCase().includes(lowered) || p.name.toLowerCase().includes(lowered)
        ) ??
        null
      )
    },
    [normalizeSearchInput, searchableProducts]
  )

  // Snapshot current ticket AND persist to localStorage atomically.
  // Previously split into 2 effects with a race condition: if the component
  // unmounted between them (tab navigation), localStorage never got written.
  useEffect((): void => {
    setTicketSnapshots((prev) => {
      const updated = {
        ...prev,
        [activeTicketId]: buildCurrentTicketSnapshot()
      }
      try {
        const state: SavedActiveState = {
          activeTickets,
          activeTicketId,
          ticketSnapshots: updated,
          ticketCounter: ticketCounterRef.current
        }
        localStorage.setItem(getActiveStorageKey(), JSON.stringify(state))
      } catch {
        // storage full or inaccessible — silently ignore
      }
      return updated
    })
  }, [
    activeTicketId,
    amountReceived,
    cart,
    customerId,
    customerName,
    globalDiscountPct,
    paymentMethod,
    buildCurrentTicketSnapshot,
    activeTickets
  ])

  function switchActiveTicket(nextTicketId: string): void {
    if (nextTicketId === activeTicketId) return

    const snapshotsWithCurrent = {
      ...ticketSnapshots,
      [activeTicketId]: buildCurrentTicketSnapshot()
    }
    const nextSnapshot = snapshotsWithCurrent[nextTicketId]
    if (!nextSnapshot) return

    setTicketSnapshots(snapshotsWithCurrent)
    setActiveTicketId(nextTicketId)
    applyTicketSnapshot(nextSnapshot)
    focusSearchInput()
    setMessage(
      `Ticket activo cambiado a: ${activeTickets.find((t) => t.id === nextTicketId)?.label ?? nextTicketId}`
    )
  }

  const createNewActiveTicket = useCallback((): void => {
    if (activeTickets.length >= 8) {
      setMessage('Límite alcanzado: máximo 8 tickets activos.')
      return
    }
    ticketCounterRef.current += 1
    const nextNumber = ticketCounterRef.current
    const nextId = `active-${Date.now()}`
    const nextMeta: ActiveTicketMeta = { id: nextId, label: `Activa ${nextNumber}` }
    const snapshotToPersist = buildCurrentTicketSnapshot()


    const snapshotsWithCurrent = {
      ...ticketSnapshots,
      [activeTicketId]: snapshotToPersist,
      [nextId]: createEmptyTicketSnapshot()
    }

    setActiveTickets((prev) => [...prev, nextMeta].slice(0, 8))
    setTicketSnapshots(snapshotsWithCurrent)
    setActiveTicketId(nextId)
    applyTicketSnapshot(createEmptyTicketSnapshot())
    focusSearchInput()
    setMessage(`Ticket activo creado: ${nextMeta.label}`)
  }, [
    activeTicketId,
    activeTickets,
    applyTicketSnapshot,
    buildCurrentTicketSnapshot,
    focusSearchInput,
    ticketSnapshots
  ])

  async function closeActiveTicket(ticketId: string): Promise<void> {
    if (activeTickets.length <= 1) {
      setMessage('Debe existir al menos un ticket activo.')
      return
    }
    const snapshot = ticketSnapshots[ticketId]
    const ticketCart = ticketId === activeTicketId ? cart : (snapshot?.cart ?? [])
    if (ticketCart.length > 0) {
      if (
        !(await confirm(
          `Este ticket tiene ${ticketCart.length} producto(s). ¿Descartar y cerrar?`,
          { variant: 'warning', title: 'Cerrar ticket' }
        ))
      )
        return
    }

    const remaining = activeTickets.filter((t) => t.id !== ticketId)
    const restSnapshots = Object.fromEntries(
      Object.entries(ticketSnapshots).filter(([id]) => id !== ticketId)
    ) as Record<string, ActiveTicketSnapshot>
    setActiveTickets(remaining)
    setTicketSnapshots(restSnapshots)

    if (ticketId !== activeTicketId) {
      setMessage('Ticket cerrado.')
      return
    }

    const fallback = remaining[0]
    if (!fallback) return
    const fallbackSnap = restSnapshots[fallback.id]
    setActiveTicketId(fallback.id)
    applyTicketSnapshot(fallbackSnap ?? createEmptyTicketSnapshot())
    focusSearchInput()
    setMessage(`Ticket activo cerrado. Cambiado a ${fallback.label}.`)
  }

  const updateItemDiscount = useCallback((sku: string, nextDiscountPct: number): void => {
    const safeDiscount = clampDiscount(nextDiscountPct)
    setCart((prev) =>
      prev.map((item) =>
        item.sku === sku
          ? {
              ...item,
              discountPct: safeDiscount,
              subtotal: calculateLineSubtotal(item.price, item.qty, safeDiscount)
            }
          : item
      )
    )
  }, [])

  const addProduct = useCallback(
    (product: Product): void => {
      const safeQty = Math.max(1, Math.floor(qty))
      const effectivePrice =
        wholesaleMode && product.priceWholesale ? product.priceWholesale : product.price
      setCart((prev) => {
        const _idx = prev.findIndex((item) => item.sku === product.sku)
        if (_idx >= 0) {
          const copy = [...prev]
          const mergedQty = copy[_idx].qty + safeQty
          copy[_idx] = {
            ...copy[_idx],
            price: effectivePrice,
            qty: mergedQty,
            subtotal: calculateLineSubtotal(effectivePrice, mergedQty, copy[_idx].discountPct)
          }
          return copy
        }
        return [
          ...prev,
          {
            ...product,
            price: effectivePrice,
            qty: safeQty,
            discountPct: 0,
            isCommon: false,
            subtotal: calculateLineSubtotal(effectivePrice, safeQty, 0)
          }
        ]
      })
      shouldClearSearchAfterAddRef.current = true
      setSelectedCartSku(product.sku)
      setMessage(`Agregado: ${product.name}`)
    },
    [qty, wholesaleMode]
  )

  const addCommonProduct = useCallback((): void => {
    setIsCommonModalOpen(true)
  }, [])

  const handleCommonProductSubmit = useCallback((result: CommonProductResult): void => {
    const sku = `COMUN-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
    const item: CartItem = {
      sku,
      name: result.name,
      price: result.price,
      qty: result.qty,
      discountPct: 0,
      isCommon: true,
      commonNote: result.note,
      satClaveProdServ: result.satCode,
      satClaveUnidad: result.satClaveUnidad,
      subtotal: calculateLineSubtotal(result.price, result.qty, 0)
    }
    setCart((prev) => [...prev, item])
    setSelectedCartSku(sku)
    setMessage(`Producto común agregado: ${result.name}`)
    setIsCommonModalOpen(false)
  }, [])

  const removeItem = useCallback((sku: string): void => {
    setCart((prev) => prev.filter((item) => item.sku !== sku))
    setSelectedCartSku((current) => (current === sku ? null : current))
  }, [])

  const increaseSelectedQty = useCallback((): void => {
    if (!selectedCartSku) {
      setMessage('Selecciona un producto del carrito.')
      return
    }
    setCart((prev) => {
      const _idx = prev.findIndex((item) => item.sku === selectedCartSku)
      if (_idx < 0) return prev
      const current = prev[_idx]
      const nextQty = current.qty + 1
      const copy = [...prev]
      copy[_idx] = {
        ...current,
        qty: nextQty,
        subtotal: calculateLineSubtotal(current.price, nextQty, current.discountPct)
      }
      return copy
    })
  }, [selectedCartSku])

  const decreaseSelectedQty = useCallback((): void => {
    if (!selectedCartSku) {
      setMessage('Selecciona un producto del carrito.')
      return
    }
    setCart((prev) => {
      const _idx = prev.findIndex((item) => item.sku === selectedCartSku)
      if (_idx < 0) return prev
      const current = prev[_idx]
      const nextQty = Math.max(1, current.qty - 1)
      if (nextQty === current.qty) return prev
      const copy = [...prev]
      copy[_idx] = {
        ...current,
        qty: nextQty,
        subtotal: calculateLineSubtotal(current.price, nextQty, current.discountPct)
      }
      return copy
    })
  }, [selectedCartSku])

  const deleteSelectedItem = useCallback(async (): Promise<void> => {
    if (!selectedCartSku) {
      setMessage('Selecciona un producto del carrito.')
      return
    }
    const item = cart.find((i) => i.sku === selectedCartSku)
    if (
      item &&
      !(await confirm(`¿Quitar "${item.name}" del ticket?`, {
        variant: 'warning',
        title: 'Quitar producto'
      }))
    )
      return
    removeItem(selectedCartSku)
  }, [cart, removeItem, selectedCartSku, confirm])

  const handleCharge = useCallback(async (): Promise<void> => {
    if (chargingRef.current) return
    chargingRef.current = true
    if (!cart.length) {
      setMessage('No hay productos en el ticket.')
      chargingRef.current = false
      return
    }
    if (cartWarnings.missingSkus.length > 0) {
      setMessage(
        'Hay productos marcados como "Ya no en catálogo". Quítalos del ticket (botón ×) antes de cobrar.'
      )
      chargingRef.current = false
      return
    }
    if (cartWarnings.lowStockItems.length > 0) {
      const msg = `Hay ${cartWarnings.lowStockItems.length} producto(s) con stock insuficiente. El servidor puede rechazar la venta. ¿Cobrar de todas formas?`
      if (!(await confirm(msg, { variant: 'warning', title: 'Stock insuficiente' }))) {
        chargingRef.current = false
        return
      }
    }
    const shift = readCurrentShift(config.terminalId)
    if (!shift) {
      setCurrentShift(null)
      setMessage('No hay turno abierto. Abre un turno en la pestaña Turnos antes de cobrar.')
      chargingRef.current = false
      return
    }
    // For cash: if no amount entered, assume exact payment
    const effectiveReceived =
      paymentMethod === 'cash' && amountReceivedNum === 0 ? totals.total : amountReceivedNum
    if (paymentMethod === 'cash' && effectiveReceived < totals.total) {
      setMessage(`Monto insuficiente. Falta: $${(totals.total - effectiveReceived).toFixed(2)}`)
      chargingRef.current = false
      return
    }
    let mixedAmounts: MixedAmounts | undefined
    if (paymentMethod === 'mixed') {
      const mc = toNumber(mixedCash)
      const mcard = toNumber(mixedCard)
      const mt = toNumber(mixedTransfer)
      const sum = mc + mcard + mt
      const tolerance = 0.02
      if (Math.abs(sum - totals.total) > tolerance) {
        setMessage(
          `La suma del desglose ($${sum.toFixed(2)}) debe coincidir con el total ($${totals.total.toFixed(2)}).`
        )
        chargingRef.current = false
        return
      }
      mixedAmounts = { cash: mc, card: mcard, transfer: mt }
    }
    setBusy(true)
    try {
      const turnId = shift.backendTurnId ?? null
      const saleData = await syncSale(
        config,
        cart,
        customerName,
        paymentMethod,
        globalDiscountPct,
        paymentMethod === 'cash' ? effectiveReceived : undefined,
        turnId,
        wholesaleMode,
        customerId,
        solicitaFactura,
        mixedAmounts,
        paymentReference
      )
      const folio = saleData.folio ?? saleData.folio_visible ?? ''
      const rawSaleTotal = Number(saleData.total)
      const saleTotal =
        Number.isFinite(rawSaleTotal) && rawSaleTotal > 0 ? rawSaleTotal : totals.total
      const capturedChange =
        paymentMethod === 'cash' ? Math.max(0, effectiveReceived - saleTotal) : 0
      setCart([])
      setGlobalDiscountPct(0)
      setSelectedCartSku(null)
      setAmountReceived('')
      setSolicitaFactura(false)
      setPaymentReference('')
      setMixedCash('')
      setMixedCard('')
      setMixedTransfer('')
      setCustomerName('Público General')
      setCustomerId(null)
      // Re-read shift from localStorage to avoid stale data after async sale
      const freshShift = readCurrentShift(config.terminalId)
      if (freshShift) {
        const cashDelta =
          paymentMethod === 'cash'
            ? saleTotal
            : paymentMethod === 'mixed' && mixedAmounts
              ? mixedAmounts.cash
              : 0
        const cardDelta =
          paymentMethod === 'card'
            ? saleTotal
            : paymentMethod === 'mixed' && mixedAmounts
              ? mixedAmounts.card
              : 0
        const transferDelta =
          paymentMethod === 'transfer'
            ? saleTotal
            : paymentMethod === 'mixed' && mixedAmounts
              ? mixedAmounts.transfer
              : 0
        const updatedShift: ShiftState = {
          ...freshShift,
          salesCount: (freshShift.salesCount ?? 0) + 1,
          totalSales: Math.round(((freshShift.totalSales ?? 0) + saleTotal) * 100) / 100,
          cashSales: Math.round(((freshShift.cashSales ?? 0) + cashDelta) * 100) / 100,
          cardSales: Math.round(((freshShift.cardSales ?? 0) + cardDelta) * 100) / 100,
          transferSales: Math.round(((freshShift.transferSales ?? 0) + transferDelta) * 100) / 100,
          lastSaleAt: new Date().toISOString()
        }
        saveCurrentShift(updatedShift, config.terminalId)
        setCurrentShift(updatedShift)
      }
      setMessage(
        paymentMethod === 'cash'
          ? `Venta ${folio} registrada. Cambio: $${capturedChange.toFixed(2)}`
          : `Venta ${folio} registrada correctamente.`
      )

      // Auto-print receipt + auto-open drawer (fire-and-forget)
      const hwCfg = loadHwConfigFromCache()
      if (hwCfg) {
        const saleId = saleData.id ?? saleData.sale_id
        if (hwCfg.printer?.enabled && hwCfg.printer?.auto_print && saleId) {
          printReceipt(config, Number(saleId)).catch(() => {})
        }
        if (hwCfg.drawer?.enabled) {
          const shouldOpen =
            (paymentMethod === 'cash' && hwCfg.drawer.auto_open_cash) ||
            (paymentMethod === 'card' && hwCfg.drawer.auto_open_card) ||
            (paymentMethod === 'transfer' && hwCfg.drawer.auto_open_transfer)
          if (shouldOpen) {
            openDrawerForSale(config).catch(() => {})
          }
        }
      }
    } catch (error) {
      const raw = (error as Error).message
      if (raw.includes('fetch') || raw.includes('network') || raw.includes('Failed')) {
        setMessage(
          'No se pudo conectar al servidor. El ticket sigue intacto, intenta cobrar de nuevo.'
        )
      } else if (raw.includes('Tiempo de espera')) {
        setMessage(`${raw} El ticket sigue intacto.`)
      } else {
        setMessage(`Error al registrar venta: ${raw}. El ticket sigue intacto.`)
      }
    } finally {
      chargingRef.current = false
      setBusy(false)
    }
  }, [
    amountReceivedNum,
    cart,
    cartWarnings,
    config,
    customerId,
    customerName,
    globalDiscountPct,
    paymentMethod,
    solicitaFactura,
    paymentReference,
    mixedCash,
    mixedCard,
    mixedTransfer,
    totals,
    wholesaleMode,
    confirm
  ])

  function saveCurrentAsPending(): void {
    if (!cart.length) {
      setMessage('No hay artículos para guardar como pendiente.')
      return
    }
    const label = ticketLabel.trim() || `Ticket-${new Date().toISOString().slice(11, 19)}`
    const pending: PendingTicket = {
      id: `pending-${Date.now()}`,
      label,
      customerName,
      customerId,
      paymentMethod,
      globalDiscountPct,
      cart,
      wholesaleMode
    }
    setPendingTickets((prev) => [pending, ...prev].slice(0, 30))
    setTicketLabel('')
    setMessage(`Pendiente guardado: ${label}`)
    setOpenNewAfterPending(true)
  }

  const openCheckoutModal = useCallback(async (): Promise<void> => {
    if (cart.length === 0) return
    if (cartWarnings.missingSkus.length > 0) {
      setMessage(
        'Hay productos marcados como "Ya no en catálogo". Quítalos del ticket (botón ×) antes de cobrar.'
      )
      return
    }
    if (cartWarnings.lowStockItems.length > 0) {
      const msg = `Hay ${cartWarnings.lowStockItems.length} producto(s) con stock insuficiente. El servidor puede rechazar la venta. ¿Cobrar de todas formas?`
      if (!(await confirm(msg, { variant: 'warning', title: 'Stock insuficiente' }))) return
    }
    setIsCheckoutModalOpen(true)
  }, [cart.length, cartWarnings.missingSkus.length, cartWarnings.lowStockItems.length, confirm])

  useEffect(() => {
    if (!openNewAfterPending) return
    setOpenNewAfterPending(false)
    createNewActiveTicket()
  }, [openNewAfterPending, createNewActiveTicket])

  useEffect((): (() => void) => {
    const onKeyDown = async (event: KeyboardEvent): Promise<void> => {
      // Bloquear atajos si no estamos estrictamente en la pestaña de Terminal
      if (window.location.hash !== '#/terminal') return

      // Permitir la navegación natural (Tab, Flechas) si hay un modal abierto
      if (document.getElementById('checkout-modal') || document.querySelector('[role="dialog"]')) {
        if (event.key === 'Escape' && isCheckoutModalOpen) {
          setIsCheckoutModalOpen(false)
        }
        return
      }

      const key = event.key.toLowerCase()
      const tag = (document.activeElement?.tagName ?? '').toUpperCase()
      const isInputFocused = tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA'

      if (key === 'f10') {
        event.preventDefault()
        event.stopImmediatePropagation()
        searchInputRef.current?.focus()
        searchInputRef.current?.select()
        return
      }

      if (key === 'f11') {
        event.preventDefault()
        event.stopImmediatePropagation()
        setWholesaleMode((prev) => !prev)
        return
      }

      if (key === 'f12') {
        event.preventDefault()
        event.stopImmediatePropagation()
        if (!busy && !isInputFocused) {
          if (cart.length === 0) {
            setMessage('Agrega productos al carrito antes de cobrar.')
            return
          }
          void openCheckoutModal()
        }
        return
      }

      if (!isInputFocused) {
        if (key === '+' || key === '=' || key === 'add') {
          event.preventDefault()
          increaseSelectedQty()
          return
        }

        if (key === '-' || key === 'subtract') {
          event.preventDefault()
          decreaseSelectedQty()
          return
        }

        if (key === 'delete' || key === 'backspace') {
          event.preventDefault()
          void deleteSelectedItem()
          return
        }
      }

      if (!event.ctrlKey) return

      // Bloquear comportamientos nativos del navegador con Ctrl
      if (key === 'p' || key === 'd' || key === 'g' || key === 'n') {
        event.preventDefault()
        event.stopImmediatePropagation()
      }

      // Si hay algun modal abierto o input enfocado, no ejecutar atajos Ctrl
      const isAnyModalOpen =
        isCheckoutModalOpen || isDiscountModalOpen || isCommonModalOpen || isNoteModalOpen

      if (isInputFocused || isAnyModalOpen) return

      if (key === 'p') {
        void addCommonProduct()
        return
      }

      if (key === 'd') {
        if (!selectedCartSku) {
          setMessage('Selecciona un producto del carrito para aplicar descuento.')
          return
        }
        const current = cart.find((item) => item.sku === selectedCartSku)
        if (!current) {
          setMessage('El producto seleccionado ya no está en el carrito.')
          return
        }
        const raw = await prompt('Descuento de producto seleccionado (%):', {
          title: 'Descuento individual',
          defaultValue: String(current.discountPct ?? 0),
          inputType: 'number',
          placeholder: '0'
        })
        if (raw == null) return
        const parsed = Number(raw)
        if (!Number.isFinite(parsed)) {
          setMessage('Valor de descuento inválido.')
          return
        }
        updateItemDiscount(selectedCartSku, parsed)
        setMessage(`Descuento aplicado al SKU ${selectedCartSku}.`)
        return
      }

      if (key === 'g') {
        event.preventDefault()
        const raw = await prompt('Descuento global de la nota (%):', {
          title: 'Descuento global',
          defaultValue: String(globalDiscountPct),
          inputType: 'number',
          placeholder: '0'
        })
        if (raw == null) return
        const parsed = Number(raw)
        if (!Number.isFinite(parsed)) {
          setMessage('Valor de descuento global inválido.')
          return
        }
        setGlobalDiscountPct(clampDiscount(parsed))
        setMessage('Descuento global actualizado.')
      }

      if (key === 'n') {
        event.preventDefault()
        createNewActiveTicket()
      }
    }

    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [
    addCommonProduct,
    busy,
    cart,
    createNewActiveTicket,
    decreaseSelectedQty,
    deleteSelectedItem,
    globalDiscountPct,
    handleCharge,
    increaseSelectedQty,
    isCheckoutModalOpen,
    isCommonModalOpen,
    isDiscountModalOpen,
    isNoteModalOpen,
    openCheckoutModal,
    prompt,
    selectedCartSku,
    updateItemDiscount
  ])

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex flex-1 min-h-0 flex-col overflow-hidden bg-zinc-950">
        {/* Panel: ancho y alto completos, sin márgenes para evitar espacio muerto */}
        <div className="w-full h-full flex flex-col min-h-0 bg-zinc-950 border-x border-zinc-900 relative overflow-hidden">
          {/* Ticket Header (Shift + Ticket Actions) */}
          <div className="shrink-0 flex flex-wrap items-stretch justify-between gap-3 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-0">
            {/* Pestañas tipo navegador */}
            <div className="flex items-end gap-0 min-w-0 flex-1">
              <div className="flex items-end gap-0 overflow-x-auto hide-scrollbar">
                {activeTickets.map((t) => (
                  <div
                    key={t.id}
                    className={`shrink-0 flex items-center rounded-t-lg border border-zinc-800 border-b-0 overflow-hidden ${
                      t.id === activeTicketId
                        ? 'bg-zinc-950 border-b-2 border-b-zinc-950 -mb-px'
                        : 'bg-zinc-800/90'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => switchActiveTicket(t.id)}
                      className={`px-2.5 py-2 text-xs font-bold transition text-left whitespace-nowrap ${
                        t.id === activeTicketId
                          ? 'text-blue-400'
                          : 'text-zinc-400 hover:text-zinc-300'
                      }`}
                    >
                      {t.label}
                    </button>
                    {activeTickets.length > 1 && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          closeActiveTicket(t.id)
                        }}
                        className="p-1 rounded hover:bg-zinc-600/80 text-zinc-400 hover:text-rose-400 transition shrink-0"
                        title="Cerrar pestaña"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                onClick={() => createNewActiveTicket()}
                className="shrink-0 p-1.5 rounded-t-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition border border-zinc-800 border-b-0"
                title="Nuevo (Ctrl+N)"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            {/* Shift Info */}
            <div className="flex items-center gap-3 shrink-0 min-w-0">
              <div
                className="text-sm font-medium text-zinc-400 flex items-center gap-1.5 min-w-0"
                title={currentShift ? `Turno: ${currentShift.openedBy}` : 'Sin turno'}
              >
                <div
                  className={`w-2 h-2 rounded-full shrink-0 ${currentShift ? 'bg-emerald-500' : 'bg-rose-500'}`}
                />
                <span className="min-w-0 max-w-[160px] truncate">
                  {currentShift ? currentShift.openedBy : 'Cerrado'}
                </span>
              </div>
            </div>
          </div>

          {/* Top Search Bar (Integrated) */}
          <div className="p-4 shrink-0 border-b border-zinc-900/50 bg-[#09090b] relative z-30 shadow-md">
            <div className="relative w-full flex items-center gap-2">
              <div className="relative flex-1 min-w-0">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <input
                  ref={searchInputRef}
                  autoFocus
                  maxLength={200}
                  defaultValue=""
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-2.5 pl-10 pr-10 text-sm font-medium text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/50 focus:bg-zinc-900 focus:ring-2 focus:ring-blue-500/10 transition-all shadow-inner"
                  placeholder="Buscar producto o escanear (F10)..."
                  onChange={(e) => {
                    lastKeystrokeRef.current = Date.now()
                    const normalized = normalizeSearchInput(e.target.value)
                    if (
                      Date.now() < suppressSearchChangeUntilRef.current &&
                      normalized === normalizeSearchInput(lastSubmittedSearchRef.current)
                    ) {
                      clearSearchDomValue()
                      return
                    }
                    setQuery(normalized)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      e.stopPropagation()

                      const now = Date.now()
                      if (now - lastEnterRef.current < 150) return
                      lastEnterRef.current = now

                      const currentValue = e.currentTarget.value
                      if (!currentValue.trim()) return
                      lastSubmittedSearchRef.current = currentValue
                      const match = findProductForSearch(currentValue, now)
                      if (!match) {
                        return
                      }
                      addProduct(match)
                      clearSearch()
                      return
                    }
                  }}
                />
                {wholesaleMode && (
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 bg-amber-500 text-amber-950 text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded shadow-[0_0_10px_rgba(245,158,11,0.5)] animate-pulse">
                    Mayoreo
                  </div>
                )}

                {/* Embedded Search Results Dropdown */}
                {query.trim() && (
                  <div className="absolute top-[calc(100%+8px)] left-0 right-0 bg-zinc-900 border border-zinc-700/50 rounded-xl shadow-[0_20px_60px_rgba(0,0,0,0.95)] max-h-[50vh] overflow-y-auto z-[60] backdrop-blur-md">
                    {filtered.length === 0 ? (
                      <div className="p-4 text-center text-zinc-500 text-sm">
                        Ningún producto coincide con &quot;{query}&quot;
                      </div>
                    ) : (
                      <div className="flex flex-col">
                        {filtered.slice(0, 50).map((p) => (
                          <button
                            key={p.sku}
                            onClick={() => {
                              addProduct(p)
                              clearSearch()
                            }}
                            className="flex items-center justify-between p-3 border-b border-zinc-800/50 hover:bg-zinc-800 transition-colors text-left group"
                          >
                            <div>
                              <div className="text-sm font-semibold text-zinc-200 group-hover:text-blue-400 transition-colors">
                                {p.name.length > 80 ? p.name.slice(0, 80) + '…' : p.name}
                              </div>
                              <div className="text-xs text-zinc-500 font-mono mt-0.5">{p.sku}</div>
                            </div>
                            <div className="text-right flex flex-col items-end">
                              <div className="text-emerald-400 font-bold">
                                ${p.price.toFixed(2)}
                              </div>
                              {p.stock !== undefined && (
                                <div
                                  className={`text-[10px] uppercase font-bold mt-1 px-1.5 py-0.5 rounded ${p.stock <= (p.minStock ?? 0) ? 'bg-rose-500/20 text-rose-500' : 'bg-zinc-800 text-zinc-500'}`}
                                >
                                  Stock: {p.stock}
                                </div>
                              )}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => window.dispatchEvent(new CustomEvent('pos-open-price-check'))}
                className="hidden sm:flex items-center justify-center gap-1.5 min-h-[40px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold px-5 py-2.5 rounded-xl transition-colors shrink-0 whitespace-nowrap text-sm"
                title="Consulta de precios y unidades (F9)"
              >
                <Tag className="w-4 h-4 shrink-0" />
                Consulta precios (F9)
              </button>
              <button
                onClick={saveCurrentAsPending}
                disabled={cart.length === 0}
                className="hidden sm:flex items-center justify-center gap-1.5 min-h-[40px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold px-5 py-2.5 rounded-xl transition-colors shrink-0 disabled:opacity-30 disabled:hover:bg-zinc-800 whitespace-nowrap text-sm"
                title="Guardar ticket como pendiente"
              >
                <Ticket className="w-4 h-4 shrink-0" />
                Ticket pendiente
              </button>
            </div>
          </div>

          {/* Cart Items List — ocupa todo el espacio central */}
          <div className="flex-1 min-h-0 overflow-y-auto p-4 lg:p-6 space-y-3 relative hide-scrollbar z-10">
            {(cartWarnings.missingSkus.length > 0 || cartWarnings.lowStockItems.length > 0) && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-200 mb-2">
                {cartWarnings.missingSkus.length > 0 && cartWarnings.lowStockItems.length > 0
                  ? 'Productos con stock insuficiente o fuera de catálogo. Revisa las líneas marcadas antes de cobrar.'
                  : cartWarnings.missingSkus.length > 0
                    ? 'Algunos productos ya no están en el catálogo. Revisa las líneas marcadas antes de cobrar.'
                    : 'Productos con stock insuficiente. Revisa las líneas marcadas antes de cobrar.'}
              </div>
            )}
            {cart.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-600 pointer-events-none">
                <ShoppingCartIcon className="w-16 h-16 mb-4 opacity-20" />
                <p className="text-base font-medium">Ticket vacío</p>
              </div>
            ) : (
              cart.map((item) => (
                <div
                  key={item.sku}
                  onClick={() => setSelectedCartSku(item.sku)}
                  className={`py-1 px-2 rounded-md border transition-all cursor-pointer ${selectedCartSku === item.sku ? 'bg-blue-600/10 border-blue-500/50' : 'bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700'}`}
                >
                  <div className="flex items-center justify-between gap-2 min-h-0">
                    <div className="font-semibold text-xs text-zinc-200 leading-none truncate min-w-0">
                      {item.name}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-[10px] text-zinc-500 font-mono" title={item.sku}>
                        {item.sku.length > 13 ? item.sku.substring(0, 13) + '…' : item.sku}
                      </span>
                      <span className="text-[10px] text-zinc-400">
                        ${item.price.toFixed(2)} c/u
                      </span>
                      <div
                        className="flex items-center gap-0.5 bg-zinc-950 rounded border border-zinc-800"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedCartSku(item.sku)
                            decreaseSelectedQty()
                          }}
                          className="w-5 h-5 flex items-center justify-center rounded-sm bg-zinc-800 text-zinc-400 hover:text-white text-[10px] font-bold"
                        >
                          −
                        </button>
                        <span className="w-5 text-center text-[10px] font-bold text-zinc-200">
                          {item.qty}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedCartSku(item.sku)
                            increaseSelectedQty()
                          }}
                          className="w-5 h-5 flex items-center justify-center rounded-sm bg-zinc-800 text-zinc-400 hover:text-white text-[10px] font-bold"
                        >
                          +
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation()
                            setSelectedCartSku(item.sku)
                            if (
                              await confirm(`¿Quitar "${item.name}"?`, {
                                variant: 'warning',
                                title: 'Quitar'
                              })
                            )
                              removeItem(item.sku)
                          }}
                          className="w-5 h-5 flex items-center justify-center rounded-sm bg-rose-950/20 text-rose-500/60 hover:text-rose-400 text-xs ml-0.5"
                        >
                          ×
                        </button>
                      </div>
                      <span className="font-bold text-emerald-400 text-xs">
                        ${item.subtotal.toFixed(2)}
                      </span>
                    </div>
                  </div>
                  {(item.discountPct > 0 ||
                    cartWarnings.missingSkus.includes(item.sku) ||
                    cartWarnings.lowStockItems.some((l) => l.sku === item.sku)) && (
                    <div className="mt-0.5 flex flex-wrap items-center gap-1 leading-none">
                      {item.discountPct > 0 && (
                        <span className="text-[9px] font-bold text-rose-400 uppercase">
                          Desc. {item.discountPct}%
                        </span>
                      )}
                      {cartWarnings.missingSkus.includes(item.sku) && (
                        <span className="text-[9px] font-bold uppercase px-1 py-0 rounded bg-amber-500/20 text-amber-400">
                          Ya no en catálogo
                        </span>
                      )}
                      {cartWarnings.lowStockItems.find((l) => l.sku === item.sku) && (
                        <span className="text-[9px] font-bold uppercase px-1 py-0 rounded bg-rose-500/20 text-rose-400">
                          Stock:{' '}
                          {cartWarnings.lowStockItems.find((l) => l.sku === item.sku)
                            ?.currentStock ?? 0}{' '}
                          (solicitado: {item.qty})
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Totals & Payment Area — ancho, bajo */}
          <div className="shrink-0 bg-zinc-950 border-t border-zinc-900 px-3 py-2 lg:px-4 lg:py-2.5 space-y-1.5 max-w-4xl mx-auto w-full">
            {globalDiscountPct > 0 && (
              <div className="flex justify-between items-center text-[11px] leading-tight">
                <span className="text-zinc-500 font-bold uppercase tracking-wider">
                  Descuento ({globalDiscountPct}%)
                </span>
                <span className="text-rose-400 font-bold">
                  -${totals.globalDiscountAmount.toFixed(2)}
                </span>
              </div>
            )}
            <div className="grid grid-cols-[1fr_auto] gap-2 items-end">
              <div className="min-w-0 flex flex-col relative" ref={customerPickerRef}>
                <button
                  type="button"
                  className="flex items-center gap-1 text-[11px] text-zinc-300 font-bold uppercase tracking-wider mb-0.5 cursor-pointer hover:text-blue-400 transition text-left min-w-0 w-full leading-tight"
                  onClick={() => setCustomerPickerOpen((v) => !v)}
                >
                  <Users className="w-3 h-3 shrink-0" />
                  <span className="truncate">
                    {customerName === 'Público General' ? 'Cliente' : customerName}
                  </span>
                </button>
                {/* Customer picker dropdown — compacto, máx. 3 opciones visibles para incentivar búsqueda */}
                {customerPickerOpen && (
                  <div className="absolute bottom-full left-0 mb-1 w-56 bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl z-50 overflow-hidden">
                    <div className="px-2 py-1.5 border-b border-zinc-800 flex items-center gap-1.5">
                      <SearchIcon className="w-3 h-3 text-zinc-500 shrink-0" />
                      <input
                        ref={customerSearchRef}
                        type="text"
                        className="flex-1 min-w-0 bg-transparent text-[11px] text-zinc-200 placeholder:text-zinc-600 outline-none"
                        placeholder="Buscar cliente..."
                        value={customerSearch}
                        onChange={(e) => setCustomerSearch(e.target.value)}
                        onKeyDown={(e) => e.stopPropagation()}
                      />
                      <button
                        type="button"
                        onClick={() => setCustomerPickerOpen(false)}
                        className="text-zinc-500 hover:text-zinc-300 p-0.5"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                    <div className="max-h-[7.5rem] overflow-y-auto">
                      {/* Público General — siempre primero */}
                      <button
                        type="button"
                        className={`w-full text-left px-2 py-1.5 text-[11px] hover:bg-zinc-800 transition flex items-center justify-between gap-2 ${customerId === null ? 'text-blue-400 bg-blue-600/10' : 'text-zinc-300'}`}
                        onClick={() => {
                          setCustomerName('Público General')
                          setCustomerId(null)
                          setCustomerPickerOpen(false)
                        }}
                      >
                        <span className="font-semibold truncate">Público General</span>
                        {customerId === null && (
                          <CheckCircle2 className="w-3 h-3 text-blue-400 shrink-0" />
                        )}
                      </button>
                      {(() => {
                        const filtered = customerResults.filter((c) => {
                          if (!customerSearch.trim()) return true
                          const q = customerSearch.toLowerCase()
                          return (
                            c.name.toLowerCase().includes(q) ||
                            (c.phone?.toLowerCase().includes(q) ?? false)
                          )
                        })
                        const toShow = filtered.slice(0, 2)
                        return (
                          <>
                            {toShow.map((c) => (
                              <button
                                key={c.id}
                                type="button"
                                className={`w-full text-left px-2 py-1.5 text-[11px] hover:bg-zinc-800 transition flex items-center justify-between gap-2 ${customerId === c.id ? 'text-blue-400 bg-blue-600/10' : 'text-zinc-300'}`}
                                onClick={() => {
                                  setCustomerName(c.name)
                                  setCustomerId(c.id)
                                  setCustomerPickerOpen(false)
                                }}
                              >
                                <div className="min-w-0 truncate">
                                  <span className="font-semibold">{c.name}</span>
                                  {c.phone && (
                                    <span className="ml-1.5 text-zinc-500 text-[10px]">
                                      {c.phone}
                                    </span>
                                  )}
                                </div>
                                {customerId === c.id && (
                                  <CheckCircle2 className="w-3 h-3 text-blue-400 shrink-0" />
                                )}
                              </button>
                            ))}
                            {filtered.length > 2 && (
                              <div className="px-2 py-1 text-[10px] text-zinc-500 text-center border-t border-zinc-800">
                                +{filtered.length - 2} más — busca para filtrar
                              </div>
                            )}
                          </>
                        )
                      })()}
                      {customerResults.length === 0 && (
                        <div className="px-2 py-2 text-[11px] text-zinc-500 text-center">
                          Cargando clientes...
                        </div>
                      )}
                    </div>
                  </div>
                )}
                <span className="text-[11px] text-zinc-400 font-medium leading-tight">
                  {cart.reduce((a, i) => a + i.qty, 0)} artículos
                </span>
              </div>
              <div className="text-2xl lg:text-3xl font-black text-white tabular-nums tracking-tight text-right leading-tight">
                ${totals.total.toFixed(2)}
              </div>
            </div>

            <div className="text-[10px] text-zinc-400 uppercase tracking-wider text-center leading-tight">
              F9 Precios · F10 Buscar · F11 Mayoreo · F12 Cobrar
            </div>

            <button
              onClick={() => void openCheckoutModal()}
              disabled={busy || cart.length === 0}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg py-1.5 font-bold text-sm tracking-wide transition-colors disabled:opacity-50 disabled:shadow-none active:scale-[0.98]"
            >
              {busy ? 'Procesando...' : 'COBRAR'}
            </button>
          </div>
        </div>
      </div>

      {/* Checkout Modal */}
      {isCheckoutModalOpen && (
        <div
          id="checkout-modal"
          role="dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setIsCheckoutModalOpen(false)
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsCheckoutModalOpen(false)
          }}
        >
          <div
            ref={checkoutModalRef}
            className="w-full max-w-md bg-zinc-950 border border-zinc-800 rounded-3xl p-6 shadow-2xl animate-fade-in-up"
          >
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
                <ShoppingCartIcon className="w-6 h-6 text-blue-500" /> Confirmar cobro
              </h2>
              <button
                type="button"
                onClick={() => setIsCheckoutModalOpen(false)}
                className="p-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 rounded-xl transition-colors"
                tabIndex={-1}
              >
                <XIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 mb-6 text-center">
              <p className="text-sm text-zinc-500 uppercase font-bold tracking-wider mb-1">
                Monto a cobrar
              </p>
              <p className="text-5xl font-black text-white tracking-tighter tabular-nums">
                ${totals.total.toFixed(2)}
              </p>
            </div>

            <div className="space-y-4 mb-8">
              <div className="relative">
                <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider block mb-2">
                  Método de pago
                </label>
                <select
                  autoFocus
                  className="w-full bg-zinc-900/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-semibold text-zinc-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 cursor-pointer appearance-none"
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                >
                  <option value="cash">Efectivo</option>
                  <option value="card">Tarjeta</option>
                  <option value="transfer">Transferencia</option>
                  <option value="mixed">Mixto</option>
                </select>
                <div className="absolute right-4 top-[38px] pointer-events-none text-zinc-500">
                  {paymentMethod === 'cash' && <Banknote className="w-5 h-5 opacity-70" />}
                  {paymentMethod === 'card' && <CreditCard className="w-5 h-5 opacity-70" />}
                  {paymentMethod === 'transfer' && <Landmark className="w-5 h-5 opacity-70" />}
                  {paymentMethod === 'mixed' && <Wallet className="w-5 h-5 opacity-70" />}
                </div>
              </div>

              <div>
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={solicitaFactura}
                    onChange={(e) => setSolicitaFactura(e.target.checked)}
                    className="w-4 h-4 rounded border-zinc-600 bg-zinc-900 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                  />
                  <FileText className="w-4 h-4 text-zinc-500 group-hover:text-zinc-400 shrink-0" />
                  <span className="text-sm font-medium text-zinc-300 group-hover:text-zinc-200">
                    El cliente solicita factura para esta compra
                  </span>
                </label>
              </div>

              {paymentMethod === 'mixed' ? (
                <div className="space-y-3">
                  <p className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                    Desglose (suma = ${totals.total.toFixed(2)})
                  </p>
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1">Efectivo</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="w-full bg-zinc-900/80 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-medium text-zinc-200 focus:outline-none focus:border-blue-500"
                      placeholder="0.00"
                      value={mixedCash}
                      onChange={(e) => setMixedCash(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1">Tarjeta</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="w-full bg-zinc-900/80 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-medium text-zinc-200 focus:outline-none focus:border-blue-500"
                      placeholder="0.00"
                      value={mixedCard}
                      onChange={(e) => setMixedCard(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1">Transferencia</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="w-full bg-zinc-900/80 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-medium text-zinc-200 focus:outline-none focus:border-blue-500"
                      placeholder="0.00"
                      value={mixedTransfer}
                      onChange={(e) => setMixedTransfer(e.target.value)}
                    />
                  </div>
                  {(() => {
                    const sum = toNumber(mixedCash) + toNumber(mixedCard) + toNumber(mixedTransfer)
                    const valid = sum > 0 && Math.abs(sum - totals.total) <= 0.02
                    return (
                      <p
                        className={`text-xs font-semibold ${valid ? 'text-emerald-500' : 'text-amber-500'}`}
                      >
                        Suma: ${sum.toFixed(2)}
                        {!valid && sum > 0 && (
                          <span className="ml-1">(debe ser ${totals.total.toFixed(2)})</span>
                        )}
                      </p>
                    )
                  })()}
                </div>
              ) : paymentMethod === 'cash' ? (
                <div>
                  <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider block mb-2">
                    Recibido
                  </label>
                  <input
                    type="number"
                    className="w-full bg-zinc-900/80 border border-zinc-800 rounded-xl px-4 py-3 text-base font-bold text-emerald-400 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 placeholder:text-zinc-700 transition"
                    placeholder={`Recibido... (Mín. $${totals.total.toFixed(2)})`}
                    value={amountReceived}
                    onChange={(e) => setAmountReceived(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !busy) {
                        setIsCheckoutModalOpen(false)
                        void handleCharge()
                      }
                    }}
                  />
                  {amountReceivedNum > 0 && (
                    <div className="flex justify-between items-center px-1 mt-3">
                      <span className="text-xs font-bold text-zinc-500 uppercase">
                        {pendingAmount > 0 ? 'Faltante' : 'Cambio'}
                      </span>
                      <span
                        className={`text-lg tracking-tight font-black ${pendingAmount > 0 ? 'text-rose-400' : 'text-amber-400'}`}
                      >
                        ${pendingAmount > 0 ? pendingAmount.toFixed(2) : changeDue.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {(paymentMethod === 'card' || paymentMethod === 'transfer') && (
                    <div>
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider block mb-2">
                        {paymentMethod === 'card'
                          ? 'Referencia (código de autorización o últimos 4 dígitos)'
                          : 'Referencia de transferencia'}
                      </label>
                      <input
                        type="text"
                        maxLength={paymentMethod === 'card' ? 20 : 100}
                        className="w-full bg-zinc-900/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-medium text-zinc-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 placeholder:text-zinc-600"
                        placeholder={paymentMethod === 'card' ? 'Ej. 1234' : 'Ej. SPEI-123456789'}
                        value={paymentReference}
                        onChange={(e) => setPaymentReference(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !busy) {
                            setIsCheckoutModalOpen(false)
                            void handleCharge()
                          }
                        }}
                      />
                    </div>
                  )}
                  <div
                    className="w-full bg-zinc-900/40 border border-zinc-800 rounded-xl px-4 py-3 flex items-center justify-center text-sm font-medium text-emerald-400/50 cursor-pointer hover:bg-zinc-900/60 transition"
                    onClick={() => {
                      setIsCheckoutModalOpen(false)
                      void handleCharge()
                    }}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        setIsCheckoutModalOpen(false)
                        void handleCharge()
                      }
                    }}
                  >
                    Pago exacto (Enter para confirmar)
                  </div>
                </>
              )}
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setIsCheckoutModalOpen(false)}
                className="flex-1 bg-rose-600 border border-rose-500 hover:bg-rose-500 text-white rounded-xl py-3.5 font-bold transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => {
                  setIsCheckoutModalOpen(false)
                  void handleCharge()
                }}
                disabled={
                  busy ||
                  cart.length === 0 ||
                  (paymentMethod === 'mixed' &&
                    (() => {
                      const sum =
                        toNumber(mixedCash) + toNumber(mixedCard) + toNumber(mixedTransfer)
                      return sum <= 0 || Math.abs(sum - totals.total) > 0.02
                    })())
                }
                className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl py-3.5 font-black tracking-widest shadow-[0_0_20px_-5px_rgba(37,99,235,0.6)] hover:shadow-[0_0_30px_-5px_rgba(37,99,235,0.8)] transition-all disabled:opacity-50 active:scale-95"
              >
                {busy ? 'Procesando...' : 'COBRAR'}
              </button>
            </div>
          </div>
        </div>
      )}

      {isCommonModalOpen && (
        <CommonProductModal
          defaultQty={qty}
          onSubmit={handleCommonProductSubmit}
          onClose={() => setIsCommonModalOpen(false)}
        />
      )}
    </div>
  )
}
