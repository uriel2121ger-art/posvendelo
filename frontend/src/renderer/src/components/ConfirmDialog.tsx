import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
  type ReactElement,
  type FormEvent
} from 'react'

import { useFocusTrap } from '../hooks/useFocusTrap'

type ConfirmVariant = 'danger' | 'warning' | 'info'

type ConfirmOptions = {
  title?: string
  confirmText?: string
  cancelText?: string
  variant?: ConfirmVariant
}

type PromptOptions = {
  title?: string
  defaultValue?: string
  placeholder?: string
  inputType?: 'text' | 'number'
  confirmText?: string
  cancelText?: string
  variant?: ConfirmVariant
}

type ConfirmFn = (message: string, options?: ConfirmOptions) => Promise<boolean>
type PromptFn = (message: string, options?: PromptOptions) => Promise<string | null>

const ConfirmContext = createContext<ConfirmFn>(() => Promise.resolve(false))
const PromptContext = createContext<PromptFn>(() => Promise.resolve(null))

// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm(): ConfirmFn {
  return useContext(ConfirmContext)
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePrompt(): PromptFn {
  return useContext(PromptContext)
}

const variantStyles: Record<ConfirmVariant, { border: string; button: string; title: string }> = {
  danger: {
    border: 'border-rose-700',
    button: 'bg-rose-600 hover:bg-rose-500',
    title: 'text-rose-400'
  },
  warning: {
    border: 'border-amber-700',
    button: 'bg-amber-600 hover:bg-amber-500',
    title: 'text-amber-400'
  },
  info: {
    border: 'border-blue-700',
    button: 'bg-blue-600 hover:bg-blue-500',
    title: 'text-blue-400'
  }
}

