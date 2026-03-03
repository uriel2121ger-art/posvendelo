import { useEffect, type RefObject } from 'react'

export function useFocusTrap(ref: RefObject<HTMLElement | null>, active: boolean = true): void {
  useEffect((): (() => void) | void => {
    if (!active) return

    const el = ref.current
    if (!el) return

    // Enfocar automáticamente el primer elemento al montar
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(', ')

    const elements = Array.from(el.querySelectorAll<HTMLElement>(focusableSelectors)).filter(
      (node) => node.tabIndex >= 0 && node.offsetWidth > 0 && node.offsetHeight > 0
    )

    if (elements.length > 0) {
      elements[0].focus()
    }

    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key !== 'Tab') return

      const focusableElements = Array.from(
        el.querySelectorAll<HTMLElement>(focusableSelectors)
      ).filter((node) => node.tabIndex >= 0 && node.offsetWidth > 0 && node.offsetHeight > 0)

      if (focusableElements.length === 0) {
        e.preventDefault()
        return
      }

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (e.shiftKey) {
        if (
          document.activeElement === firstElement ||
          document.activeElement === el ||
          !el.contains(document.activeElement)
        ) {
          lastElement.focus()
          e.preventDefault()
        }
      } else {
        if (document.activeElement === lastElement || !el.contains(document.activeElement)) {
          firstElement.focus()
          e.preventDefault()
        }
      }
    }

    // Usar la fase de captura para ganar prioridad sobre otros listeners
    document.addEventListener('keydown', handleKeyDown, true)

    return () => {
      document.removeEventListener('keydown', handleKeyDown, true)
    }
  }, [active, ref])
}
