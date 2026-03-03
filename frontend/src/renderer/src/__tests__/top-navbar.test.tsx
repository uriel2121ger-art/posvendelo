/**
 * TopNavbar.tsx — Tests de navegación, usuario activo, y logout.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import TopNavbar from '../components/TopNavbar'
import { ConfirmProvider } from '../components/ConfirmDialog'
import { clearAuth, setAuthToken } from './test-utils'

function renderTopNavbar(path = '/terminal') {
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
  })

  afterEach(() => {
    clearAuth()
  })

  it('renderiza los 14 links de navegación principal', () => {
    renderTopNavbar()
    const expectedLabels = [
      'Ventas',
      'Productos',
      'Clientes',
      'Inventario',
      'Turnos',
      'Historial',
      'Gastos',
      'Mermas',
      'Reportes',
      'Estadísticas',
      'Empleados',
      'Remoto',
      'Fiscal',
      'Ajustes'
    ]
    for (const label of expectedLabels) {
      // Labels are hidden on small screens but still in the DOM
      expect(screen.getByTitle(label)).toBeInTheDocument()
    }
  })

  it('muestra las iniciales del usuario actual', () => {
    renderTopNavbar()
    expect(screen.getByText('ca')).toBeInTheDocument()
    expect(screen.getByTitle('Usuario Activo: cajero1')).toBeInTheDocument()
  })

  it('muestra "Us" si no hay user en localStorage', () => {
    localStorage.removeItem('titan.user')
    renderTopNavbar()
    expect(screen.getByText('Us')).toBeInTheDocument()
  })

  it('botón de logout existe con title correcto', () => {
    renderTopNavbar()
    const logoutBtn = screen.getByTitle('Cerrar Sesión')
    expect(logoutBtn).toBeInTheDocument()
  })

  it('logout limpia localStorage y redirige al confirmar', async () => {
    renderTopNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByTitle('Cerrar Sesión'))

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

    await user.click(screen.getByTitle('Cerrar Sesión'))

    await waitFor(() => {
      expect(screen.getByText('Cancelar')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Cancelar'))

    expect(localStorage.getItem('titan.token')).not.toBeNull()
  })

  it('logout con tickets pendientes muestra advertencia en el dialogo', async () => {
    localStorage.setItem('titan.pendingTickets', JSON.stringify([{ id: 1 }]))

    renderTopNavbar()
    const user = userEvent.setup()
    await user.click(screen.getByTitle('Cerrar Sesión'))

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
})
