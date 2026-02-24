import type { ReactElement } from 'react'
import TopNavbar from './components/TopNavbar'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Banknote, Plus, Search as SearchIcon } from 'lucide-react'
import {
  type RuntimeConfig,
  type SaleItemPayload,
  loadRuntimeConfig,
  saveRuntimeConfig,
  pullTable,
  createSale
} from './posApi'

type Product = {
  id?: number | string
  sku: string
  name: string
  price: number
  stock?: number
}

type CartItem = {
  id?: number | string
  sku: string
  name: string
  price: number
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
const CURRENT_SHIFT_KEY = 'titan.currentShift'

type ShiftState = {
  id: string
  terminalId: number
  openedAt: string
  openedBy: string
  openingCash: number
  status: 'open' | 'closed'
  salesCount?: number
  totalSales?: number
  cashSales?: number
  cardSales?: number
  transferSales?: number
  lastSaleAt?: string
}

function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function clampDiscount(value: number): number {
  return Math.max(0, Math.min(100, value))
}

function readCurrentShift(): ShiftState | null {
  const raw = localStorage.getItem(CURRENT_SHIFT_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as ShiftState
    if (!parsed || parsed.status !== 'open') return null
    return parsed
  } catch {
    return null
  }
}

function calculateLineSubtotal(price: number, qty: number, discountPct: number): number {
  const safeQty = Math.max(1, Math.floor(qty))
  const safeDiscount = clampDiscount(discountPct)
  return price * safeQty * (1 - safeDiscount / 100)
}

function normalizeProduct(raw: Record<string, unknown>): Product | null {
  const sku = String(raw.sku ?? raw.code ?? raw.codigo ?? '').trim()
  const name = String(raw.name ?? raw.nombre ?? '').trim()
  if (!sku || !name) return null
  const price =
    toNumber(raw.price) || toNumber(raw.sale_price) || toNumber(raw.precio) || toNumber(raw.cost)
  return {
    id: (raw.id as number | string | undefined) ?? sku,
    sku,
    name,
    price,
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
  turnId?: number | null
): Promise<Record<string, unknown>> {
  const globalDisc = clampDiscount(globalDiscountPct) / 100
  const items: SaleItemPayload[] = cart.map((item) => {
    // Compound discount: matches how the frontend display calculates totals
    // item.subtotal already has per-item discount applied (price * qty * (1 - itemDisc/100))
    // Then global discount is applied on top: item.subtotal * (1 - globalDisc)
    const fullPrice = item.price * item.qty
    const compoundSubtotal = item.subtotal * (1 - globalDisc)
    const discount = parseFloat(Math.max(0, fullPrice - compoundSubtotal).toFixed(2))
    return {
      product_id: item.isCommon ? null : (Number(item.id) || null),
      name: item.name,
      qty: item.qty,
      price: item.price,
      discount,
      is_wholesale: false,
      price_includes_tax: true
    }
  })
  const res = await createSale(cfg, {
    items,
    payment_method: paymentMethod,
    cash_received: paymentMethod === 'cash' ? (amountReceived ?? 0) : 0,
    serie: 'A',
    turn_id: turnId ?? undefined
  })
  const data = (res.data ?? res) as Record<string, unknown>
  return data
}

export default function Terminal(): ReactElement {
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const [config, setConfig] = useState<RuntimeConfig>(() => loadRuntimeConfig())
  const [products, setProducts] = useState<Product[]>([])
  const [cart, setCart] = useState<CartItem[]>([])
  const [customerName, setCustomerName] = useState('Publico General')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash')
  const [amountReceived, setAmountReceived] = useState('')
  const [globalDiscountPct, setGlobalDiscountPct] = useState(0)
  const [pendingTickets, setPendingTickets] = useState<PendingTicket[]>([])
  const [activeTickets, setActiveTickets] = useState<ActiveTicketMeta[]>([
    { id: 'active-1', label: 'Activa 1' }
  ])
  const [activeTicketId, setActiveTicketId] = useState('active-1')
  const [ticketSnapshots, setTicketSnapshots] = useState<Record<string, ActiveTicketSnapshot>>({
    'active-1': {
      customerName: 'Publico General',
      paymentMethod: 'cash',
      globalDiscountPct: 0,
      cart: [],
      selectedCartSku: null,
      amountReceived: ''
    }
  })
  const [selectedCartSku, setSelectedCartSku] = useState<string | null>(null)
  const ticketCounterRef = useRef(1)
  const [ticketLabel, setTicketLabel] = useState('')
  const [query, setQuery] = useState('')
  const [qty, setQty] = useState(1)
  const [busy, setBusy] = useState(false)
  const [currentShift, setCurrentShift] = useState<ShiftState | null>(() => readCurrentShift())
  const [message, setMessage] = useState('Configura URL/token y carga productos para comenzar.')

  useEffect((): void => {
    saveRuntimeConfig(config)
  }, [config])

  useEffect((): void => {
    const raw = localStorage.getItem(PENDING_TICKETS_STORAGE_KEY)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw) as PendingTicket[]
      if (Array.isArray(parsed)) setPendingTickets(parsed)
    } catch {
      // ignore invalid stored payload
    }
  }, [])

  useEffect((): void => {
    localStorage.setItem(PENDING_TICKETS_STORAGE_KEY, JSON.stringify(pendingTickets))
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
    const subtotalBeforeDiscount = cart.reduce((acc, item) => acc + item.subtotal, 0)
    const globalDiscountAmount = subtotalBeforeDiscount * (clampDiscount(globalDiscountPct) / 100)
    // Prices already include IVA — total is the sum minus discount (NOT plus tax)
    const total = subtotalBeforeDiscount - globalDiscountAmount
    // Extract IVA that's already baked into the prices (informational for display)
    const tax = total - total / (1 + TAX_RATE)
    const subtotal = total - tax
    return { subtotalBeforeDiscount, globalDiscountAmount, subtotal, tax, total }
  }, [cart, globalDiscountPct])
  const amountReceivedNum = toNumber(amountReceived)
  const changeDue = Math.max(0, amountReceivedNum - totals.total)
  const pendingAmount = Math.max(0, totals.total - amountReceivedNum)

  useEffect((): void => {
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
  }, [
    activeTicketId,
    amountReceived,
    cart,
    customerName,
    globalDiscountPct,
    paymentMethod,
    selectedCartSku
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

  function closeActiveTicket(ticketId: string): void {
    if (activeTickets.length <= 1) {
      setMessage('Debe existir al menos un ticket activo.')
      return
    }

    const remaining = activeTickets.filter((t) => t.id !== ticketId)
    const restSnapshots = Object.fromEntries(
      Object.entries(ticketSnapshots).filter(([id]) => id !== ticketId)
    ) as Record<string, ActiveTicketSnapshot>
    setActiveTickets(remaining)
    setTicketSnapshots(restSnapshots)

    if (ticketId !== activeTicketId) {
      setMessage('Ticket activo cerrado.')
      return
    }

    const fallback = remaining[0]
    if (!fallback) return
    const snapshot = restSnapshots[fallback.id]
    setActiveTicketId(fallback.id)
    setCart(snapshot?.cart ?? [])
    setCustomerName(snapshot?.customerName ?? 'Publico General')
    setPaymentMethod(snapshot?.paymentMethod ?? 'cash')
    setGlobalDiscountPct(snapshot?.globalDiscountPct ?? 0)
    setSelectedCartSku(snapshot?.selectedCartSku ?? null)
    setAmountReceived(snapshot?.amountReceived ?? '')
    setMessage(`Ticket activo cerrado. Cambiado a ${fallback.label}.`)
  }

  function updateItemQty(sku: string, nextQty: number): void {
    setCart((prev) =>
      prev.map((item) =>
        item.sku === sku
          ? {
              ...item,
              qty: Math.max(1, Math.floor(nextQty)),
              subtotal: calculateLineSubtotal(
                item.price,
                Math.max(1, Math.floor(nextQty)),
                item.discountPct
              )
            }
          : item
      )
    )
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
      setCart((prev) => {
        const idx = prev.findIndex((item) => item.sku === product.sku)
        if (idx >= 0) {
          const copy = [...prev]
          const mergedQty = copy[idx].qty + safeQty
          copy[idx] = {
            ...copy[idx],
            qty: mergedQty,
            subtotal: calculateLineSubtotal(copy[idx].price, mergedQty, copy[idx].discountPct)
          }
          return copy
        }
        return [
          ...prev,
          {
            ...product,
            qty: safeQty,
            discountPct: 0,
            isCommon: false,
            subtotal: calculateLineSubtotal(product.price, safeQty, 0)
          }
        ]
      })
      setSelectedCartSku(product.sku)
      setMessage(`Agregado: ${product.name}`)
    },
    [qty]
  )

  const addCommonProduct = useCallback((): void => {
    const nameRaw = window.prompt('Nombre del producto comun:')
    if (!nameRaw) return
    const name = nameRaw.trim()
    if (!name) {
      setMessage('Nombre invalido para producto comun.')
      return
    }

    const priceRaw = window.prompt('Precio unitario del producto comun:', '0')
    if (priceRaw == null) return
    const price = Number(priceRaw)
    if (!Number.isFinite(price) || price <= 0) {
      setMessage('Precio invalido para producto comun.')
      return
    }

    const qtyRaw = window.prompt('Cantidad del producto comun:', String(Math.max(1, qty)))
    if (qtyRaw == null) return
    const commonQty = Math.max(1, Math.floor(Number(qtyRaw)))
    if (!Number.isFinite(commonQty) || commonQty <= 0) {
      setMessage('Cantidad invalida para producto comun.')
      return
    }
    const commonNote = window.prompt('Nota opcional del producto comun:', '') ?? ''

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
  }, [qty])

  const removeItem = useCallback(
    (sku: string): void => {
      setCart((prev) => prev.filter((item) => item.sku !== sku))
      setSelectedCartSku((current) => (current === sku ? null : current))
    },
    []
  )

  const increaseSelectedQty = useCallback((): void => {
    if (!selectedCartSku) {
      setMessage('Selecciona un producto del carrito.')
      return
    }
    const current = cart.find((item) => item.sku === selectedCartSku)
    if (!current) return
    updateItemQty(selectedCartSku, current.qty + 1)
  }, [cart, selectedCartSku])

  const decreaseSelectedQty = useCallback((): void => {
    if (!selectedCartSku) {
      setMessage('Selecciona un producto del carrito.')
      return
    }
    const current = cart.find((item) => item.sku === selectedCartSku)
    if (!current) return
    updateItemQty(selectedCartSku, Math.max(1, current.qty - 1))
  }, [cart, selectedCartSku])

  const deleteSelectedItem = useCallback((): void => {
    if (!selectedCartSku) {
      setMessage('Selecciona un producto del carrito.')
      return
    }
    removeItem(selectedCartSku)
  }, [removeItem, selectedCartSku])

  async function handleLoadProducts(): Promise<void> {
    if (!config.token.trim()) {
      setMessage('Falta token de API.')
      return
    }
    setBusy(true)
    try {
      const data = await fetchProducts(config)
      setProducts(data)
      setMessage(`Productos cargados: ${data.length}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const handleCharge = useCallback(async (): Promise<void> => {
    if (!cart.length) {
      setMessage('No hay productos en el ticket.')
      return
    }
    const shift = readCurrentShift()
    if (!shift) {
      setCurrentShift(null)
      setMessage('No hay turno abierto. Abre turno en F5 antes de cobrar.')
      return
    }
    if (paymentMethod === 'cash' && amountReceivedNum < totals.total) {
      setMessage(`Monto insuficiente. Falta: $${pendingAmount.toFixed(2)}`)
      return
    }
    setBusy(true)
    try {
      const turnId = shift.id ? Number(shift.id) || null : null
      const saleData = await syncSale(
        config,
        cart,
        customerName,
        paymentMethod,
        globalDiscountPct,
        paymentMethod === 'cash' ? amountReceivedNum : undefined,
        turnId
      )
      const folio = saleData.folio ?? saleData.folio_visible ?? ''
      const saleTotal = Number(saleData.total) || totals.total
      const capturedChange = changeDue
      setCart([])
      setGlobalDiscountPct(0)
      setSelectedCartSku(null)
      setAmountReceived('')
      const updatedShift: ShiftState = {
        ...shift,
        salesCount: (shift.salesCount ?? 0) + 1,
        totalSales: (shift.totalSales ?? 0) + saleTotal,
        cashSales: (shift.cashSales ?? 0) + (paymentMethod === 'cash' ? saleTotal : 0),
        cardSales: (shift.cardSales ?? 0) + (paymentMethod === 'card' ? saleTotal : 0),
        transferSales:
          (shift.transferSales ?? 0) + (paymentMethod === 'transfer' ? saleTotal : 0),
        lastSaleAt: new Date().toISOString()
      }
      localStorage.setItem(CURRENT_SHIFT_KEY, JSON.stringify(updatedShift))
      setCurrentShift(updatedShift)
      setMessage(
        paymentMethod === 'cash'
          ? `Venta ${folio} registrada. Cambio: $${capturedChange.toFixed(2)}`
          : `Venta ${folio} registrada correctamente.`
      )
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }, [
    amountReceivedNum,
    cart,
    changeDue,
    config,
    customerName,
    globalDiscountPct,
    paymentMethod,
    pendingAmount,
    totals
  ])

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
    setCart(found.cart)
    setCustomerName(found.customerName)
    setPaymentMethod(found.paymentMethod)
    setGlobalDiscountPct(found.globalDiscountPct)
    setPendingTickets((prev) => prev.filter((item) => item.id !== ticketId))
    setSelectedCartSku(found.cart[0]?.sku ?? null)
    setAmountReceived('')
    setMessage(`Pendiente cargado: ${found.label}`)
  }

  const firstMatch = filtered[0]

  useEffect((): (() => void) => {
    const onKeyDown = (event: KeyboardEvent): void => {
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
        const raw = window.prompt(
          'Descuento de producto seleccionado (%):',
          String(current?.discountPct ?? 0)
        )
        if (raw == null) return
        updateItemDiscount(selectedCartSku, Number(raw))
        setMessage(`Descuento aplicado al SKU ${selectedCartSku}.`)
        return
      }

      if (key === 'g') {
        event.preventDefault()
        const raw = window.prompt('Descuento global de la nota (%):', String(globalDiscountPct))
        if (raw == null) return
        setGlobalDiscountPct(clampDiscount(Number(raw)))
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
    selectedCartSku,
    updateItemDiscount
  ])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <TopNavbar />
      <div className="border-b border-zinc-800 bg-zinc-900/80 p-5 mt-4 shadow-sm rounded-xl mx-4 mb-2">
        <h2 className="mb-4 text-xl font-bold text-blue-400 px-1">Configuración y Recepción</h2>

        <div className="grid grid-cols-1 gap-2 md:grid-cols-7">
          <input
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            value={config.baseUrl}
            onChange={(e) => setConfig((prev) => ({ ...prev, baseUrl: e.target.value }))}
            placeholder="Base URL"
          />
          <input
            type="password"
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            value={config.token}
            onChange={(e) => setConfig((prev) => ({ ...prev, token: e.target.value }))}
            placeholder="Token"
          />
          <input
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            type="number"
            value={config.terminalId}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                terminalId: Math.max(1, Number(e.target.value || 1))
              }))
            }
            placeholder="Terminal ID"
          />
          <input
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            placeholder="Cliente en ticket"
          />
          <select
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
          >
            <option value="cash">Efectivo</option>
            <option value="card">Tarjeta</option>
            <option value="transfer">Transferencia</option>
          </select>
          <input
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            type="number"
            min={0}
            value={amountReceived}
            onChange={(e) => setAmountReceived(e.target.value)}
            placeholder="Monto recibido"
            disabled={paymentMethod !== 'cash'}
          />
          <button
            className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
            onClick={() => void handleLoadProducts()}
            disabled={busy}
          >
            {busy ? 'Cargando...' : 'Cargar productos'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 border-b border-zinc-800 bg-zinc-900/80 p-5 mt-2 shadow-sm rounded-xl mx-4 md:grid-cols-[1fr_auto_auto]">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-zinc-400" />
          <input
            autoFocus
            ref={searchInputRef}
            className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 pl-10 pr-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
            placeholder="Buscar por SKU o nombre"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <input
          className="w-32 rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold text-center focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, Number(e.target.value || 1)))}
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => firstMatch && addProduct(firstMatch)}
          disabled={!firstMatch || busy}
        >
          <Plus className="h-4 w-4" /> Agregar primero
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900/80 p-5 mt-2 shadow-sm rounded-xl mx-4 md:grid-cols-[1fr_180px_180px_220px]">
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={ticketLabel}
          onChange={(e) => setTicketLabel(e.target.value)}
          placeholder="Nombre ticket pendiente (opcional)"
        />
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={saveCurrentAsPending}
          disabled={busy || cart.length === 0}
        >
          Guardar pendiente
        </button>
        <input
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          type="number"
          min={0}
          max={100}
          value={globalDiscountPct}
          onChange={(e) => setGlobalDiscountPct(clampDiscount(Number(e.target.value || 0)))}
          placeholder="Descuento global %"
        />
        <select
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value=""
          onChange={(e) => {
            const value = e.target.value
            if (!value) return
            loadPendingTicket(value)
            e.target.value = ''
          }}
        >
          <option value="">Cargar ticket pendiente...</option>
          {pendingTickets.map((ticket) => (
            <option key={ticket.id} value={ticket.id}>
              {ticket.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900/80 p-5 mt-2 shadow-sm rounded-xl mx-4 md:grid-cols-[1fr_auto_auto]">
        <select
          className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"
          value={activeTicketId}
          onChange={(e) => switchActiveTicket(e.target.value)}
        >
          {activeTickets.map((ticket) => (
            <option key={ticket.id} value={ticket.id}>
              {ticket.label}
            </option>
          ))}
        </select>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"
          onClick={createNewActiveTicket}
          disabled={busy || activeTickets.length >= 8}
        >
          Nuevo ticket activo (Ctrl+N)
        </button>
        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
          onClick={() => closeActiveTicket(activeTicketId)}
          disabled={busy || activeTickets.length <= 1}
        >
          Cerrar ticket activo
        </button>
      </div>

      <div className="grid grid-cols-1 gap-2 border-b border-zinc-800 bg-zinc-900/80 p-5 mt-2 shadow-sm rounded-xl mx-4 md:grid-cols-4">
        <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm">
          <span className="text-zinc-400">Turno</span>
          <div className="font-semibold">
            {currentShift ? `Abierto (${currentShift.openedBy})` : 'Sin turno'}
          </div>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm">
          <span className="text-zinc-400">Ventas turno</span>
          <div className="font-semibold">{currentShift?.salesCount ?? 0}</div>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm">
          <span className="text-zinc-400">Total turno</span>
          <div className="font-semibold">${(currentShift?.totalSales ?? 0).toFixed(2)}</div>
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm">
          <span className="text-zinc-400">Efectivo turno</span>
          <div className="font-semibold">${(currentShift?.cashSales ?? 0).toFixed(2)}</div>
        </div>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)] md:grid-cols-[1fr_400px]">
        <div className="overflow-hidden rounded border border-zinc-800">
          <div className="grid grid-cols-12 gap-2 border-b border-zinc-800 bg-zinc-900/80 px-4 py-3 text-xs font-bold uppercase tracking-wider text-zinc-500">
            <div className="col-span-3">SKU</div>
            <div className="col-span-5">Producto</div>
            <div className="col-span-2 text-right">Precio</div>
            <div className="col-span-2 text-right">Stock</div>
          </div>
          <div className="max-h-[38vh] overflow-y-auto bg-zinc-950">
            {filtered.map((p) => (
              <button
                key={`${p.sku}-${p.id ?? ''}`}
                className="grid w-full grid-cols-12 gap-2 border-b border-zinc-800/50 px-4 py-4 text-left text-sm cursor-pointer transition-colors hover:bg-zinc-800/40"
                onClick={() => addProduct(p)}
              >
                <div className="col-span-3 font-mono text-zinc-300">{p.sku}</div>
                <div className="col-span-5">{p.name}</div>
                <div className="col-span-2 text-right">${p.price.toFixed(2)}</div>
                <div className="col-span-2 text-right">{p.stock ?? 0}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col overflow-hidden rounded border border-zinc-800 bg-zinc-900">
          <div className="border-b border-zinc-800 px-4 py-3 font-semibold">Ticket actual</div>
          <div className="flex-1 overflow-y-auto px-4 py-2">
            {cart.length === 0 && (
              <p className="text-sm text-zinc-400">Sin productos en carrito.</p>
            )}
            {cart.map((item) => (
              <div
                key={item.sku}
                className={`mb-2 rounded border p-2 text-sm ${
                  selectedCartSku === item.sku
                    ? 'border-blue-500 bg-zinc-900'
                    : 'border-zinc-800 bg-zinc-950'
                }`}
                onClick={() => setSelectedCartSku(item.sku)}
              >
                <div className="font-semibold">{item.name}</div>
                {item.isCommon && item.commonNote && (
                  <div className="mt-1 text-xs text-amber-300">Nota: {item.commonNote}</div>
                )}
                <div className="mt-1 flex items-center justify-between text-zinc-300">
                  <span>{item.sku}</span>
                  <span>
                    {item.qty} x ${item.price.toFixed(2)}
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-zinc-300">
                  <label className="flex items-center gap-2">
                    Cant:
                    <input
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 font-semibold text-blue-300 focus:border-blue-500 focus:outline-none"
                      type="number"
                      min={1}
                      value={item.qty}
                      onChange={(e) => updateItemQty(item.sku, Number(e.target.value || 1))}
                    />
                  </label>
                  <label className="flex items-center gap-2">
                    Desc %:
                    <input
                      className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 font-semibold text-blue-300 focus:border-blue-500 focus:outline-none"
                      type="number"
                      min={0}
                      max={100}
                      value={item.discountPct}
                      onChange={(e) => updateItemDiscount(item.sku, Number(e.target.value || 0))}
                    />
                  </label>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="font-mono text-blue-300">${item.subtotal.toFixed(2)}</span>
                  <button
                    className="text-xs text-rose-400 hover:text-rose-300"
                    onClick={() => removeItem(item.sku)}
                  >
                    Quitar
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-zinc-800 px-4 py-3 text-sm">
            <div className="mb-1 flex justify-between">
              <span>Subtotal</span>
              <span>${totals.subtotalBeforeDiscount.toFixed(2)}</span>
            </div>
            {globalDiscountPct > 0 && (
              <div className="mb-1 flex justify-between text-rose-400">
                <span>Desc. global ({clampDiscount(globalDiscountPct).toFixed(0)}%)</span>
                <span>-${totals.globalDiscountAmount.toFixed(2)}</span>
              </div>
            )}
            <div className="mb-3 flex justify-between text-lg font-bold text-emerald-400">
              <span>Total</span>
              <span>${totals.total.toFixed(2)}</span>
            </div>
            <div className="mb-1 flex justify-between text-xs text-zinc-500">
              <span>IVA incluido</span>
              <span>${totals.tax.toFixed(2)}</span>
            </div>
            {paymentMethod === 'cash' && (
              <>
                <div className="mb-1 flex justify-between">
                  <span>Recibido</span>
                  <span>${amountReceivedNum.toFixed(2)}</span>
                </div>
                <div className="mb-1 flex justify-between">
                  <span>Faltante</span>
                  <span>${pendingAmount.toFixed(2)}</span>
                </div>
                <div className="mb-3 flex justify-between font-semibold text-amber-300">
                  <span>Cambio</span>
                  <span>${changeDue.toFixed(2)}</span>
                </div>
              </>
            )}
            <button
              className="flex w-full mt-4 items-center justify-center gap-2 rounded-xl bg-blue-600 py-4 font-bold text-lg tracking-wide text-white shadow-[0_0_20px_rgba(37,99,235,0.4)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0 disabled:shadow-none"
              onClick={() => void handleCharge()}
              disabled={busy || cart.length === 0}
            >
              <Banknote className="h-5 w-5" /> {busy ? 'Procesando...' : 'Cobrar y sincronizar'}
            </button>
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
        {message}
      </div>
    </div>
  )
}
