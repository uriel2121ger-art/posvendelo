import type { ReactElement } from 'react'

import { useConfirm, usePrompt } from './components/ConfirmDialog'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Plus,
  Search as SearchIcon,
  ShoppingCart as ShoppingCartIcon
} from 'lucide-react'
import {
  type RuntimeConfig,
  type SaleItemPayload,
  type HardwareConfig,
  loadRuntimeConfig,
  saveRuntimeConfig,
  pullTable,
  createSale,
  printReceipt,
  openDrawerForSale,
  getTurnSummary
} from './posApi'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  priceWholesale?: number
  stock?: number
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
  subtotal: number
}

type PaymentMethod = 'cash' | 'card' | 'transfer'

type PendingTicket = {
  id: string
  label: string
  customerName: string
  paymentMethod: PaymentMethod
  globalDiscountPct: number
  cart: CartItem[]
}

type ActiveTicketMeta = {
  id: string
  label: string
}

type ActiveTicketSnapshot = {
  customerName: string
  paymentMethod: PaymentMethod
  globalDiscountPct: number
  cart: CartItem[]
  selectedCartSku: string | null
  amountReceived: string
}

const TAX_RATE = 0.16
const PENDING_TICKETS_STORAGE_KEY = 'titan.pendingTickets'
import { type ShiftRecord as ShiftState, CURRENT_SHIFT_KEY, readCurrentShift } from './shiftTypes'
const ACTIVE_TICKETS_STORAGE_KEY = 'titan.activeTickets'


function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
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

