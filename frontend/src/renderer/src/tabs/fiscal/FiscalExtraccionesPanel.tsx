import type { ReactElement } from 'react'
import { useState } from 'react'
import type { RuntimeConfig } from '../../posApi'
import {
  addRelatedPerson,
  getSerieBBalance,
  createCashExtraction,
  getExtractionContract,
  getExtractionAnnualSummary,
  registerDiscrepancyExpense,
  getDiscrepancyAnalysis,
  getDiscrepancyTrend,
  getDiscrepancySuggestExtraction,
  getDiscrepancyExpenses,
  getResicoHealth,
  getResicoShouldPause,
  getResicoMonthlyBreakdown
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

export default function FiscalExtraccionesPanel({
  cfg,
  busy,
  wrap
}: FiscalPanelProps): ReactElement {
  const [relName, setRelName] = useState('')
  const [relParentesco, setRelParentesco] = useState('')
  const [relRfc, setRelRfc] = useState('')
  const [relCurp, setRelCurp] = useState('')
  const [extAmount, setExtAmount] = useState('')
  const [extDocType, setExtDocType] = useState('')
  const [extPurpose, setExtPurpose] = useState('')
  const [extractionId, setExtractionId] = useState('')
  const [annualYear, setAnnualYear] = useState('')
  const [expAmount, setExpAmount] = useState('')
  const [expCategory, setExpCategory] = useState('')
  const [expPayment, setExpPayment] = useState('efectivo')
  const [expDesc, setExpDesc] = useState('')
  const [discYear, setDiscYear] = useState('')
  const [discMonth, setDiscMonth] = useState('')
  const [resicoYear, setResicoYear] = useState('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Persona relacionada</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input
            className={inputCls}
            placeholder="Nombre"
            value={relName}
            onChange={(e) => setRelName(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Parentesco"
            value={relParentesco}
            onChange={(e) => setRelParentesco(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="RFC (opcional)"
            value={relRfc}
            onChange={(e) => setRelRfc(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="CURP (opcional)"
            value={relCurp}
            onChange={(e) => setRelCurp(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !relName.trim() || !relParentesco.trim()}
            onClick={() =>
              void wrap(() =>
                addRelatedPerson(cfg(), {
                  name: relName.trim(),
                  parentesco: relParentesco.trim(),
                  rfc: relRfc.trim() || undefined,
                  curp: relCurp.trim() || undefined
                })
              )
            }
          >
            Agregar
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Extracción de efectivo</h3>
        <div className="flex gap-2 flex-wrap mb-3">
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getSerieBBalance(cfg()))}
          >
            Balance Serie B
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input
            className={inputCls}
            type="number"
            placeholder="Monto"
            value={extAmount}
            onChange={(e) => setExtAmount(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Tipo documento"
            value={extDocType}
            onChange={(e) => setExtDocType(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Propósito (opcional)"
            value={extPurpose}
            onChange={(e) => setExtPurpose(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !extAmount.trim() || !extDocType.trim()}
            onClick={() =>
              void wrap(() =>
                createCashExtraction(cfg(), {
                  amount: toNumber(extAmount),
                  document_type: extDocType.trim(),
                  purpose: extPurpose.trim() || undefined
                })
              )
            }
          >
            Crear extracción
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          <input
            className={inputCls + ' max-w-[120px]'}
            type="number"
            placeholder="Extraction ID"
            value={extractionId}
            onChange={(e) => setExtractionId(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !extractionId.trim()}
            onClick={() =>
              void wrap(() => getExtractionContract(cfg(), toNumber(extractionId)))
            }
          >
            Contrato
          </button>
          <input
            className={inputCls + ' max-w-[100px]'}
            type="number"
            placeholder="Año"
            value={annualYear}
            onChange={(e) => setAnnualYear(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getExtractionAnnualSummary(
                  cfg(),
                  annualYear ? parseInt(annualYear, 10) : undefined
                )
              )
            }
          >
            Resumen anual
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Monitor de discrepancias</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <input
            className={inputCls}
            type="number"
            placeholder="Monto"
            value={expAmount}
            onChange={(e) => setExpAmount(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Categoría"
            value={expCategory}
            onChange={(e) => setExpCategory(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Forma de pago"
            value={expPayment}
            onChange={(e) => setExpPayment(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Descripción"
            value={expDesc}
            onChange={(e) => setExpDesc(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !expAmount.trim() || !expCategory.trim()}
            onClick={() =>
              void wrap(() =>
                registerDiscrepancyExpense(cfg(), {
                  amount: toNumber(expAmount),
                  category: expCategory.trim(),
                  payment_method: expPayment.trim(),
                  description: expDesc.trim() || undefined,
                  is_visible: true
                })
              )
            }
          >
            Registrar gasto
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Año"
            value={discYear}
            onChange={(e) => setDiscYear(e.target.value)}
          />
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Mes"
            value={discMonth}
            onChange={(e) => setDiscMonth(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getDiscrepancyAnalysis(
                  cfg(),
                  discYear ? parseInt(discYear, 10) : undefined,
                  discMonth ? parseInt(discMonth, 10) : undefined
                )
              )
            }
          >
            Análisis
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getDiscrepancyTrend(
                  cfg(),
                  discYear ? parseInt(discYear, 10) : undefined
                )
              )
            }
          >
            Tendencia
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getDiscrepancySuggestExtraction(cfg()))}
          >
            Sugerir extracción
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getDiscrepancyExpenses(
                  cfg(),
                  discYear ? parseInt(discYear, 10) : undefined,
                  discMonth ? parseInt(discMonth, 10) : undefined
                )
              )
            }
          >
            Gastos
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>RESICO</h3>
        <div className="flex gap-2 flex-wrap">
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Año"
            value={resicoYear}
            onChange={(e) => setResicoYear(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getResicoHealth(
                  cfg(),
                  resicoYear ? parseInt(resicoYear, 10) : undefined
                )
              )
            }
          >
            Salud
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getResicoShouldPause(cfg()))}
          >
            ¿Pausar?
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getResicoMonthlyBreakdown(
                  cfg(),
                  resicoYear ? parseInt(resicoYear, 10) : undefined
                )
              )
            }
          >
            Desglose mensual
          </button>
        </div>
      </div>
    </div>
  )
}
