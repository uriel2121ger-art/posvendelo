import type { ReactElement } from 'react'
import { useState } from 'react'
import type { RuntimeConfig } from '../../posApi'
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
            placeholder='Items JSON [{"amount": 100}]'
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
            Varianza batch
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Climate Shield</h3>
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
            placeholder="Categoría producto"
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
            placeholder="Nombre producto"
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
            placeholder="Merma ID"
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
