import type { ReactElement } from 'react'
import { useState } from 'react'
import { getFiscalDashboardData, getFiscalDashboardSmartSelection } from '../../posApi'
import type { FiscalPanelProps } from '../../types/fiscalTypes'
import { inputCls, btnPrimary, btnSecondary } from '../../utils/styles'

const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2'

export default function FiscalDashboardPanel({ cfg, busy, wrap }: FiscalPanelProps): ReactElement {
  const [year, setYear] = useState<string>('')
  const [maxAmount, setMaxAmount] = useState<string>('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Panel fiscal</h3>
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
              void wrap(() => getFiscalDashboardData(cfg(), year ? parseInt(year, 10) : undefined))
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