export function ConfirmProvider({ children }: { children: ReactNode }): ReactElement {
  /* ── Confirm dialog state ─────────────────────────────── */
  const [dialog, setDialog] = useState<{
    message: string
    options: ConfirmOptions
    resolve: (value: boolean) => void
  } | null>(null)

  const dialogRef = useRef<typeof dialog>(null)
  useEffect(() => {
    dialogRef.current = dialog
  }, [dialog])

  const confirmBtnRef = useRef<HTMLButtonElement>(null)
  const confirmModalRef = useRef<HTMLDivElement>(null)

  useFocusTrap(confirmModalRef, !!dialog)

  const confirm: ConfirmFn = useCallback((message, options = {}) => {
    return new Promise<boolean>((resolve) => {
      setDialog({ message, options, resolve })
    })
  }, [])

  const handleConfirmResult = useCallback((result: boolean) => {
    dialogRef.current?.resolve(result)
    setDialog(null)
  }, [])

  useEffect(() => {
    if (!dialog) return
    confirmBtnRef.current?.focus()

    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        handleConfirmResult(false)
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [dialog, handleConfirmResult])

  /* ── Prompt dialog state ──────────────────────────────── */
  const [promptDialog, setPromptDialog] = useState<{
    message: string
    options: PromptOptions
    resolve: (value: string | null) => void
  } | null>(null)

  const promptDialogRef = useRef<typeof promptDialog>(null)
  useEffect(() => {
    promptDialogRef.current = promptDialog
  }, [promptDialog])

  const [promptValue, setPromptValue] = useState('')
  const promptValueRef = useRef(promptValue)
  useEffect(() => {
    promptValueRef.current = promptValue
  }, [promptValue])

  const promptInputRef = useRef<HTMLInputElement>(null)
  const promptModalRef = useRef<HTMLFormElement>(null)

  useFocusTrap(promptModalRef, !!promptDialog)

  const prompt: PromptFn = useCallback((message, options = {}) => {
    return new Promise<string | null>((resolve) => {
      setPromptValue(options.defaultValue ?? '')
      setPromptDialog({ message, options, resolve })
    })
  }, [])

  const handlePromptSubmit = useCallback((e?: FormEvent) => {
    e?.preventDefault()
    promptDialogRef.current?.resolve(promptValueRef.current)
    setPromptDialog(null)
    setPromptValue('')
  }, [])

  const handlePromptCancel = useCallback(() => {
    promptDialogRef.current?.resolve(null)
    setPromptDialog(null)
    setPromptValue('')
  }, [])

  useEffect(() => {
    if (!promptDialog) return
    // Small delay to let React render the input before focusing
    const t = setTimeout(() => {
      promptInputRef.current?.focus()
      promptInputRef.current?.select()
    }, 30)

    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        handlePromptCancel()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      clearTimeout(t)
      window.removeEventListener('keydown', onKey, true)
    }
  }, [promptDialog, handlePromptCancel])

  /* ── Render ───────────────────────────────────────────── */
  const confirmStyle = dialog
    ? variantStyles[dialog.options.variant ?? 'warning']
    : variantStyles.warning
  const promptStyle = promptDialog
    ? variantStyles[promptDialog.options.variant ?? 'info']
    : variantStyles.info

  return (
    <ConfirmContext.Provider value={confirm}>
      <PromptContext.Provider value={prompt}>
        {children}

        {/* Confirm Dialog */}
        {dialog && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div
              ref={confirmModalRef}
              className={`w-full max-w-sm rounded-2xl border ${confirmStyle.border} bg-zinc-900 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150`}
            >
              <h3 className={`text-lg font-bold ${confirmStyle.title} mb-3`}>
                {dialog.options.title ?? 'Confirmar'}
              </h3>
              <p className="text-zinc-300 text-sm mb-6 whitespace-pre-wrap">{dialog.message}</p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleConfirmResult(false)}
                  className="flex-1 rounded-xl border border-rose-600 bg-rose-600 py-2.5 font-bold text-white hover:bg-rose-500 transition-colors"
                >
                  {dialog.options.cancelText ?? 'Cancelar'}
                </button>
                <button
                  ref={confirmBtnRef}
                  onClick={() => handleConfirmResult(true)}
                  className={`flex-1 rounded-xl ${confirmStyle.button} py-2.5 font-bold text-white transition-colors`}
                >
                  {dialog.options.confirmText ?? 'Aceptar'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Prompt Dialog */}
        {promptDialog && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <form
              ref={promptModalRef}
              onSubmit={handlePromptSubmit}
              className={`w-full max-w-sm rounded-2xl border ${promptStyle.border} bg-zinc-900 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150`}
            >
              <h3 className={`text-lg font-bold ${promptStyle.title} mb-3`}>
                {promptDialog.options.title ?? 'Ingresa un valor'}
              </h3>
              <p className="text-zinc-300 text-sm mb-4 whitespace-pre-wrap">
                {promptDialog.message}
              </p>
              <input
                ref={promptInputRef}
                type={promptDialog.options.inputType ?? 'text'}
                value={promptValue}
                onChange={(e) => setPromptValue(e.target.value)}
                placeholder={promptDialog.options.placeholder ?? ''}
                step={promptDialog.options.inputType === 'number' ? 'any' : undefined}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 py-2.5 px-3 text-sm font-semibold mb-4 focus:border-blue-500 focus:outline-none text-zinc-100"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handlePromptCancel}
                  className="flex-1 rounded-xl border border-rose-600 bg-rose-600 py-2.5 font-bold text-white hover:bg-rose-500 transition-colors"
                >
                  {promptDialog.options.cancelText ?? 'Cancelar'}
                </button>
                <button
                  type="submit"
                  className={`flex-1 rounded-xl ${promptStyle.button} py-2.5 font-bold text-white transition-colors`}
                >
                  {promptDialog.options.confirmText ?? 'Aceptar'}
                </button>
              </div>
            </form>
          </div>
        )}
      </PromptContext.Provider>
    </ConfirmContext.Provider>
  )
}
