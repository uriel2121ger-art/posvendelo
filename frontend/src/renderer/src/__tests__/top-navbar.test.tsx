/**
 * TopNavbar.tsx — Tests de navegación, usuario activo, y logout.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import TopNavbar from '../components/TopNavbar'
import { ConfirmProvider } from '../components/ConfirmDialog'
import { clearAuth, setAuthToken } from './test-utils'

function renderTopNavbar(path = '/terminal'): ReturnType<typeof render> {
  return render(
    <ConfirmProvider>
      <MemoryRouter initialEntries={[path]}>
        <TopNavbar />
      </MemoryRouter>
    </ConfirmProvider>
  )
}

describe('TopNavbar', () => {
  beforeEach(() => {
    clearAuth()
    setAuthToken(undefined, 'admin', 'cajero1')
    global.fetch = vi.fn().mockRejectedValue(new TypeError('offline'))
  })

  afterEach(() => {
    clearAuth()
  })

  it('renderiza los 13 links de navegación principal', async () => {
    const user = userEvent.setup()
    renderTopNavbar()
    const expectedLabels = [
      'Ventas',
      'Productos',
      'Clientes',
      'Inventario',
      'Turnos',
      'Historial',
      'Mermas',
      'Reportes',
      'Estadísticas',
      'Empleados',
      'Remoto',
      'Fiscal',
      'Ajustes'
    ]
    // Abrir "Más" para que los enlaces secundarios estén en el DOM
    await user.click(screen.getByTitle('Más opciones'))
    await waitFor(() => {
      for (const label of expectedLabels) {
        expect(screen.getByTitle(label)).toBeInTheDocument()
      }
    })
  })

  it('muestra las iniciales del usuario actual', () => {
    renderTopNavbar()
    expect(screen.getByText('ca')).toBeInTheDocument()
    expect(screen.getByTitle('Usuario: cajero1')).toBeInTheDocument()
  })

  it('muestra "Us" si no hay user en localStorage', () => {
    localStorage.removeItem('titan.user')
    renderTopNavbar()
    expect(screen.getByText('Us')).toBeInTheDocument()
  })

  it('botón de logout existe con title correcto', () => {
    renderTopNavbar()
    const logoutBtn = screen.getByTitle('Cerrar sesión')
    expect(logoutBtn).toBeInTheDocument()
  })

  it('logout limpia localStorage y redirige al confirmar', async () => {
    renderTopNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByTitle('Cerrar sesión'))

    await waitFor(() => {
      expect(screen.getByText('Aceptar')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Aceptar'))

    expect(localStorage.getItem('titan.token')).toBeNull()
    expect(localStorage.getItem('titan.user')).toBeNull()
    expect(localStorage.getItem('titan.role')).toBeNull()
    expect(window.location.hash).toBe('#/login')
  })

  it('logout cancelado no limpia localStorage', async () => {
    renderTopNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByTitle('Cerrar sesión'))

    await waitFor(() => {
      expect(screen.getByText('Cancelar')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Cancelar'))

    expect(localStorage.getItem('titan.token')).not.toBeNull()
  })

  it('logout con tickets pendientes muestra advertencia en el dialogo', async () => {
    // Clave por usuario: el usuario en beforeEach es 'cajero1' (setAuthToken(..., 'cajero1'))
    localStorage.setItem('titan.pendingTickets.cajero1', JSON.stringify([{ id: 1 }]))

    renderTopNavbar()
    const user = userEvent.setup()
    await user.click(screen.getByTitle('Cerrar sesión'))

    await waitFor(() => {
      expect(screen.getByText(/tickets pendientes/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText('Cancelar'))
  })

  it('navega correctamente al hacer click en un link', async () => {
    renderTopNavbar('/terminal')
    const user = userEvent.setup()

    await user.click(screen.getByTitle('Productos'))

    const link = screen.getByTitle('Productos').closest('a')
    expect(link).toHaveAttribute('href', '/productos')
  })

  it('muestra banner cuando la licencia está en gracia', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          success: true,
          data: {
            effective_status: 'grace',
            message: 'Licencia mensual en gracia. Renueva para evitar bloqueo comercial.'
          }
        }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    } as unknown as Response)

    renderTopNavbar()

    await waitFor(() => {
      expect(screen.getByText(/Licencia mensual en gracia/i)).toBeInTheDocument()
    })
  })
})
