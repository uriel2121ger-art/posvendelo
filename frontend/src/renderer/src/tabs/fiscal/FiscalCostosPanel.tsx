import type { ReactElement } from 'react'
import { useState } from 'react'
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
import type { FiscalPanelProps } from '../../types/fiscalTypes'
import { inputCls, btnPrimary, btnSecondary } from '../../utils/styles'
import { toNumber } from '../../utils/numbers'

const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2'

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
            placeholder="ID de producto"
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
            placeholder="ID de producto"
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
            placeholder="ID de venta"
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
