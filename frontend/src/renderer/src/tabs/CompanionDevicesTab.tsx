import type { ReactElement } from 'react'
import { useCallback, useEffect, useState } from 'react'
import { Link2, RefreshCw, ShieldX, Smartphone } from 'lucide-react'

import {
  getPairQrPayload,
  getPairedDevices,
  getUserRole,
  loadRuntimeConfig,
  revokePairedDevice
} from '../posApi'

export default function CompanionDevicesTab(): ReactElement {
  const cfg = loadRuntimeConfig()
  const role = getUserRole()
  const canManage = role === 'owner' || role === 'admin' || role === 'manager'
  const canPair = canManage || role === 'cashier'

  const [branchId, setBranchId] = useState('1')
  const [terminalId, setTerminalId] = useState(String(cfg.terminalId || 1))
  const [pairPayload, setPairPayload] = useState<Record<string, unknown> | null>(null)
  const [devices, setDevices] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('Vincula móviles y controla los dispositivos autorizados.')

  const loadDevices = useCallback(async (): Promise<void> => {
    if (!canManage) return
    try {
      const raw = await getPairedDevices(loadRuntimeConfig())
      const data = (raw.data ?? []) as Record<string, unknown>[]
      setDevices(Array.isArray(data) ? data : [])
    } catch (error) {
      setMessage((error as Error).message)
    }
  }, [canManage])

  useEffect(() => {
    void loadDevices()
  }, [loadDevices])

  async function handleGenerate(): Promise<void> {
    if (!canPair) {
      setMessage('Sin permisos para generar vinculación.')
      return
    }
    setLoading(true)
    try {
      const raw = await getPairQrPayload(
        loadRuntimeConfig(),
        Number(branchId) || 1,
        Number(terminalId) || 1
      )
      setPairPayload((raw.data ?? raw) as Record<string, unknown>)
      setMessage('Payload de vinculación generado. Puede usarse para un QR o activación asistida.')
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRevoke(pairingId: number): Promise<void> {
    setLoading(true)
    try {
      await revokePairedDevice(loadRuntimeConfig(), pairingId)
      setMessage('Dispositivo revocado.')
      await loadDevices()
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden bg-zinc-950 font-sans text-slate-200">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-5xl mx-auto w-full p-4 lg:p-6 space-y-6 pb-24">
          <div className="flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4">
            <div className="flex items-center gap-2 min-w-0">
              <Smartphone className="w-6 h-6 text-emerald-500 shrink-0" />
              <div className="min-w-0">
                <h1 className="text-xl font-bold text-white truncate">Dispositivos vinculados</h1>
                <p className="text-xs text-zinc-500">
                  Pairing QR, terminales móviles y revocación operativa.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void loadDevices()}
              disabled={loading || !canManage}
              className="flex items-center gap-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors border border-zinc-800 px-3 py-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Actualizar
            </button>
          </div>

          {!canPair && (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
              Tu rol no puede generar tokens de vinculación.
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6 space-y-4">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                <Link2 className="w-4 h-4 text-emerald-500" /> Generar vinculación
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <input
                  className="bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:border-emerald-500 focus:outline-none transition-all placeholder:text-zinc-600"
                  placeholder="Sucursal"
                  type="number"
                  min={1}
                  value={branchId}
                  onChange={(e) => setBranchId(e.target.value)}
                />
                <input
                  className="bg-zinc-950/80 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:border-emerald-500 focus:outline-none transition-all placeholder:text-zinc-600"
                  placeholder="Terminal"
                  type="number"
                  min={1}
                  value={terminalId}
                  onChange={(e) => setTerminalId(e.target.value)}
                />
              </div>
              <button
                type="button"
                onClick={() => void handleGenerate()}
                disabled={loading || !canPair}
                className="w-full rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 transition-all disabled:opacity-50"
              >
                Generar payload
              </button>
              {pairPayload && (
                <pre className="rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-xs font-mono text-zinc-300 overflow-x-auto">
                  {JSON.stringify(pairPayload, null, 2)}
                </pre>
              )}
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 lg:p-6">
              <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2 mb-4">
                <ShieldX className="w-4 h-4 text-amber-400" /> Registro de dispositivos
              </h2>
              {!canManage ? (
                <p className="text-sm text-zinc-500">
                  Solo administración puede listar y revocar dispositivos.
                </p>
              ) : devices.length === 0 ? (
                <p className="text-sm text-zinc-500">No hay dispositivos activos.</p>
              ) : (
                <div className="space-y-3">
                  {devices.map((device) => (
                    <div
                      key={String(device.id)}
                      className="rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3 flex items-start justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white">
                          {String(device.device_name ?? device.device_id ?? '-')}
                        </p>
                        <p className="text-xs text-zinc-500">
                          {String(device.platform ?? 'plataforma')} • terminal{' '}
                          {String(device.terminal_id ?? '-')}
                        </p>
                        <p className="text-[11px] text-zinc-600">
                          Último visto:{' '}
                          {String(device.last_seen ?? device.paired_at ?? '-').slice(0, 19)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleRevoke(Number(device.id))}
                        disabled={loading}
                        className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-200 disabled:opacity-50"
                      >
                        Revocar
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {message && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-300">
              {message}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
