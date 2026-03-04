import type { ReactElement } from 'react'
import { useState } from 'react'
import type { RuntimeConfig } from '../../posApi'
import { getFiscalDashboardData, getFiscalDashboardSmartSelection } from '../../posApi'

export interface FiscalPanelProps {
  cfg: () => RuntimeConfig
  busy: boolean
  wrap: (fn: () => Promise<Record<string, unknown>>) => Promise<void>
  canAdmin: boolean
}

const inputCls =
  'w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600'
const btnPrimary =
  'flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 transition-all disabled:opacity-50'
const btnSecondary =
  'flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50'
const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-1'

export default function FiscalDashboardPanel({
  cfg,
  busy,
  wrap
}: FiscalPanelProps): ReactElement {
  const [year, setYear] = useState<string>('')
  const [maxAmount, setMaxAmount] = useState<string>('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Dashboard fiscal</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input
            className={inputCls}
            type="number"
            placeholder="Año (opcional)"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getFiscalDashboardData(cfg(), year ? parseInt(year, 10) : undefined)
              )
            }
          >
            Cargar datos
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Selección inteligente</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input
            className={inputCls}
            type="number"
            placeholder="Monto máximo (opcional)"
            value={maxAmount}
            onChange={(e) => setMaxAmount(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getFiscalDashboardSmartSelection(
                  cfg(),
                  maxAmount ? parseFloat(maxAmount) : undefined
                )
              )
            }
          >
            Obtener selección
          </button>
        </div>
      </div>
    </div>
  )
}
