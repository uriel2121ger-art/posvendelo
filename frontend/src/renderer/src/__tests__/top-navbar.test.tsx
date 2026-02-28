/**
 * TopNavbar.tsx — Tests de navegación, usuario activo, y logout.
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import TopNavbar from '../components/TopNavbar'
import { clearAuth, setAuthToken } from './test-utils'

function renderNavbar(path = '/terminal') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TopNavbar />
    </MemoryRouter>,
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

  it('logout limpia localStorage y redirige', async () => {
    // Mock window.confirm
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText('Cerrar sesión'))

    expect(localStorage.getItem('titan.token')).toBeNull()
    expect(localStorage.getItem('titan.user')).toBeNull()
    expect(localStorage.getItem('titan.role')).toBeNull()
    expect(window.location.hash).toBe('#/login')
  })

  it('logout cancelado no limpia localStorage', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    renderNavbar()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText('Cerrar sesión'))

    // Token sigue ahí
    expect(localStorage.getItem('titan.token')).toBe('tok')
  })

  it('logout con turno abierto muestra advertencia', async () => {
    localStorage.setItem('titan.currentShift', '42')
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    renderNavbar()
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Cerrar sesión'))

    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining('turno abierto'),
    )
  })

  it('logout con tickets pendientes muestra advertencia', async () => {
    localStorage.setItem('titan.pendingTickets', JSON.stringify([{ id: 1 }]))
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    renderNavbar()
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Cerrar sesión'))

    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining('tickets pendientes'),
    )
  })
})
