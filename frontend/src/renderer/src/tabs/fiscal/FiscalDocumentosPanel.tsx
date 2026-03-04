import type { ReactElement } from 'react'
import { useState } from 'react'
import type { RuntimeConfig } from '../../posApi'
import {
  getLegalMonthlySummary,
  registerSelfConsumption,
  registerSample,
  registerEmployeeConsumption,
  getSelfConsumptionSummary,
  generateSelfConsumptionVoucher,
  getPendingVoucherMonths,
  registerShrinkageLoss,
  authorizeShrinkageLoss,
  getShrinkageActa,
  getShrinkagePending,
  getShrinkageSummary
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

export default function FiscalDocumentosPanel({
  cfg,
  busy,
  wrap
}: FiscalPanelProps): ReactElement {
  const [legalYear, setLegalYear] = useState('')
  const [legalMonth, setLegalMonth] = useState('')
  const [scProductId, setScProductId] = useState('')
  const [scQty, setScQty] = useState('')
  const [scCategory, setScCategory] = useState('')
  const [scReason, setScReason] = useState('')
  const [scBeneficiary, setScBeneficiary] = useState('')
  const [scRecipient, setScRecipient] = useState('Cliente')
  const [scEmployee, setScEmployee] = useState('')
  const [lossProductId, setLossProductId] = useState('')
  const [lossQty, setLossQty] = useState('')
  const [lossReason, setLossReason] = useState('')
  const [lossCategory, setLossCategory] = useState('deterioro')
  const [lossWitness, setLossWitness] = useState('')
  const [actaNumber, setActaNumber] = useState('')
  const [authorizedBy, setAuthorizedBy] = useState('')
  const [shrinkYear, setShrinkYear] = useState('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Resumen legal mensual</h3>
        <div className="flex gap-2 flex-wrap">
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Año"
            value={legalYear}
            onChange={(e) => setLegalYear(e.target.value)}
          />
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Mes"
            value={legalMonth}
            onChange={(e) => setLegalMonth(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getLegalMonthlySummary(
                  cfg(),
                  legalYear ? parseInt(legalYear, 10) : undefined,
                  legalMonth ? parseInt(legalMonth, 10) : undefined
                )
              )
            }
          >
            Resumen legal
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Documentos legales (acta destrucción, devolución, voucher)</h3>
        <p className="text-xs text-zinc-500 mb-2">
          Usar API con body JSON según esquema del backend (destruction-acta, return-document,
          legal/selfconsumption-voucher).
        </p>
        <button
          className={btnSecondary}
          disabled={busy}
          onClick={() => void wrap(() => getLegalMonthlySummary(cfg()))}
        >
          Cargar resumen
        </button>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Autoconsumo</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
          <input
            className={inputCls}
            type="number"
            placeholder="Product ID"
            value={scProductId}
            onChange={(e) => setScProductId(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Cantidad"
            value={scQty}
            onChange={(e) => setScQty(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Categoría"
            value={scCategory}
            onChange={(e) => setScCategory(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Razón (opcional)"
            value={scReason}
            onChange={(e) => setScReason(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Beneficiario (opcional)"
            value={scBeneficiary}
            onChange={(e) => setScBeneficiary(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !scProductId.trim()}
            onClick={() =>
              void wrap(() =>
                registerSelfConsumption(cfg(), {
                  product_id: toNumber(scProductId),
                  quantity: toNumber(scQty),
                  category: scCategory.trim() || 'general',
                  reason: scReason.trim() || undefined,
                  beneficiary: scBeneficiary.trim() || undefined
                })
              )
            }
          >
            Registrar autoconsumo
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
          <input
            className={inputCls}
            placeholder="Destinatario muestra"
            value={scRecipient}
            onChange={(e) => setScRecipient(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !scProductId.trim()}
            onClick={() =>
              void wrap(() =>
                registerSample(cfg(), {
                  product_id: toNumber(scProductId),
                  quantity: toNumber(scQty),
                  recipient: scRecipient.trim()
                })
              )
            }
          >
            Registrar muestra
          </button>
          <input
            className={inputCls}
            placeholder="Nombre empleado"
            value={scEmployee}
            onChange={(e) => setScEmployee(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !scProductId.trim() || !scEmployee.trim()}
            onClick={() =>
              void wrap(() =>
                registerEmployeeConsumption(cfg(), {
                  product_id: toNumber(scProductId),
                  quantity: toNumber(scQty),
                  employee_name: scEmployee.trim()
                })
              )
            }
          >
            Consumo empleado
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Año"
            value={legalYear}
            onChange={(e) => setLegalYear(e.target.value)}
          />
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Mes"
            value={legalMonth}
            onChange={(e) => setLegalMonth(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getSelfConsumptionSummary(
                  cfg(),
                  legalYear ? parseInt(legalYear, 10) : undefined,
                  legalMonth ? parseInt(legalMonth, 10) : undefined
                )
              )
            }
          >
            Resumen autoconsumo
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                generateSelfConsumptionVoucher(
                  cfg(),
                  legalYear ? parseInt(legalYear, 10) : undefined,
                  legalMonth ? parseInt(legalMonth, 10) : undefined
                )
              )
            }
          >
            Generar voucher
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getPendingVoucherMonths(cfg()))}
          >
            Meses pendientes
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Mermas / Pérdidas</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <input
            className={inputCls}
            type="number"
            placeholder="Product ID"
            value={lossProductId}
            onChange={(e) => setLossProductId(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Cantidad"
            value={lossQty}
            onChange={(e) => setLossQty(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Razón"
            value={lossReason}
            onChange={(e) => setLossReason(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Categoría"
            value={lossCategory}
            onChange={(e) => setLossCategory(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Testigo (opcional)"
            value={lossWitness}
            onChange={(e) => setLossWitness(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !lossProductId.trim() || !lossReason.trim()}
            onClick={() =>
              void wrap(() =>
                registerShrinkageLoss(cfg(), {
                  product_id: toNumber(lossProductId),
                  quantity: toNumber(lossQty),
                  reason: lossReason.trim(),
                  category: lossCategory.trim(),
                  witness_name: lossWitness.trim() || undefined
                })
              )
            }
          >
            Registrar pérdida
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input
            className={inputCls + ' max-w-[140px]'}
            placeholder="Número acta"
            value={actaNumber}
            onChange={(e) => setActaNumber(e.target.value)}
          />
          <input
            className={inputCls + ' max-w-[180px]'}
            placeholder="Autorizado por"
            value={authorizedBy}
            onChange={(e) => setAuthorizedBy(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy || !actaNumber.trim()}
            onClick={() => void wrap(() => getShrinkageActa(cfg(), actaNumber.trim()))}
          >
            Ver acta
          </button>
          <button
            className={btnPrimary}
            disabled={busy || !actaNumber.trim() || !authorizedBy.trim()}
            onClick={() =>
              void wrap(() =>
                authorizeShrinkageLoss(cfg(), {
                  acta_number: actaNumber.trim(),
                  authorized_by: authorizedBy.trim()
                })
              )
            }
          >
            Autorizar pérdida
          </button>
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() => void wrap(() => getShrinkagePending(cfg()))}
          >
            Pendientes
          </button>
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Año"
            value={shrinkYear}
            onChange={(e) => setShrinkYear(e.target.value)}
          />
          <button
            className={btnSecondary}
            disabled={busy}
            onClick={() =>
              void wrap(() =>
                getShrinkageSummary(
                  cfg(),
                  shrinkYear ? parseInt(shrinkYear, 10) : undefined
                )
              )
            }
          >
            Resumen
          </button>
        </div>
      </div>
    </div>
  )
}