function readSavedActiveState(): SavedActiveState | null {
  try {
    const raw = localStorage.getItem(ACTIVE_TICKETS_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SavedActiveState
    if (!parsed || !Array.isArray(parsed.activeTickets) || !parsed.activeTicketId) return null
    return parsed
  } catch {
    return null
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
    stock: toNumber(raw.stock)
  }
}

async function fetchProducts(cfg: RuntimeConfig): Promise<Product[]> {
  const raw = await pullTable('products', cfg)
  return raw.map(normalizeProduct).filter((item): item is Product => item !== null)
}

async function syncSale(
  cfg: RuntimeConfig,
  cart: CartItem[],
  _customerName: string,
  paymentMethod: PaymentMethod,
  globalDiscountPct: number,
  amountReceived?: number,
  turnId?: number | null,
  isWholesale?: boolean
): Promise<Record<string, unknown>> {
  const globalDisc = clampDiscount(globalDiscountPct) / 100
  const items: SaleItemPayload[] = cart.map((item) => {
    // Compound discount: matches how the frontend display calculates totals
    // item.subtotal already has per-item discount applied (price * qty * (1 - itemDisc/100))
    // Then global discount is applied on top: item.subtotal * (1 - globalDisc)
    const fullPrice = Math.round(item.price * item.qty * 100) / 100
    const compoundSubtotal = Math.round(item.subtotal * (1 - globalDisc) * 100) / 100
    const discount = parseFloat(Math.max(0, fullPrice - compoundSubtotal).toFixed(2))
    return {
      product_id: item.isCommon ? null : Number(item.id) > 0 ? Number(item.id) : null,
      name: item.name,
      qty: item.qty,
      price: item.price,
      discount,
      is_wholesale: isWholesale ?? false,
      price_includes_tax: true
    }
  })
  const res = await createSale(cfg, {
    items,
    payment_method: paymentMethod,
    cash_received: paymentMethod === 'cash' ? (amountReceived ?? 0) : undefined,
    serie: 'A',
    turn_id: turnId ?? undefined
  })
  const data = (res.data ?? res) as Record<string, unknown>
  return data
}

export default function Terminal(): ReactElement {
  const confirm = useConfirm()
  const prompt = usePrompt()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const lastKeystrokeRef = useRef<number>(Date.now())
  const lastEnterRef = useRef<number>(0)
  const [config] = useState<RuntimeConfig>(() => loadRuntimeConfig())
  const [products, setProducts] = useState<Product[]>([])
  // Restore active ticket state from localStorage (navigation persistence)
  const [_savedActive] = useState(() => readSavedActiveState())
  const _snap = _savedActive?.ticketSnapshots?.[_savedActive?.activeTicketId ?? '']
  const [cart, setCart] = useState<CartItem[]>(_snap?.cart ?? [])
  const [customerName, setCustomerName] = useState(_snap?.customerName ?? 'Publico General')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(_snap?.paymentMethod ?? 'cash')
  const [amountReceived, setAmountReceived] = useState(_snap?.amountReceived ?? '')
  const [globalDiscountPct, setGlobalDiscountPct] = useState(_snap?.globalDiscountPct ?? 0)
  const [pendingTickets, setPendingTickets] = useState<PendingTicket[]>([])
  const [activeTickets, setActiveTickets] = useState<ActiveTicketMeta[]>(
    _savedActive?.activeTickets ?? [{ id: 'active-1', label: 'Activa 1' }]
  )
  const [activeTicketId, setActiveTicketId] = useState(_savedActive?.activeTicketId ?? 'active-1')
  const [ticketSnapshots, setTicketSnapshots] = useState<Record<string, ActiveTicketSnapshot>>(
    _savedActive?.ticketSnapshots ?? {
      'active-1': {
        customerName: 'Publico General',
        paymentMethod: 'cash',
        globalDiscountPct: 0,
        cart: [],
        selectedCartSku: null,
        amountReceived: ''
      }
    }
  )
  const [selectedCartSku, setSelectedCartSku] = useState<string | null>(
    _snap?.selectedCartSku ?? null
  )
  const ticketCounterRef = useRef(_savedActive?.ticketCounter ?? 1)
  const [ticketLabel, setTicketLabel] = useState('')
  const [qty] = useState(1)
  const [query, setQuery] = useState('')
      const [busy, setBusy] = useState(false)
  const [currentShift, setCurrentShift] = useState<ShiftState | null>(() => readCurrentShift())
  const [wholesaleMode, setWholesaleMode] = useState(false)
  const [message, setMessage] = useState('Cargando productos...')
  const chargingRef = useRef(false)

  useEffect((): void => {
    saveRuntimeConfig(config)
  }, [config])

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
          setProducts(data)
          if (!silent) setMessage(data.length ? `${data.length} productos cargados` : 'Sin productos')
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
    const onFocus = (): void => { loadProducts(true) }
    window.addEventListener('focus', onFocus)
    return (): void => {
      cancelled = true
      window.removeEventListener('focus', onFocus)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Recalculate cart prices when wholesale mode toggles
  useEffect(() => {
    setCart((prev) =>
      prev.map((item) => {
        const effectivePrice =
          wholesaleMode && item.priceWholesale ? item.priceWholesale : (products.find((p) => p.sku === item.sku)?.price ?? item.price)
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

  useEffect((): void => {
    let raw: string | null = null
    try {
      raw = localStorage.getItem(PENDING_TICKETS_STORAGE_KEY)
    } catch {
      /* storage inaccessible */
    }
    if (!raw) {

      return
    }
    try {
      const parsed = JSON.parse(raw) as PendingTicket[]
      if (!Array.isArray(parsed)) {

        return
      }
      // Validate each ticket has required fields before loading
      const valid = parsed.filter(
        (t) => t && typeof t.id === 'string' && typeof t.label === 'string' && Array.isArray(t.cart)
      )
      setPendingTickets(valid)
    } catch {
      // ignore invalid stored payload
    }

  }, [])

  const isFirstPendingPersist = useRef(true)
  useEffect((): void => {
    // Skip the mount-time execution to avoid overwriting localStorage with []
    // before the load effect's state update has re-rendered
    if (isFirstPendingPersist.current) {
      isFirstPendingPersist.current = false
      return
    }
    try {
      localStorage.setItem(PENDING_TICKETS_STORAGE_KEY, JSON.stringify(pendingTickets))
    } catch {
      setMessage('Error: no se pudieron guardar tickets pendientes. Almacenamiento lleno.')
    }
  }, [pendingTickets])

  useEffect((): (() => void) => {
    const refreshShift = (): void => setCurrentShift(readCurrentShift())
    const onStorage = (event: StorageEvent): void => {
      if (event.key === CURRENT_SHIFT_KEY) refreshShift()
    }
    window.addEventListener('focus', refreshShift)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('focus', refreshShift)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  // Poll backend every 60s to sync shift counters (multi-terminal visibility)
  useEffect(() => {
    const poll = setInterval(() => {
      const shift = readCurrentShift()
      if (!shift?.backendTurnId) return
      const cfg = loadRuntimeConfig()
      getTurnSummary(cfg, shift.backendTurnId)
        .then((raw) => {
          const data = (raw.data ?? raw) as Record<string, unknown>
          const backendCount = Number(data.sales_count ?? 0)
          const backendTotal = Number(data.total_sales ?? 0)
          if (backendCount > (shift.salesCount ?? 0) || Math.abs(backendTotal - (shift.totalSales ?? 0)) > 0.01) {
            const updated: ShiftState = {
              ...shift,
              salesCount: backendCount,
              totalSales: Math.round(backendTotal * 100) / 100
            }
            try {
              localStorage.setItem(CURRENT_SHIFT_KEY, JSON.stringify(updated))
            } catch { /* storage full */ }
            setCurrentShift(updated)
          }
        })
        .catch(() => { /* network error — skip this cycle */ })
    }, 60_000)
    return () => clearInterval(poll)
  }, [])

  const filtered = useMemo((): Product[] => {
    const q = query.trim().toLowerCase()
    if (!q) return products.slice(0, 20)
    return products
      .filter((p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q))
      .slice(0, 20)
  }, [products, query])

  const totals = useMemo((): {
    subtotalBeforeDiscount: number
    globalDiscountAmount: number
    subtotal: number
    tax: number
    total: number
  } => {
    // Accumulate in cents to avoid float drift over many cart items
    const subtotalBeforeDiscountCents = cart.reduce(
      (acc, item) => acc + Math.round(item.subtotal * 100),
      0
    )
    const subtotalBeforeDiscount = subtotalBeforeDiscountCents / 100
    const globalDiscountAmount =
      Math.round(subtotalBeforeDiscount * (clampDiscount(globalDiscountPct) / 100) * 100) / 100
    // Prices already include IVA — total is the sum minus discount (NOT plus tax)
    const total = Math.round((subtotalBeforeDiscount - globalDiscountAmount) * 100) / 100
    // Extract IVA that's already baked into the prices (informational for display)
    const tax = Math.round((total - total / (1 + TAX_RATE)) * 100) / 100
    const subtotal = Math.round((total - tax) * 100) / 100
    return { subtotalBeforeDiscount, globalDiscountAmount, subtotal, tax, total }
  }, [cart, globalDiscountPct])
  const amountReceivedNum = toNumber(amountReceived)
  const changeDue = Math.max(0, amountReceivedNum - totals.total)
  const pendingAmount = Math.max(0, totals.total - amountReceivedNum)

  // Snapshot current ticket AND persist to localStorage atomically.
  // Previously split into 2 effects with a race condition: if the component
  // unmounted between them (tab navigation), localStorage never got written.
  useEffect((): void => {
    setTicketSnapshots((prev) => {
      const updated = {
        ...prev,
        [activeTicketId]: {
          customerName,
          paymentMethod,
          globalDiscountPct,
          cart,
          selectedCartSku,
          amountReceived
        }
      }
      try {
        const state: SavedActiveState = {
          activeTickets,
          activeTicketId,
          ticketSnapshots: updated,
          ticketCounter: ticketCounterRef.current
        }
        localStorage.setItem(ACTIVE_TICKETS_STORAGE_KEY, JSON.stringify(state))
      } catch {
        // storage full or inaccessible — silently ignore
      }
      return updated
    })
  }, [
    activeTicketId,
    amountReceived,
    cart,
    customerName,
    globalDiscountPct,
    paymentMethod,
    selectedCartSku,
    activeTickets
  ])

  function switchActiveTicket(nextTicketId: string): void {
    if (nextTicketId === activeTicketId) return

    const snapshotsWithCurrent = {
      ...ticketSnapshots,
      [activeTicketId]: {
        customerName,
        paymentMethod,
        globalDiscountPct,
        cart,
        selectedCartSku,
        amountReceived
      }
    }
    const nextSnapshot = snapshotsWithCurrent[nextTicketId]
    if (!nextSnapshot) return

    setTicketSnapshots(snapshotsWithCurrent)
    setActiveTicketId(nextTicketId)
    setCart(nextSnapshot.cart)
    setCustomerName(nextSnapshot.customerName)
    setPaymentMethod(nextSnapshot.paymentMethod)
    setGlobalDiscountPct(nextSnapshot.globalDiscountPct)
    setSelectedCartSku(nextSnapshot.selectedCartSku)
    setAmountReceived(nextSnapshot.amountReceived)
    setMessage(
      `Ticket activo cambiado a: ${activeTickets.find((t) => t.id === nextTicketId)?.label ?? nextTicketId}`
    )
  }

  const createNewActiveTicket = useCallback((): void => {
    if (activeTickets.length >= 8) {
      setMessage('Limite alcanzado: maximo 8 tickets activos.')
      return
    }
    ticketCounterRef.current += 1
    const nextNumber = ticketCounterRef.current
    const nextId = `active-${Date.now()}`
    const nextMeta: ActiveTicketMeta = { id: nextId, label: `Activa ${nextNumber}` }

    const snapshotsWithCurrent = {
      ...ticketSnapshots,
      [activeTicketId]: {
        customerName,
        paymentMethod,
        globalDiscountPct,
        cart,
        selectedCartSku,
        amountReceived
      },
      [nextId]: {
        customerName: 'Publico General',
        paymentMethod: 'cash' as PaymentMethod,
        globalDiscountPct: 0,
        cart: [],
        selectedCartSku: null,
        amountReceived: ''
      }
    }

    setActiveTickets((prev) => [...prev, nextMeta].slice(0, 8))
    setTicketSnapshots(snapshotsWithCurrent)
    setActiveTicketId(nextId)
    setCart([])
    setCustomerName('Publico General')
    setPaymentMethod('cash')
    setGlobalDiscountPct(0)
    setSelectedCartSku(null)
    setAmountReceived('')
    setMessage(`Ticket activo creado: ${nextMeta.label}`)
  }, [
    activeTicketId,
    activeTickets,
    amountReceived,
    cart,
    customerName,
    globalDiscountPct,
    paymentMethod,
    selectedCartSku,
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
        !await confirm(`Este ticket tiene ${ticketCart.length} producto(s). ¿Descartar y cerrar?`, { variant: 'warning', title: 'Cerrar ticket' })
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
    setCart(fallbackSnap?.cart ?? [])
    setCustomerName(fallbackSnap?.customerName ?? 'Publico General')
    setPaymentMethod(fallbackSnap?.paymentMethod ?? 'cash')
    setGlobalDiscountPct(fallbackSnap?.globalDiscountPct ?? 0)
    setSelectedCartSku(fallbackSnap?.selectedCartSku ?? null)
    setAmountReceived(fallbackSnap?.amountReceived ?? '')
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
      const effectivePrice = wholesaleMode && product.priceWholesale ? product.priceWholesale : product.price
      setCart((prev) => {
        const _idx = prev.findIndex((item) => item.sku === product.sku)
        if (_idx >= 0) {
          const copy = [...prev]
          const mergedQty = copy[_idx].qty + safeQty
          copy[_idx] = {
            ...copy[_idx],
            qty: mergedQty,
            subtotal: calculateLineSubtotal(copy[_idx].price, mergedQty, copy[_idx].discountPct)
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
      setSelectedCartSku(product.sku)
      setMessage(`Agregado: ${product.name}`)
    },
    [qty, wholesaleMode]
  )

  const addCommonProduct = useCallback(async (): Promise<void> => {
    const nameRaw = await prompt('Nombre del producto comun:', { title: 'Producto comun', placeholder: 'Ej: Servicio de reparacion' })
    if (!nameRaw) return
    const name = nameRaw.trim()
    if (!name) {
      setMessage('Nombre invalido para producto comun.')
      return
    }

    const priceRaw = await prompt('Precio unitario del producto comun:', { title: 'Precio', defaultValue: '0', inputType: 'number', placeholder: '$0.00' })
    if (priceRaw == null) return
    const price = Number(priceRaw)
    if (!Number.isFinite(price) || price <= 0) {
      setMessage('Precio invalido para producto comun.')
      return
    }

    const qtyRaw = await prompt('Cantidad del producto comun:', { title: 'Cantidad', defaultValue: String(Math.max(1, qty)), inputType: 'number', placeholder: '1' })
    if (qtyRaw == null) return
    const commonQty = Math.max(1, Math.floor(Number(qtyRaw)))
    if (!Number.isFinite(commonQty) || commonQty <= 0) {
      setMessage('Cantidad invalida para producto comun.')
      return
    }
    const commonNote = await prompt('Nota opcional del producto comun:', { title: 'Nota (opcional)', defaultValue: '', placeholder: 'Descripcion adicional...' }) ?? ''

    const sku = `COMUN-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
    const item: CartItem = {
      sku,
      name,
      price,
      qty: commonQty,
      discountPct: 0,
      isCommon: true,
      commonNote: commonNote.trim(),
      subtotal: calculateLineSubtotal(price, commonQty, 0)
    }

    setCart((prev) => [...prev, item])
    setSelectedCartSku(sku)
    setMessage(`Producto comun agregado: ${name}`)
  }, [qty, prompt])

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
    if (item && !await confirm(`¿Quitar "${item.name}" del ticket?`, { variant: 'warning', title: 'Quitar producto' })) return
    removeItem(selectedCartSku)
  }, [cart, removeItem, selectedCartSku, confirm])

  const handleCharge = useCallback(async (): Promise<void> => {
    if (chargingRef.current) return
    if (!cart.length) {
      setMessage('No hay productos en el ticket.')
      return
    }
    const shift = readCurrentShift()
    if (!shift) {
      setCurrentShift(null)
      setMessage('No hay turno abierto. Abre un turno en la pestaña Turnos antes de cobrar.')
      return
    }
    // For cash: if no amount entered, assume exact payment
    const effectiveReceived =
      paymentMethod === 'cash' && amountReceivedNum === 0 ? totals.total : amountReceivedNum
    if (paymentMethod === 'cash' && effectiveReceived < totals.total) {
      setMessage(`Monto insuficiente. Falta: $${(totals.total - effectiveReceived).toFixed(2)}`)
      return
    }
    chargingRef.current = true
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
        wholesaleMode
      )
      const folio = saleData.folio ?? saleData.folio_visible ?? ''
      const saleTotal = saleData.total != null ? Number(saleData.total) : totals.total
      const capturedChange = Math.max(0, effectiveReceived - saleTotal)
      setCart([])
      setGlobalDiscountPct(0)
      setSelectedCartSku(null)
      setAmountReceived('')
      setCustomerName('Publico General')
      // Re-read shift from localStorage to avoid stale data after async sale
      const freshShift = readCurrentShift()
      if (freshShift) {
        const updatedShift: ShiftState = {
          ...freshShift,
          salesCount: (freshShift.salesCount ?? 0) + 1,
          totalSales: Math.round(((freshShift.totalSales ?? 0) + saleTotal) * 100) / 100,
          cashSales:
            Math.round(
              ((freshShift.cashSales ?? 0) + (paymentMethod === 'cash' ? saleTotal : 0)) * 100
            ) / 100,
          cardSales:
            Math.round(
              ((freshShift.cardSales ?? 0) + (paymentMethod === 'card' ? saleTotal : 0)) * 100
            ) / 100,
          transferSales:
            Math.round(
              ((freshShift.transferSales ?? 0) + (paymentMethod === 'transfer' ? saleTotal : 0)) *
                100
            ) / 100,
          lastSaleAt: new Date().toISOString()
        }
        try {
          localStorage.setItem(CURRENT_SHIFT_KEY, JSON.stringify(updatedShift))
        } catch {
          /* storage full — shift counters may drift */
        }
        setCurrentShift(updatedShift)
      }
      setMessage(
        paymentMethod === 'cash'
          ? `Venta ${folio} registrada. Cambio: $${capturedChange.toFixed(2)}`
          : `Venta ${folio} registrada correctamente.`
      )

      // Auto-print receipt + auto-open drawer (fire-and-forget)
      try {
        const hwRaw = localStorage.getItem('titan.hwConfig')
        if (hwRaw) {
          const parsed = JSON.parse(hwRaw)
          if (!parsed || typeof parsed !== 'object') throw new Error('invalid hwConfig')
          const hwCfg: HardwareConfig = parsed
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
      } catch {
        /* hw config parse error — non-fatal */
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
  }, [amountReceivedNum, cart, config, customerName, globalDiscountPct, paymentMethod, totals, wholesaleMode])

  function saveCurrentAsPending(): void {
    if (!cart.length) {
      setMessage('No hay items para guardar como pendiente.')
      return
    }
    const label = ticketLabel.trim() || `Ticket-${new Date().toISOString().slice(11, 19)}`
    const pending: PendingTicket = {
      id: `pending-${Date.now()}`,
      label,
      customerName,
      paymentMethod,
      globalDiscountPct,
      cart
    }
    setPendingTickets((prev) => [pending, ...prev].slice(0, 30))
    setCart([])
    setGlobalDiscountPct(0)
    setSelectedCartSku(null)
    setAmountReceived('')
    setTicketLabel('')
    setMessage(`Pendiente guardado: ${label}`)
  }

  function loadPendingTicket(ticketId: string): void {
    const found = pendingTickets.find((item) => item.id === ticketId)
    if (!found) return
    // Save current active ticket state before overwriting
    setTicketSnapshots((prev) => ({
      ...prev,
      [activeTicketId]: {
        customerName,
        paymentMethod,
        globalDiscountPct,
        cart,
        selectedCartSku,
        amountReceived
      }
    }))
    // Look up current prices from products array; fall back to saved price if not found
    const restoredCart = found.cart.map((item) => {
      const currentProduct = products.find((p) => p.sku === item.sku)
      const currentPrice = currentProduct ? currentProduct.price : item.price
      return {
        ...item,
        price: currentPrice,
        subtotal: calculateLineSubtotal(currentPrice, item.qty, item.discountPct)
      }
    })
    setCart(restoredCart)
    setCustomerName(found.customerName)
    const safePm: PaymentMethod = (['cash', 'card', 'transfer'] as const).includes(
      found.paymentMethod as 'cash' | 'card' | 'transfer'
    )
      ? (found.paymentMethod as PaymentMethod)
      : 'cash'
    setPaymentMethod(safePm)
    setGlobalDiscountPct(found.globalDiscountPct)
    setPendingTickets((prev) => prev.filter((item) => item.id !== ticketId))
    setSelectedCartSku(restoredCart[0]?.sku ?? null)
    setAmountReceived('')
    setMessage(`Pendiente cargado: ${found.label}`)
  }

  const firstMatch = filtered[0]

  useEffect((): (() => void) => {
    const onKeyDown = async (event: KeyboardEvent): Promise<void> => {
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
          void handleCharge()
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
          deleteSelectedItem()
          return
        }
      }

      if (!event.ctrlKey) return
      if (isInputFocused) return

      if (key === 'p') {
        event.preventDefault()
        addCommonProduct()
        return
      }

      if (key === 'd') {
        event.preventDefault()
        if (!selectedCartSku) {
          setMessage('Selecciona un producto del carrito para aplicar descuento.')
          return
        }
        const current = cart.find((item) => item.sku === selectedCartSku)
        if (!current) {
          setMessage('El producto seleccionado ya no esta en el carrito.')
          return
        }
        const raw = await prompt(
          'Descuento de producto seleccionado (%):',
          { title: 'Descuento individual', defaultValue: String(current.discountPct ?? 0), inputType: 'number', placeholder: '0' }
        )
        if (raw == null) return
        const parsed = Number(raw)
        if (!Number.isFinite(parsed)) {
          setMessage('Valor de descuento invalido.')
          return
        }
        updateItemDiscount(selectedCartSku, parsed)
        setMessage(`Descuento aplicado al SKU ${selectedCartSku}.`)
        return
      }

      if (key === 'g') {
        event.preventDefault()
        const raw = await prompt('Descuento global de la nota (%):', { title: 'Descuento global', defaultValue: String(globalDiscountPct), inputType: 'number', placeholder: '0' })
        if (raw == null) return
        const parsed = Number(raw)
        if (!Number.isFinite(parsed)) {
          setMessage('Valor de descuento global invalido.')
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
    prompt,
    selectedCartSku,
    updateItemDiscount
  ])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex flex-1 overflow-hidden">

        {/* Left Panel: Ticket (35% width, max 450px) */}
        <div className="w-full md:w-[35%] max-w-[450px] flex flex-col bg-zinc-950 border-r border-zinc-900 z-10 shadow-[4px_0_24px_rgba(0,0,0,0.5)]">
          {/* Ticket Header (Shift + Ticket Actions) */}
          <div className="p-4 border-b border-zinc-900 bg-zinc-950 shrink-0 flex items-center justify-between">
             {/* Ticket tabs/selector */}
             <div className="flex items-center gap-2">
                <select className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs font-bold text-blue-400 focus:outline-none" value={activeTicketId} onChange={(e) => switchActiveTicket(e.target.value)}>
                   {activeTickets.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
                <button onClick={createNewActiveTicket} className="p-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition" title="Nuevo (Ctrl+N)"><Plus className="w-4 h-4" /></button>
                {activeTickets.length > 1 && <button onClick={() => closeActiveTicket(activeTicketId)} className="p-1.5 rounded-lg bg-rose-950/30 text-rose-500 hover:bg-rose-900/50 transition">&times;</button>}
             </div>
             {/* Shift Info & Pending */}
             <div className="flex items-center gap-3">
                {pendingTickets.length > 0 && (
                   <select
                      className="bg-amber-950/30 border border-amber-900/50 rounded-lg px-2 py-1.5 text-xs font-bold text-amber-500 focus:outline-none focus:border-amber-500 cursor-pointer max-w-[120px]"
                      value=""
                      onChange={(e) => { if (e.target.value) loadPendingTicket(e.target.value) }}
                      title="Cargar ticket pendiente"
                   >
                      <option value="">Pendientes ({pendingTickets.length})</option>
                      {pendingTickets.map((t) => (
                         <option key={t.id} value={t.id}>{t.label.substring(0, 10)}...</option>
                      ))}
                   </select>
                )}
                <div className="text-xs font-medium text-zinc-500 flex items-center gap-1.5" title={currentShift ? `Turno: ${currentShift.openedBy}` : 'Sin turno'}>
                   <div className={`w-2 h-2 rounded-full ${currentShift ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                   <span className="max-w-[80px] truncate">{currentShift ? currentShift.openedBy : 'Cerrado'}</span>
                </div>
             </div>
          </div>

          {/* Cart Items List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2 relative hide-scrollbar">
            {cart.length === 0 ? (
               <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-600">
                 <ShoppingCartIcon className="w-12 h-12 mb-3 opacity-20" />
                 <p className="text-sm font-medium">Ticket vacio</p>
               </div>
            ) : (
               cart.map((item, _idx) => (
                  <div key={item.sku} onClick={() => setSelectedCartSku(item.sku)} className={`p-3 rounded-xl border transition-all cursor-pointer ${selectedCartSku === item.sku ? 'bg-blue-600/10 border-blue-500/50' : 'bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700'}`}>
                     <div className="flex justify-between items-start mb-2">
                        <div className="font-semibold text-sm text-zinc-200 leading-tight pr-2">{item.name}</div>
                        <div className="font-bold text-emerald-400 shrink-0">${item.subtotal.toFixed(2)}</div>
                     </div>
                     <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                           <span className="text-zinc-500 font-mono" title={item.sku}>{item.sku.length > 8 ? item.sku.substring(0,8) + '...' : item.sku}</span>
                           <span className="text-zinc-400">${item.price.toFixed(2)} c/u</span>
                        </div>
                        <div className="flex items-center gap-1 bg-zinc-950 rounded-lg p-0.5 border border-zinc-800" onClick={(e) => e.stopPropagation()}>
                           <button onClick={(e) => { e.stopPropagation(); setSelectedCartSku(item.sku); decreaseSelectedQty(); }} className="w-6 h-6 flex items-center justify-center rounded bg-zinc-800 text-zinc-400 hover:text-white">-</button>
                           <span className="w-8 text-center font-bold text-zinc-200">{item.qty}</span>
                           <button onClick={(e) => { e.stopPropagation(); setSelectedCartSku(item.sku); increaseSelectedQty(); }} className="w-6 h-6 flex items-center justify-center rounded bg-zinc-800 text-zinc-400 hover:text-white">+</button>
                           <button onClick={async (e) => { e.stopPropagation(); setSelectedCartSku(item.sku); if (await confirm(`¿Quitar "${item.name}"?`, { variant: 'warning', title: 'Quitar' })) removeItem(item.sku); }} className="w-6 h-6 flex items-center justify-center rounded bg-rose-950/20 text-rose-500/60 hover:text-rose-400 ml-1">&times;</button>
                        </div>
                     </div>
                     {item.discountPct > 0 && <div className="mt-1 text-[10px] font-bold text-rose-400 uppercase tracking-widest">Desc. {item.discountPct}%</div>}
                  </div>
               ))
            )}
          </div>

          {/* Totals & Payment Area (Sticky Bottom) */}
          <div className="shrink-0 bg-zinc-950 border-t border-zinc-900 p-4 pb-6">
             {globalDiscountPct > 0 && (
                <div className="flex justify-between items-center text-xs mb-2">
                   <span className="text-zinc-500 font-bold uppercase tracking-wider">Descuento ({globalDiscountPct}%)</span>
                   <span className="text-rose-400 font-bold">-${totals.globalDiscountAmount.toFixed(2)}</span>
                </div>
             )}
             <div className="flex justify-between items-end mb-4">
                <div className="flex flex-col">
                   <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider mb-1 cursor-pointer hover:text-blue-400 transition" onClick={() => {
                      const name = window.prompt('Nombre del cliente para esta nota:', customerName);
                      if (name !== null) setCustomerName(name || 'Publico General');
                   }}>
                      {customerName === 'Publico General' ? 'Cliente ✏️' : customerName}
                   </span>
                   <span className="text-xs text-zinc-600 font-medium">{cart.reduce((a, i) => a + i.qty, 0)} articulos</span>
                </div>
                <div className="text-4xl font-black text-white tabular-nums tracking-tight">
                   ${totals.total.toFixed(2)}
                </div>
             </div>

             <div className="grid grid-cols-2 gap-2 mb-4 relative group">
                <select className="bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-3 text-sm font-semibold text-zinc-200 focus:outline-none focus:border-blue-500 cursor-pointer" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}>
                   <option value="cash">Efectivo 💵</option>
                   <option value="card">Tarjeta 💳</option>
                   <option value="transfer">Transferencia 🏦</option>
                </select>
                {paymentMethod === 'cash' ? (
                   <input
                      type="number" className="bg-zinc-900 mx-0 border border-zinc-800 rounded-xl px-3 py-3 text-sm font-semibold text-emerald-400 focus:outline-none focus:border-emerald-500 text-right placeholder:text-zinc-600 outline-none hover:bg-zinc-800 transition"
                      placeholder="Recibido..." value={amountReceived} onChange={(e) => setAmountReceived(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void handleCharge() }}
                   />
                ) : (
                   <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl px-3 py-3 flex items-center justify-center text-xs font-medium text-emerald-400/50 cursor-pointer" onClick={() => void handleCharge()}>Cobro Exacto</div>
                )}
             </div>

             {paymentMethod === 'cash' && amountReceivedNum > 0 && (
                <div className="flex justify-between items-center px-1 mb-4">
                   <span className="text-xs font-bold text-zinc-500 uppercase">{pendingAmount > 0 ? 'Faltante' : 'Cambio'}</span>
                   <span className={`text-xl tracking-tight font-bold ${pendingAmount > 0 ? 'text-rose-400' : 'text-amber-400'}`}>${pendingAmount > 0 ? pendingAmount.toFixed(2) : changeDue.toFixed(2)}</span>
                </div>
             )}

             <button
                onClick={() => void handleCharge()} disabled={busy || cart.length === 0}
                className="w-full flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl py-4 font-black text-xl tracking-widest shadow-[0_0_40px_-10px_rgba(37,99,235,0.6)] hover:shadow-[0_0_60px_-10px_rgba(37,99,235,0.8)] transition-all disabled:opacity-50 disabled:shadow-none active:scale-[0.98]"
             >
                {busy ? 'Procesando...' : 'COBRAR'}
             </button>
          </div>
        </div>

        {/* Right Panel: Action Area (Products Grid & Search) */}
        <div className="flex-1 flex flex-col bg-[#09090b] relative">
           {/* Top Search Bar */}
           <div className="p-6 pb-2 shrink-0 border-b border-zinc-900/50">
              <div className="relative max-w-2xl mx-auto flex items-center gap-2">
                 <div className="relative flex-1">
                    <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                    <input
                       ref={searchInputRef}
                       autoFocus
                       className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl py-4 pl-12 pr-12 text-lg font-medium text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/50 focus:bg-zinc-900 focus:ring-4 focus:ring-blue-500/10 transition-all shadow-inner"
                       placeholder="Buscar producto o escanear (F10)..."
                       value={query}
                       onChange={(e) => {
                          lastKeystrokeRef.current = Date.now()
                          setQuery(e.target.value.replace(/[\x00-\x1F\x7F-\x9F]/g, ''))
                       }}
                       onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                             e.preventDefault()
                             e.stopPropagation()

                             const now = Date.now()
                             if (now - lastEnterRef.current < 150) return
                             lastEnterRef.current = now

                             if (!query.trim()) return

                             let scannerMinSpeed = 50
                             let scannerPrefix = ''
                             let scannerSuffix = ''
                             let isScanner = false
                             try {
                               const hwRaw = localStorage.getItem('titan.hwConfig')
                               if (hwRaw) {
                                 const hwCfg = JSON.parse(hwRaw)
                                 if (!hwCfg || typeof hwCfg !== 'object') throw new Error('invalid hwConfig')
                                 if (hwCfg.scanner?.enabled) {
                                   scannerMinSpeed = hwCfg.scanner.min_speed_ms || 50
                                   scannerPrefix = hwCfg.scanner.prefix || ''
                                   scannerSuffix = hwCfg.scanner.suffix || ''
                                   const elapsed = now - lastKeystrokeRef.current
                                   if (elapsed < scannerMinSpeed && query.trim().length > 2) {
                                     isScanner = true
                                   }
                                 }
                               }
                             } catch (_e) { /* parse error */ }

                             let searchTerm = query.trim()
                             if (isScanner) {
                               if (scannerPrefix && searchTerm.startsWith(scannerPrefix)) {
                                 searchTerm = searchTerm.slice(scannerPrefix.length)
                               }
                               if (scannerSuffix && searchTerm.endsWith(scannerSuffix)) {
                                 searchTerm = searchTerm.slice(0, -scannerSuffix.length)
                               }
                               const exact = products.find(
                                 (p) => p.sku.toLowerCase() === searchTerm.toLowerCase()
                               )
                               if (exact) {
                                 addProduct(exact)
                                 setQuery('')
                                 searchInputRef.current?.focus()
                                 return
                               }
                             }
                             if (firstMatch) {
                               addProduct(firstMatch)
                               setQuery('')
                               searchInputRef.current?.focus()
                             }
                             return
                          }
                       }}
                    />
                    {wholesaleMode && (
                       <div className="absolute right-4 top-1/2 -translate-y-1/2 bg-amber-500 text-amber-950 text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded shadow-[0_0_10px_rgba(245,158,11,0.5)] animate-pulse">
                          Mayoreo
                       </div>
                    )}
                 </div>
                 <button onClick={saveCurrentAsPending} disabled={cart.length === 0} className="hidden sm:flex items-center gap-2 bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 font-bold px-4 py-4 rounded-2xl transition-colors shrink-0 disabled:opacity-30 disabled:hover:bg-zinc-800/80" title="Guardar Ticket Pendiente">
                    Pausar
                 </button>
              </div>
           </div>

           {/* Products Grid (Results or Top Products) */}
           <div className="flex-1 overflow-y-auto px-6 py-6 pb-24 relative">
              <div className="max-w-[1400px] mx-auto">
                 <div className="flex items-center justify-between mb-4 px-1">
                    <h2 className="text-sm font-bold tracking-wide text-zinc-400 uppercase">
                       {query.trim() ? 'Resultados de Búsqueda' : 'Catálogo Rápido'}
                    </h2>
                    <span className="text-xs text-zinc-600 font-medium">{filtered.length} items</span>
                 </div>

                 {filtered.length === 0 ? (
                    <div className="text-zinc-500 mt-20 text-center font-medium">Ningún producto coincide con "{query}"</div>
                 ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 lg:gap-4">
                       {filtered.map(p => (
                          <button
                             key={p.sku}
                             onClick={() => { addProduct(p); setQuery(''); searchInputRef.current?.focus(); }}
                             className="flex flex-col text-left bg-zinc-900/60 border border-zinc-800 hover:bg-zinc-800 hover:border-zinc-600 p-4 rounded-2xl transition-all group hover:-translate-y-1 hover:shadow-xl hover:shadow-blue-900/10 active:scale-95"
                          >
                             <div className="font-semibold text-zinc-300 text-xs lg:text-sm mb-2 line-clamp-2 leading-snug group-hover:text-blue-400 transition-colors">{p.name}</div>
                             <div className="mt-auto pt-3 flex items-end justify-between w-full border-t border-zinc-800/50">
                                <div className="font-black text-emerald-400 text-base xl:text-lg">${p.price.toFixed(2)}</div>
                                <div className="text-[10px] font-mono text-zinc-600 truncate max-w-[50%]">{p.sku.substring(0,6)}</div>
                             </div>
                             {p.stock !== undefined && (
                                <div className={`mt-2 text-[9px] font-bold uppercase tracking-wider ${p.stock <= 5 ? 'text-rose-500' : 'text-zinc-600'}`}>
                                   Stock: {p.stock} uds
                                </div>
                             )}
                          </button>
                       ))}
                    </div>
                 )}
              </div>
           </div>

           {/* Keyboard Shortcuts Overlay (Bottom Right) */}
           <div className="absolute bottom-6 right-6 hidden md:flex items-center gap-2 pointer-events-none">
              <div className="bg-zinc-950/80 backdrop-blur border border-zinc-800/80 rounded-xl px-2.5 py-1.5 flex flex-col items-center">
                 <span className="text-[10px] font-bold text-zinc-300 tracking-wider">F10</span>
                 <span className="text-[8px] uppercase tracking-widest text-zinc-500">Buscar</span>
              </div>
              <div className="bg-zinc-950/80 backdrop-blur border border-zinc-800/80 rounded-xl px-2.5 py-1.5 flex flex-col items-center">
                 <span className="text-[10px] font-bold text-zinc-300 tracking-wider">F11</span>
                 <span className="text-[8px] uppercase tracking-widest text-zinc-500">Mayoreo</span>
              </div>
              <div className="bg-zinc-950/80 backdrop-blur border border-zinc-800/80 rounded-xl px-2.5 py-1.5 flex flex-col items-center">
                 <span className="text-[10px] font-bold text-zinc-300 tracking-wider">F12</span>
                 <span className="text-[8px] uppercase tracking-widest text-zinc-500">Cobrar</span>
              </div>
           </div>

           {/* Message Toast (Bottom Left) */}
           {message && message !== 'Cargando productos...' && (
              <div className="absolute bottom-6 left-6 max-w-sm pointer-events-none">
                 <div className="bg-zinc-900/90 backdrop-blur border border-zinc-700/50 shadow-2xl text-zinc-300 text-xs font-semibold px-4 py-3 rounded-xl">
                    {message}
                 </div>
              </div>
           )}
        </div>
      </div>
    </div>
  )
}
