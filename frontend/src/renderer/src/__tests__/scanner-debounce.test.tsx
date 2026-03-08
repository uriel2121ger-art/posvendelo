/**
 * Scanner debounce test — verifies barcode scanner (pistola) doesn't
 * trigger double-Enter and maintains input focus after product addition.
 *
 * Uses a minimal component that replicates Terminal.tsx's onKeyDown logic
 * to avoid mocking the entire app.
 */
import { render, screen, act } from '@testing-library/react'
import { useRef, useState, type ReactElement } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ---------------------------------------------------------------------------
// Minimal component replicating Terminal search input scanner logic
// ---------------------------------------------------------------------------

type Product = { sku: string; name: string; price: number }

const PRODUCTS: Product[] = [
  { sku: '7501234567890', name: 'Coca-Cola 600ml', price: 15 },
  { sku: '7509876543210', name: 'Sabritas Adobadas', price: 18 }
]

function ScannerInput({ onAdd }: { onAdd: (p: Product) => void }): ReactElement {
  const inputRef = useRef<HTMLInputElement>(null)
  const lastKeystrokeRef = useRef<number>(0)
  const lastEnterRef = useRef<number>(0)
  const [query, setQuery] = useState('')

  return (
    <input
      ref={inputRef}
      data-testid="search-input"
      value={query}
      onChange={(e) => {
        lastKeystrokeRef.current = Date.now()
        setQuery(e.target.value)
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          e.stopPropagation()

          // Debounce: ignore Enter if another fired within 150ms (scanner CR+LF)
          const now = Date.now()
          if (now - lastEnterRef.current < 150) return
          lastEnterRef.current = now

          // Skip if query is empty
          if (!query.trim()) return

          // Exact match by SKU
          const searchTerm = query.trim()
          const exact = PRODUCTS.find((p) => p.sku.toLowerCase() === searchTerm.toLowerCase())
          if (exact) {
            onAdd(exact)
            setQuery('')
            inputRef.current?.focus()
            return
          }

          // Fallback: first partial match
          const partial = PRODUCTS.find(
            (p) =>
              p.sku.includes(searchTerm) || p.name.toLowerCase().includes(searchTerm.toLowerCase())
          )
          if (partial) {
            onAdd(partial)
            setQuery('')
            inputRef.current?.focus()
          }
        }
      }}
    />
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Simulate scanner typing: set value instantly + fire onChange, then Enter */
async function simulateScan(input: HTMLInputElement, barcode: string): Promise<void> {
  // Scanner types all chars at once (nearly instant)
  await act(async () => {
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    )!.set!
    nativeInputValueSetter.call(input, barcode)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })

  // Small delay to simulate scanner speed
  await act(async () => {
    await new Promise((r) => setTimeout(r, 10))
  })

  // Scanner sends Enter
  await act(async () => {
    input.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    )
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Scanner debounce (barcode pistola)', () => {
  let onAdd: ReturnType<typeof vi.fn>

  beforeEach(() => {
    onAdd = vi.fn()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  it('adds product exactly once on single Enter', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement

    await simulateScan(input, '7501234567890')

    expect(onAdd).toHaveBeenCalledTimes(1)
    expect(onAdd).toHaveBeenCalledWith(
      expect.objectContaining({ sku: '7501234567890', name: 'Coca-Cola 600ml' })
    )
  })

  it('ignores second Enter within 150ms (scanner CR+LF)', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement

    await simulateScan(input, '7501234567890')

    // Simulate second Enter immediately (CR+LF from scanner, < 150ms)
    await act(async () => {
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
      )
    })

    expect(onAdd).toHaveBeenCalledTimes(1)
  })

  it('allows second Enter after 150ms (separate scans)', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement

    // First scan
    await simulateScan(input, '7501234567890')
    expect(onAdd).toHaveBeenCalledTimes(1)

    // Wait > 150ms
    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Second scan (different product)
    await simulateScan(input, '7509876543210')
    expect(onAdd).toHaveBeenCalledTimes(2)
    expect(onAdd).toHaveBeenLastCalledWith(
      expect.objectContaining({ sku: '7509876543210', name: 'Sabritas Adobadas' })
    )
  })

  it('does nothing on Enter with empty input', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement

    await act(async () => {
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
      )
    })

    expect(onAdd).not.toHaveBeenCalled()
  })

  it('retains focus on input after adding product', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement
    input.focus()

    await simulateScan(input, '7501234567890')

    expect(document.activeElement).toBe(input)
  })

  it('clears input after adding product', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement

    await simulateScan(input, '7501234567890')

    expect(input.value).toBe('')
  })

  it('triple Enter from faulty scanner still adds only once', async () => {
    vi.useRealTimers()
    render(<ScannerInput onAdd={onAdd} />)
    const input = screen.getByTestId('search-input') as HTMLInputElement

    await simulateScan(input, '7501234567890')

    // Two more rapid Enters
    await act(async () => {
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
      )
    })
    await act(async () => {
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
      )
    })

    expect(onAdd).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// FASE 0.3: Sanitización escáner — \t y caracteres de control no deben
// llegar al valor del input (evitar saltos de foco o acciones destructivas).
// ---------------------------------------------------------------------------
// eslint-disable-next-line no-control-regex
const CONTROL_STRIP_RE = /[\x00-\x1F\x7F-\x9F]/g
function stripControlChars(value: string): string {
  return value.replace(CONTROL_STRIP_RE, '')
}

describe('Scanner sanitization (FASE 0.3)', () => {
  it('strips tab and control characters from search input', () => {
    expect(stripControlChars('7501234567890')).toBe('7501234567890')
    expect(stripControlChars('7501234567890\t')).toBe('7501234567890')
    expect(stripControlChars('SKU\x00\t\n')).toBe('SKU')
    expect(stripControlChars('a\x1Fb\x7Fc')).toBe('abc')
  })
})
