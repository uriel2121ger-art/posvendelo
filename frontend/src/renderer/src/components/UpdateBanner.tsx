import type { ReactElement } from 'react'

export type UpdateBannerStatus = 'available' | 'downloading' | 'staged' | 'applying' | 'error' | null

type UpdateBannerProps = {
  status: UpdateBannerStatus
  version: string | null
  message: string | null
  onDownload: () => void
  onInstall: () => void
  onDiscard: () => void
}

export default function UpdateBanner({
  status,
  version,
  message,
  onDownload,
  onInstall,
  onDiscard
}: UpdateBannerProps): ReactElement | null {
  if (!status || status === ('idle' as string)) return null

  if (status === 'available') {
    return (
      <div className="border-b border-blue-500/20 bg-blue-500/10 px-4 py-2 text-center text-xs font-semibold text-blue-200 flex items-center justify-center gap-3">
        <span>Actualización v{version ?? '?'} disponible</span>
        <button
          onClick={onDownload}
          className="rounded bg-blue-600 px-3 py-0.5 text-white text-xs font-bold hover:bg-blue-500 transition-colors"
        >
          Descargar
        </button>
      </div>
    )
  }

  if (status === 'downloading') {
    return (
      <div className="border-b border-blue-500/20 bg-blue-500/10 px-4 py-2 text-center text-xs font-semibold text-blue-200 flex items-center justify-center gap-3">
        <div className="w-3.5 h-3.5 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
        <span>Descargando actualización...</span>
      </div>
    )
  }

  if (status === 'staged') {
    return (
      <div className="border-b border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-center text-xs font-semibold text-emerald-200 flex items-center justify-center gap-3">
        <span>Actualización v{version ?? '?'} lista para instalar</span>
        <button
          onClick={onInstall}
          className="rounded bg-emerald-600 px-3 py-0.5 text-white text-xs font-bold hover:bg-emerald-500 transition-colors"
        >
          Instalar ahora
        </button>
        <button
          onClick={onDiscard}
          className="rounded border border-zinc-600 px-3 py-0.5 text-zinc-300 text-xs font-bold hover:bg-zinc-800 transition-colors"
        >
          Descartar
        </button>
      </div>
    )
  }

  if (status === 'applying') {
    return (
      <div className="border-b border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-center text-xs font-semibold text-emerald-200 flex items-center justify-center gap-3">
        <div className="w-3.5 h-3.5 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
        <span>Instalando actualización...</span>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="border-b border-rose-500/20 bg-rose-500/10 px-4 py-2 text-center text-xs font-semibold text-rose-200 flex items-center justify-center gap-3">
        <span>Error al actualizar{message ? `: ${message}` : ''}</span>
        <button
          onClick={onDownload}
          className="rounded bg-rose-600 px-3 py-0.5 text-white text-xs font-bold hover:bg-rose-500 transition-colors"
        >
          Reintentar
        </button>
      </div>
    )
  }

  return null
}
