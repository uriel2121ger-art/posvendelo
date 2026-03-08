import type { ReactElement } from 'react'
import { useState } from 'react'
import {
  calculateSmartLoss,
  suggestOptimalCast,
  generateBatchVariance,
  getSeasonalFactor,
  getCurrentClimate,
  evaluateDegradationRisk,
  generateShrinkageJustification,
  attachClimateToMerma
} from '../../posApi'
import type { FiscalPanelProps } from '../../types/fiscalTypes'
import { inputCls, btnPrimary, btnSecondary } from '../../utils/styles'
import { toNumber } from '../../utils/numbers'

const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2'

export default function FiscalAnalyticsPanel({ cfg, busy, wrap }: FiscalPanelProps): ReactElement {
  const [baseAmount, setBaseAmount] = useState('')
  const [category, setCategory] = useState('general')
  const [batchItems, setBatchItems] = useState('')
  const [totalTarget, setTotalTarget] = useState('')
  const [climateCategory, setClimateCategory] = useState('')
  const [prodName, setProdName] = useState('')
  const [prodQty, setProdQty] = useState('')
  const [prodCategory, setProdCategory] = useState('deterioro')
  const [mermaId, setMermaId] = useState('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Varianza de precios</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <input
            className={inputCls}
            type="number"
            placeholder="Monto base"
            value={baseAmount}
            onChange={(e) => setBaseAmount(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Categoría"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !baseAmount.trim()}
            onClick={() =>
              void wrap(() =>
                calculateSmartLoss(cfg(), {
                  base_amount: toNumber(baseAmount),
                  category: category.trim()
                })
              )
            }
          >
            Pérdida inteligente
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => suggestOptimalCast(cfg()))}
          >
            CAST óptimo
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getSeasonalFactor(cfg()))}
          >
            Factor estacional
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input
            className={inputCls}
            placeholder='Artículos JSON [{"amount": 100}]'
            value={batchItems}
            onChange={(e) => setBatchItems(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Total objetivo"
            value={totalTarget}
            onChange={(e) => setTotalTarget(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !batchItems.trim() || !totalTarget.trim()}
            onClick={() => {
              let items: unknown[] = []
              try {
                items = JSON.parse(batchItems)
              } catch {
                /* invalid */
              }
              void wrap(() =>
                generateBatchVariance(cfg(), {
                  items,
                  total_target: toNumber(totalTarget)
                })
              )
            }}
          >
            Varianza por lote
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Escudo climático</h3>
        <div className="flex gap-2 flex-wrap mb-3">
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getCurrentClimate(cfg()))}
          >
            Clima actual
          </button>
          <input
            className={inputCls + ' max-w-[180px]'}
            placeholder="Categoría de producto"
            value={climateCategory}
            onChange={(e) => setClimateCategory(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                evaluateDegradationRisk(cfg(), {
                  climate: {},
                  product_category: climateCategory.trim() || undefined
                })
              )
            }
          >
            Evaluar riesgo
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <input
            className={inputCls}
            placeholder="Nombre de producto"
            value={prodName}
            onChange={(e) => setProdName(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Cantidad"
            value={prodQty}
            onChange={(e) => setProdQty(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Categoría"
            value={prodCategory}
            onChange={(e) => setProdCategory(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !prodName.trim()}
            onClick={() =>
              void wrap(() =>
                generateShrinkageJustification(cfg(), {
                  product_name: prodName.trim(),
                  quantity: toNumber(prodQty),
                  category: prodCategory.trim(),
                  id: undefined
                })
              )
            }
          >
            Justificación merma
          </button>
        </div>
        <div className="flex gap-2">
          <input
            className={inputCls + ' max-w-[100px]'}
            type="number"
            placeholder="ID de merma"
            value={mermaId}
            onChange={(e) => setMermaId(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !mermaId.trim()}
            onClick={() => void wrap(() => attachClimateToMerma(cfg(), toNumber(mermaId)))}
          >
            Adjuntar clima a merma
          </button>
        </div>
      </div>
    </div>
  )
}
