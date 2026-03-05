import type { ReactElement } from 'react'
import { useState } from 'react'
import type { RuntimeConfig } from '../../posApi'
import {
  registerCostPurchase,
  getCostDualView,
  getCostFiscal,
  getCostReal,
  getCostProfit,
  getCostGlobalReport,
  satCatalogSearch,
  satCatalogDescription
} from '../../posApi'

export interface FiscalPanelProps {
  cfg: () => RuntimeConfig
  busy: boolean
  wrap: (fn: () => Promise<Record<string, unknown>>) => Promise<void>
  canAdmin: boolean
}

const inputCls =
  'w-full rounded-lg border border-zinc-800 bg-zinc-900/80 py-2 px-3 text-sm font-medium text-zinc-200 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition placeholder:text-zinc-600'
const btnPrimary =
  'flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-bold text-sm text-white hover:bg-blue-500 transition disabled:opacity-50'
const btnSecondary =
  'flex items-center justify-center gap-2 rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-2 font-bold text-sm text-zinc-300 hover:bg-zinc-700 hover:text-white transition disabled:opacity-50'
const cardCls = 'rounded-xl border border-zinc-800 bg-zinc-900/50 p-4'
const labelCls = 'text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2'

function toNumber(value: string): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function FiscalCostosPanel({ cfg, busy, wrap }: FiscalPanelProps): ReactElement {
  const [productId, setProductId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [serie, setSerie] = useState('A')
  const [supplier, setSupplier] = useState('')
  const [invoice, setInvoice] = useState('')
  const [saleId, setSaleId] = useState('')
  const [satQuery, setSatQuery] = useState('')
  const [satClave, setSatClave] = useState('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Registrar compra (costos)</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input
            className={inputCls}
            placeholder="Product ID"
            type="number"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Cantidad"
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Costo unitario"
            type="number"
            value={unitCost}
            onChange={(e) => setUnitCost(e.target.value)}
          />
          <select className={inputCls} value={serie} onChange={(e) => setSerie(e.target.value)}>
            <option value="A">Serie A</option>
            <option value="B">Serie B</option>
          </select>
          <input
            className={inputCls}
            placeholder="Proveedor (opcional)"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Factura (opcional)"
            value={invoice}
            onChange={(e) => setInvoice(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !productId.trim()}
            onClick={() =>
              void wrap(() =>
                registerCostPurchase(cfg(), {
                  product_id: toNumber(productId),
                  quantity: toNumber(quantity),
                  unit_cost: toNumber(unitCost),
                  serie,
                  supplier: supplier.trim() || undefined,
                  invoice: invoice.trim() || undefined
                })
              )
            }
          >
            Registrar
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Vistas de costo por producto</h3>
        <div className="flex gap-2 flex-wrap">
          <input
            className={inputCls + ' max-w-[120px]'}
            placeholder="Product ID"
            type="number"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !productId.trim()}
            onClick={() => void wrap(() => getCostDualView(cfg(), toNumber(productId)))}
          >
            Vista dual
          </button>
          <button
            className={btnSecondary}
            disabled={busy || !productId.trim()}
            onClick={() => void wrap(() => getCostFiscal(cfg(), toNumber(productId)))}
          >
            Costo fiscal
          </button>
          <button
            className={btnSecondary}
            disabled={busy || !productId.trim()}
            onClick={() => void wrap(() => getCostReal(cfg(), toNumber(productId)))}
          >
            Costo real
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Utilidad por venta</h3>
        <div className="flex gap-2">
          <input
            className={inputCls + ' max-w-[140px]'}
            placeholder="Sale ID"
            type="number"
            value={saleId}
            onChange={(e) => setSaleId(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !saleId.trim()}
            onClick={() => void wrap(() => getCostProfit(cfg(), toNumber(saleId)))}
          >
            Utilidad
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getCostGlobalReport(cfg()))}
          >
            Reporte global
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Catálogo SAT</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input
            className={inputCls}
            placeholder="Buscar (texto)"
            value={satQuery}
            onChange={(e) => setSatQuery(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !satQuery.trim()}
            onClick={() => void wrap(() => satCatalogSearch(cfg(), satQuery.trim()))}
          >
            Buscar
          </button>
          <input
            className={inputCls}
            placeholder="Clave SAT (descripción)"
            value={satClave}
            onChange={(e) => setSatClave(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !satClave.trim()}
            onClick={() => void wrap(() => satCatalogDescription(cfg(), satClave.trim()))}
          >
            Descripción
          </button>
        </div>
      </div>
    </div>
  )
}
