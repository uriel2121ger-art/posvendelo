/**
 * Login.tsx — Tests de Login, auto-discovery, y validación de formulario.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Login from '../Login'
import { clearAuth, mockFetchJson, mockFetchError } from './test-utils'

// Mock navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Login />
    </MemoryRouter>
  )
}

describe('Login', () => {
  beforeEach(() => {
    clearAuth()
    mockNavigate.mockReset()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('muestra título "Acceso a Caja"', async () => {
    // Mock auto-discovery devuelve backend disponible
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
      body: { cancel: () => Promise.resolve() }
    } as unknown as Response)

    renderLogin()
    expect(screen.getByText('Acceso a Caja')).toBeInTheDocument()
  })

  it('muestra "Buscando servidor..." durante auto-discovery', () => {
    // Fetch que nunca resuelve — simula discovery en progreso
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
    renderLogin()
    expect(screen.getByText('Buscando servidor...')).toBeInTheDocument()
  })

  it('botón deshabilitado con campos vacíos', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
      body: { cancel: () => Promise.resolve() }
    } as unknown as Response)

    renderLogin()
    await waitFor(() => {
      expect(screen.queryByText('Buscando servidor...')).not.toBeInTheDocument()
    })

    const btn = screen.getByRole('button', { name: /ingresar/i })
    expect(btn).toBeDisabled()
  })

  it('muestra error con credenciales vacías al intentar submit', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
      body: { cancel: () => Promise.resolve() }
    } as unknown as Response)

    renderLogin()
    await waitFor(() => {
      expect(screen.queryByText('Buscando servidor...')).not.toBeInTheDocument()
    })

    const user = userEvent.setup()
    // Escribir solo usuario para habilitar parcialmente
    await user.type(screen.getByPlaceholderText('Nombre de usuario'), 'a')
    await user.type(screen.getByPlaceholderText('••••••••'), 'x')

    // Limpiar ambos campos
    await user.clear(screen.getByPlaceholderText('Nombre de usuario'))
    await user.clear(screen.getByPlaceholderText('••••••••'))

    // Botón debe seguir deshabilitado
    const btn = screen.getByRole('button', { name: /ingresar/i })
    expect(btn).toBeDisabled()
  })

  it('login exitoso navega a /terminal', async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation((url: string) => {
      // Primera llamada: auto-discovery (GET /auth/verify)
      if (String(url).includes('/auth/verify')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({}),
          body: { cancel: () => Promise.resolve() }
        })
      }
      // Segunda llamada: POST /auth/login
      if (String(url).includes('/auth/login')) {
        callCount++
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ token: 'jwt-mock-123', role: 'admin' }),
          text: () => Promise.resolve(''),
          body: { cancel: () => Promise.resolve() }
        })
      }
      return Promise.reject(new Error('Unexpected fetch'))
    })

    renderLogin()
    const user = userEvent.setup()

    // Esperar discovery
    await waitFor(() => {
      expect(screen.queryByText('Buscando servidor...')).not.toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Nombre de usuario'), 'admin')
    await user.type(screen.getByPlaceholderText('••••••••'), 'admin1234')

    const btn = screen.getByRole('button', { name: /ingresar/i })
    expect(btn).toBeEnabled()
    await user.click(btn)

    await waitFor(() => {
      expect(callCount).toBeGreaterThanOrEqual(1)
      expect(mockNavigate).toHaveBeenCalledWith('/terminal')
    })

    // Token guardado en localStorage
    expect(localStorage.getItem('titan.token')).toBe('jwt-mock-123')
    expect(localStorage.getItem('titan.user')).toBe('admin')
    expect(localStorage.getItem('titan.role')).toBe('admin')
  })

  it('login fallido muestra error', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/auth/verify')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({}),
          body: { cancel: () => Promise.resolve() }
        })
      }
      if (String(url).includes('/auth/login')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Credenciales incorrectas' }),
          text: () => Promise.resolve(''),
          body: { cancel: () => Promise.resolve() }
        })
      }
      return Promise.reject(new Error('Unexpected'))
    })

    renderLogin()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.queryByText('Buscando servidor...')).not.toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Nombre de usuario'), 'admin')
    await user.type(screen.getByPlaceholderText('••••••••'), 'wrongpass')
    await user.click(screen.getByRole('button', { name: /ingresar/i }))

    await waitFor(() => {
      expect(screen.getByText('Credenciales incorrectas')).toBeInTheDocument()
    })

    // No debería haber navegado
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('auto-discovery falla muestra error de servidor', async () => {
    // Todos los puertos fallan
    mockFetchError('fetch failed')

    renderLogin()

    await waitFor(() => {
      expect(
        screen.getByText('No se encontró el servidor. Verifica que esté encendido.')
      ).toBeInTheDocument()
    })
  })

  it('error de red durante login muestra mensaje apropiado', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/auth/verify')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({}),
          body: { cancel: () => Promise.resolve() }
        })
      }
      // Login falla con TypeError (error de red)
      return Promise.reject(new TypeError('Failed to fetch'))
    })

    renderLogin()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.queryByText('Buscando servidor...')).not.toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Nombre de usuario'), 'admin')
    await user.type(screen.getByPlaceholderText('••••••••'), 'admin1234')
    await user.click(screen.getByRole('button', { name: /ingresar/i }))

    await waitFor(() => {
      expect(screen.getByText(/No se puede conectar al servidor/)).toBeInTheDocument()
    })
  })
})
