/**
 * Utilidades compartidas para tests de TITAN POS.
 * Custom render con Router + helpers de localStorage.
 */
import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom'

/* ── Auth helpers ───────────────────────────────────── */

/** Simula un usuario autenticado con token y rol. */
export function setAuthToken(token = 'test-token-abc', role = 'admin', user = 'admin'): void {
  localStorage.setItem('titan.token', token)
  localStorage.setItem('titan.role', role)
  localStorage.setItem('titan.user', user)
  localStorage.setItem('titan.baseUrl', 'http://127.0.0.1:8090')
}

/** Limpia todo localStorage de titan. */
export function clearAuth(): void {
  const keys = [
    'titan.token', 'titan.role', 'titan.user', 'titan.baseUrl',
    'titan.currentShift', 'titan.pendingTickets', 'titan.activeTickets',
    'titan.terminalId', 'titan.hwConfig',
  ]
  keys.forEach((k) => localStorage.removeItem(k))
}

/* ── Custom render con MemoryRouter ─────────────────── */

type CustomRenderOptions = RenderOptions & {
  initialEntries?: MemoryRouterProps['initialEntries']
}

function Providers({ children, initialEntries }: { children: ReactNode; initialEntries?: MemoryRouterProps['initialEntries'] }): ReactElement {
  return (
    <MemoryRouter initialEntries={initialEntries ?? ['/']}>
      {children}
    </MemoryRouter>
  )
}

export function renderWithRouter(
  ui: ReactElement,
  options: CustomRenderOptions = {},
): RenderResult {
  const { initialEntries, ...rest } = options
  return render(ui, {
    wrapper: ({ children }) => <Providers initialEntries={initialEntries}>{children}</Providers>,
    ...rest,
  })
}

/* ── API mock helpers ──────────────────────────────── */

/** Crea un mock de fetch que responde con JSON. */
export function mockFetchJson(body: unknown, status = 200): void {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    body: { cancel: () => Promise.resolve() },
  } as unknown as Response)
}

/** Crea un mock de fetch que falla con error de red. */
export function mockFetchError(message = 'Network error'): void {
  global.fetch = vi.fn().mockRejectedValue(new TypeError(message))
}
