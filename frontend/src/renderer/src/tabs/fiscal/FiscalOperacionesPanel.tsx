import type { ReactElement } from 'react'
import { useState } from 'react'
import {
  selectOptimalRfc,
  processCrossInvoice,
  proxyTimbrar,
  configureProxies,
  getJitterRandomTime,
  distributeTimbrados,
  getOptimalNoise,
  generateNoiseTransaction,
  startDailyNoise
} from '../../posApi'
import type { FiscalPanelProps } from '../../types/fiscalTypes'
import { inputCls, btnPrimary, btnSecondary } from '../../utils/styles'
import { toNumber } from '../../utils/numbers'

const cardCls = 'rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6'
const labelCls = 'text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2'

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
  // Proxy timbrado
  const [proxyXml, setProxyXml] = useState('')
  const [proxyRfc, setProxyRfc] = useState('')
  const [proxyPacUrl, setProxyPacUrl] = useState('')
  const [proxiesJson, setProxiesJson] = useState('')

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h3 className={labelCls}>Intercompañía / RFC óptimo</h3>
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
            placeholder="ID de venta"
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
        <h3 className={labelCls}>Proxy / Timbrado PAC</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
          <textarea
            className={inputCls + ' min-h-[60px]'}
            placeholder="XML CFDI *"
            value={proxyXml}
            onChange={(e) => setProxyXml(e.target.value)}
          />
          <input
            className={inputCls}
            placeholder="RFC *"
            maxLength={13}
            value={proxyRfc}
            onChange={(e) => setProxyRfc(e.target.value.toUpperCase())}
          />
          <input
            className={inputCls}
            placeholder="PAC URL *"
            value={proxyPacUrl}
            onChange={(e) => setProxyPacUrl(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={
              busy || !proxyXml.trim() || !proxyRfc.trim() || !proxyPacUrl.trim() || !canAdmin
            }
            onClick={() =>
              void wrap(() =>
                proxyTimbrar(cfg(), {
                  xml_data: proxyXml.trim(),
                  rfc: proxyRfc.trim(),
                  pac_url: proxyPacUrl.trim()
                })
              )
            }
          >
            Timbrar con proxy
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <textarea
            className={inputCls + ' min-h-[60px]'}
            placeholder='Proxies JSON [{"url":"...","user":"...","password":"..."}]'
            value={proxiesJson}
            onChange={(e) => setProxiesJson(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !proxiesJson.trim() || !canAdmin}
            onClick={() => {
              let proxies: Record<string, unknown>[] = []
              try {
                const parsed = JSON.parse(proxiesJson)
                if (Array.isArray(parsed)) proxies = parsed
              } catch {
                /* empty */
              }
              void wrap(() => configureProxies(cfg(), { proxies }))
            }}
          >
            Configurar proxies
          </button>
        </div>
      </div>
      <div className={cardCls}>
        <h3 className={labelCls}>Variación temporal / Rotación RFC</h3>
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
            Generar transacción de ruido
          </button>
          <input
            className={inputCls + ' max-w-[80px]'}
            type="number"
            placeholder="Objetivo"
            value={noiseTarget}
            onChange={(e) => setNoiseTarget(e.target.value)}
          />
          <button
            className={btnPrimary}
            disabled={busy || !canAdmin}
            onClick={() =>
              void wrap(() =>
                startDailyNoise(cfg(), noiseTarget.trim() ? { target: toNumber(noiseTarget) } : {})
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
