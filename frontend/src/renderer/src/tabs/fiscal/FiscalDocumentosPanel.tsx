import type { ReactElement } from 'react'
import { useState } from 'react'
import {
  getLegalMonthlySummary,
  generateDestructionActa,
  generateReturnDocument,
  generateLegalSelfConsumptionVoucher,
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
import type { FiscalPanelProps } from '../../types/fiscalTypes'
import { inputCls, btnPrimary, btnSecondary } from '../../utils/styles'
import { toNumber } from '../../utils/numbers'

const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2'

export default function FiscalDocumentosPanel({ cfg, busy, wrap }: FiscalPanelProps): ReactElement {
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
  // Acta destrucción
  const [adProductName, setAdProductName] = useState('')
  const [adSku, setAdSku] = useState('')
  const [adSatKey, setAdSatKey] = useState('')
  const [adQty, setAdQty] = useState('')
  const [adUnit, setAdUnit] = useState('PZA')
  const [adUnitCost, setAdUnitCost] = useState('')
  const [adCategory, setAdCategory] = useState('deterioro')
  const [adReason, setAdReason] = useState('Deterioro natural')
  const [adWitness, setAdWitness] = useState('')
  const [adSupervisor, setAdSupervisor] = useState('')
  const [adAuthorizedBy, setAdAuthorizedBy] = useState('')
  // Documento devolución
  const [rdFolio, setRdFolio] = useState('')
  const [rdProductName, setRdProductName] = useState('')
  const [rdSku, setRdSku] = useState('')
  const [rdQty, setRdQty] = useState('')
  const [rdUnitPrice, setRdUnitPrice] = useState('')
  const [rdSerie, setRdSerie] = useState('A')
  const [rdReturnReason, setRdReturnReason] = useState('')
  // Voucher autoconsumo legal
  const [voucherItemsJson, setVoucherItemsJson] = useState('')
  const [voucherPeriod, setVoucherPeriod] = useState('')

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
        <h3 className={labelCls}>Acta de destrucción</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
          <input
            className={inputCls}
            placeholder="Producto *"
            value={adProductName}
            onChange={(e) => setAdProductName(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="SKU"
            value={adSku}
            onChange={(e) => setAdSku(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Clave SAT"
            value={adSatKey}
            onChange={(e) => setAdSatKey(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Cantidad *"
            value={adQty}
            onChange={(e) => setAdQty(e.target.value)}
          />
          <input
            className={inputCls + ' max-w-[80px]'}
            placeholder="Unidad"
            value={adUnit}
            onChange={(e) => setAdUnit(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Costo unitario *"
            value={adUnitCost}
            onChange={(e) => setAdUnitCost(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Categoría"
            value={adCategory}
            onChange={(e) => setAdCategory(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Razón"
            value={adReason}
            onChange={(e) => setAdReason(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Testigo"
            value={adWitness}
            onChange={(e) => setAdWitness(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Supervisor"
            value={adSupervisor}
            onChange={(e) => setAdSupervisor(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Autorizado por"
            value={adAuthorizedBy}
            onChange={(e) => setAdAuthorizedBy(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !adProductName.trim() || !adQty.trim() || !adUnitCost.trim()}
            onClick={() =>
              void wrap(() => {
                const qty = toNumber(adQty)
                const cost = toNumber(adUnitCost)
                return generateDestructionActa(cfg(), {
                  product_name: adProductName.trim(),
                  sku: adSku.trim() || undefined,
                  sat_key: adSatKey.trim() || undefined,
                  quantity: qty,
                  unit: adUnit.trim() || 'PZA',
                  unit_cost: cost,
                  total_value: qty * cost,
                  category: adCategory.trim() || 'deterioro',
                  reason: adReason.trim() || 'Deterioro natural',
                  witness_name: adWitness.trim() || undefined,
                  supervisor_name: adSupervisor.trim() || undefined,
                  authorized_by: adAuthorizedBy.trim() || undefined
                })
              })
            }
          >
            Generar acta
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Documento de devolución</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
          <input
            className={inputCls}
            placeholder="Folio original"
            value={rdFolio}
            onChange={(e) => setRdFolio(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Producto *"
            value={rdProductName}
            onChange={(e) => setRdProductName(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="SKU"
            value={rdSku}
            onChange={(e) => setRdSku(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Cantidad *"
            value={rdQty}
            onChange={(e) => setRdQty(e.target.value)}
          />
          <input
            className={inputCls}
            type="number"
            placeholder="Precio unitario *"
            value={rdUnitPrice}
            onChange={(e) => setRdUnitPrice(e.target.value)}
          />
          <select
            className={inputCls + ' max-w-[80px]'}
            value={rdSerie}
            onChange={(e) => setRdSerie(e.target.value)}
          >
            <option value="A">A</option>
            <option value="B">B</option>
          </select>
          <input
            className={inputCls}
            placeholder="Razón devolución"
            value={rdReturnReason}
            onChange={(e) => setRdReturnReason(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !rdProductName.trim() || !rdQty.trim() || !rdUnitPrice.trim()}
            onClick={() =>
              void wrap(() => {
                const qty = toNumber(rdQty)
                const price = toNumber(rdUnitPrice)
                const subtotal = qty * price
                const tax = subtotal * 0.16
                return generateReturnDocument(cfg(), {
                  original_folio: rdFolio.trim() || undefined,
                  product_name: rdProductName.trim(),
                  sku: rdSku.trim() || undefined,
                  quantity: qty,
                  unit_price: price,
                  subtotal,
                  tax,
                  total: subtotal + tax,
                  serie: rdSerie,
                  return_reason: rdReturnReason.trim() || undefined
                })
              })
            }
          >
            Generar documento
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Voucher autoconsumo (legal)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input
            className={inputCls}
            placeholder='Artículos JSON [{"product":"X","quantity":1,"value":10}]'
            value={voucherItemsJson}
            onChange={(e) => setVoucherItemsJson(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="Período (ej: 2026-03)"
            value={voucherPeriod}
            onChange={(e) => setVoucherPeriod(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !voucherItemsJson.trim()}
            onClick={() => {
              let items: Record<string, unknown>[] = []
              try {
                const parsed = JSON.parse(voucherItemsJson)
                if (Array.isArray(parsed)) items = parsed
              } catch {
                /* empty */
              }
              void wrap(() =>
                generateLegalSelfConsumptionVoucher(cfg(), {
                  items,
                  period: voucherPeriod.trim() || undefined
                })
              )
            }}
          >
            Generar comprobante legal
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Autoconsumo</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
          <input
            className={inputCls}
            type="number"
            placeholder="ID de producto"
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
            placeholder="Destinatario de muestra"
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
            Generar comprobante
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
            placeholder="ID de producto"
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
                getShrinkageSummary(cfg(), shrinkYear ? parseInt(shrinkYear, 10) : undefined)
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
