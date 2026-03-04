import type { ReactElement } from 'react'
import { useState } from 'react'
import type { RuntimeConfig } from '../../posApi'
import {
  selectOptimalRfc,
  processCrossInvoice,
  getJitterRandomTime,
  distributeTimbrados,
  getOptimalNoise,
  generateNoiseTransaction,
  startDailyNoise
} from '../../posApi'

export interface FiscalPanelProps {
  cfg: () => RuntimeConfig
  busy: boolean
  wrap: (fn: () => Promise<Record<string, unknown>>) => Promise<void>
  canAdmin: boolean
}

const inputCls =
  'w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600'
const btnPrimary =
  'flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white hover:bg-blue-500 transition-all disabled:opacity-50'
const btnSecondary =
  'flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 hover:bg-zinc-700 transition-all disabled:opacity-50'
const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1'

function toNumber(value: string): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function FiscalOperacionesPanel({
  cfg,
  busy,
  wrap,
  canAdmin
}: FiscalPanelProps): ReactElement {
  const [intercompanyAmount, setIntercompanyAmount] = useState('')
  const [originalRfc, setOriginalRfc] = useState('')
  const [branchName, setBranchName] = useState('')
  const [crossSaleId, setCrossSaleId] = useState('')
  const [targetRfc, setTargetRfc] = useState('')
  const [crossConcept, setCrossConcept] = useState('')
  const [jitterCount, setJitterCount] = useState('')
  const [jitterHours, setJitterHours] = useState('8')
  const [noiseRfc, setNoiseRfc] = useState('')
  const [noiseTarget, setNoiseTarget] = useState('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Intercompany / RFC óptimo</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <input
            className={inputCls}
            type="number"
            placeholder="Monto"
            value={intercompanyAmount}
            onChange={(e) => setIntercompanyAmount(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="RFC original (opcional)"
            value={originalRfc}
            onChange={(e) => setOriginalRfc(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Sucursal (opcional)"
            value={branchName}
            onChange={(e) => setBranchName(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !intercompanyAmount.trim() || !canAdmin}
            onClick={() =>
              void wrap(() =>
                selectOptimalRfc(cfg(), {
                  amount: toNumber(intercompanyAmount),
                  original_rfc: originalRfc.trim() || undefined,
                  branch_name: branchName.trim() || undefined
                })
              )
            }
          >
            Seleccionar RFC
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input
            className={inputCls}
            type="number"
            placeholder="Sale ID"
            value={crossSaleId}
            onChange={(e) => setCrossSaleId(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="RFC destino"
            value={targetRfc}
            onChange={(e) => setTargetRfc(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="RFC origen"
            value={originalRfc}
            onChange={(e) => setOriginalRfc(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Concepto cruzado"
            value={crossConcept}
            onChange={(e) => setCrossConcept(e.target.value)}
          />
          <button
            className={`${btnPrimary} col-span-2 md:col-span-1`}
            disabled={
              busy ||
              !crossSaleId.trim() ||
              !targetRfc.trim() ||
              !originalRfc.trim() ||
              !crossConcept.trim() ||
              !canAdmin
            }
            onClick={() =>
              void wrap(() =>
                processCrossInvoice(cfg(), {
                  sale_id: toNumber(crossSaleId),
                  target_rfc: targetRfc.trim(),
                  original_rfc: originalRfc.trim(),
                  cross_concept: crossConcept.trim()
                })
              )
            }
          >
            Procesar factura cruzada
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Jitter / RFC rotation</h3>
        <div className="flex gap-2 flex-wrap">
          <button
            className={btnSecondary}
            disabled={busy || !canAdmin}
            onClick={() => void wrap(() => getJitterRandomTime(cfg()))}
          >
            Tiempo aleatorio
          </button>
          <input
            className={inputCls + ' max-w-[100px]'}
            type="number"
            placeholder="Cantidad"
            value={jitterCount}
            onChange={(e) => setJitterCount(e.target.value)}
          />
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Horas"
            value={jitterHours}
            onChange={(e) => setJitterHours(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !jitterCount.trim() || !canAdmin}
            onClick={() =>
              void wrap(() =>
                distributeTimbrados(cfg(), {
                  count: toNumber(jitterCount),
                  hours: toNumber(jitterHours) || 8
                })
              )
            }
          >
            Distribuir timbrados
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Ruido fiscal</h3>
        <div className="flex gap-2 flex-wrap">
          <button
            className={btnSecondary}
            disabled={busy || !canAdmin}
            onClick={() => void wrap(() => getOptimalNoise(cfg()))}
          >
            Ruido óptimo
          </button>
          <input
            className={inputCls + ' max-w-[140px]'}
            placeholder="RFC (opcional)"
            value={noiseRfc}
            onChange={(e) => setNoiseRfc(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !canAdmin}
            onClick={() =>
              void wrap(() =>
                generateNoiseTransaction(cfg(), noiseRfc.trim() ? { rfc: noiseRfc.trim() } : {})
              )
            }
          >
            Generar transacción ruido
          </button>
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Target"
            value={noiseTarget}
            onChange={(e) => setNoiseTarget(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !canAdmin}
            onClick={() =>
              void wrap(() =>
                startDailyNoise(
                  cfg(),
                  noiseTarget.trim() ? { target: toNumber(noiseTarget) } : {}
                )
              )
            }
          >
            Iniciar ruido diario
          </button>
        </div>
      </div>
    </div>
  )
}
