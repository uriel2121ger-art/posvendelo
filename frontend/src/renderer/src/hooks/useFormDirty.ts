import { useRef, useCallback, type RefObject } from 'react'

type UseFormDirtyResult = {
  formDirtyRef: RefObject<boolean>
  markDirty: () => void
  guardedClose: (closeFn: () => void) => void
  resetDirty: () => void
}

export function useFormDirty(): UseFormDirtyResult {
  const formDirtyRef = useRef(false)

  const markDirty = useCallback(() => {
    formDirtyRef.current = true
  }, [])

  const guardedClose = useCallback((closeFn: () => void) => {
    if (formDirtyRef.current && !window.confirm('Hay cambios sin guardar. ¿Salir sin guardar?'))
      return
    formDirtyRef.current = false
    closeFn()
  }, [])

  const resetDirty = useCallback(() => {
    formDirtyRef.current = false
  }, [])

  return { formDirtyRef, markDirty, guardedClose, resetDirty }
}
