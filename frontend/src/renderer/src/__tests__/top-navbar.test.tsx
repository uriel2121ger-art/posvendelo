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

function renderNavbar(path = '/terminal') {
  return render(
    <ConfirmProvider>
      <MemoryRouter initialEntries={[path]}>
        <TopNavbar />
      </MemoryRouter>
    </ConfirmProvider>,
  )
}

describe('TopNavbar', () => {
  beforeEach(() => {
    clearAuth()
    setAuthToken('tok', 'admin', 'cajero1')
  })

  afterEach(() => {
    clearAuth()
  })

  it('renderiza los 15 links de navegación', () => {
    renderNavbar()
    const expectedLabels = [
      'Ventas', 'Clientes', 'Productos', 'Inventario', 'Turnos',
      'Reportes', 'Historial', 'Ajustes', 'Stats', 'Mermas',
      'Gastos', 'Empleados', 'Remoto', 'Fiscal', 'Hardware',
    ]
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('marca la pestaña activa con aria-current="page"', () => {
    renderNavbar('/productos')
    const link = screen.getByText('Productos').closest('a')
    expect(link).toHaveAttribute('aria-current', 'page')

    // Otros links no deben tener aria-current
    const ventas = screen.getByText('Ventas').closest('a')
    expect(ventas).not.toHaveAttribute('aria-current')
  })

  it('muestra el nombre de usuario actual', () => {
    renderNavbar()
    expect(screen.getByText('cajero1')).toBeInTheDocument()
    expect(screen.getByText('Le atiende:')).toBeInTheDocument()
  })

  it('muestra "Usuario" si no hay user en localStorage', () => {
    localStorage.removeItem('titan.user')
    renderNavbar()
    expect(screen.getByText('Usuario')).toBeInTheDocument()
  })

  it('botón de logout existe con aria-label correcto', () => {
    renderNavbar()
    const logoutBtn = screen.getByLabelText('Cerrar sesión')
    expect(logoutBtn).toBeInTheDocument()
  })

  it('logout limpia localStorage y redirige al confirmar', async () => {
    renderNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText('Cerrar sesión'))

    // ConfirmDialog should appear
    await waitFor(() => {
      expect(screen.getByText('Aceptar')).toBeInTheDocument()
    })

    // Click "Aceptar" to confirm logout
    await user.click(screen.getByText('Aceptar'))

    expect(localStorage.getItem('titan.token')).toBeNull()
    expect(localStorage.getItem('titan.user')).toBeNull()
    expect(localStorage.getItem('titan.role')).toBeNull()
    expect(window.location.hash).toBe('#/login')
  })

  it('logout cancelado no limpia localStorage', async () => {
    renderNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText('Cerrar sesión'))

    // ConfirmDialog should appear
    await waitFor(() => {
      expect(screen.getByText('Cancelar')).toBeInTheDocument()
    })

    // Click "Cancelar" to abort logout
    await user.click(screen.getByText('Cancelar'))

    // Token sigue ahí
    expect(localStorage.getItem('titan.token')).toBe('tok')
  })

  it('logout con turno abierto muestra advertencia en el dialogo', async () => {
    localStorage.setItem('titan.currentShift', '42')

    renderNavbar()
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Cerrar sesión'))

    // ConfirmDialog should show warning about open shift
    await waitFor(() => {
      expect(screen.getByText(/turno abierto/i)).toBeInTheDocument()
    })

    // Cancel to keep session
    await user.click(screen.getByText('Cancelar'))
  })

  it('logout con tickets pendientes muestra advertencia en el dialogo', async () => {
    localStorage.setItem('titan.pendingTickets', JSON.stringify([{ id: 1 }]))

    renderNavbar()
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Cerrar sesión'))

    // ConfirmDialog should show warning about pending tickets
    await waitFor(() => {
      expect(screen.getByText(/tickets pendientes/i)).toBeInTheDocument()
    })

    // Cancel to keep session
    await user.click(screen.getByText('Cancelar'))
  })
})
