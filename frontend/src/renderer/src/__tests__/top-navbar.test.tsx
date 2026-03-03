/**
 * Sidebar.tsx — Tests de navegación, usuario activo, y logout.
 * (Originalmente TopNavbar, reescrito para el componente Sidebar.)
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import { ConfirmProvider } from '../components/ConfirmDialog'
import { clearAuth, setAuthToken } from './test-utils'

function renderSidebar(path = '/terminal') {
  return render(
    <ConfirmProvider>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    </ConfirmProvider>,
  )
}

describe('Sidebar', () => {
  beforeEach(() => {
    clearAuth()
    setAuthToken(undefined, 'admin', 'cajero1')
  })

  afterEach(() => {
    clearAuth()
  })

  it('renderiza los 8 links de navegación principal', () => {
    renderSidebar()
    const expectedLabels = [
      'Ventas', 'Productos', 'Inventario', 'Clientes',
      'Turnos', 'Historial', 'Reportes', 'Ajustes',
    ]
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('muestra las iniciales del usuario actual', () => {
    renderSidebar()
    // Sidebar muestra las primeras 2 letras del nombre como iniciales
    expect(screen.getByText('ca')).toBeInTheDocument()
    // El div con iniciales tiene title con el nombre completo
    expect(screen.getByTitle('Usuario Activo: cajero1')).toBeInTheDocument()
  })

  it('muestra "Us" si no hay user en localStorage', () => {
    localStorage.removeItem('titan.user')
    renderSidebar()
    // Default es 'User', iniciales = 'Us'
    expect(screen.getByText('Us')).toBeInTheDocument()
  })

  it('botón de logout existe con title correcto', () => {
    renderSidebar()
    const logoutBtn = screen.getByTitle('Cerrar Sesión')
    expect(logoutBtn).toBeInTheDocument()
  })

  it('logout limpia localStorage y redirige al confirmar', async () => {
    renderSidebar()
    const user = userEvent.setup()

    await user.click(screen.getByTitle('Cerrar Sesión'))

    // ConfirmDialog debe aparecer
    await waitFor(() => {
      expect(screen.getByText('Aceptar')).toBeInTheDocument()
    })

    // Click "Aceptar" para confirmar logout
    await user.click(screen.getByText('Aceptar'))

    expect(localStorage.getItem('titan.token')).toBeNull()
    expect(localStorage.getItem('titan.user')).toBeNull()
    expect(localStorage.getItem('titan.role')).toBeNull()
    expect(window.location.hash).toBe('#/login')
  })

  it('logout cancelado no limpia localStorage', async () => {
    renderSidebar()
    const user = userEvent.setup()

    await user.click(screen.getByTitle('Cerrar Sesión'))

    // ConfirmDialog debe aparecer
    await waitFor(() => {
      expect(screen.getByText('Cancelar')).toBeInTheDocument()
    })

    // Click "Cancelar" para abortar logout
    await user.click(screen.getByText('Cancelar'))

    // Token sigue presente
    expect(localStorage.getItem('titan.token')).not.toBeNull()
  })

  it('logout con tickets pendientes muestra advertencia en el dialogo', async () => {
    localStorage.setItem('titan.pendingTickets', JSON.stringify([{ id: 1 }]))

    renderSidebar()
    const user = userEvent.setup()
    await user.click(screen.getByTitle('Cerrar Sesión'))

    // ConfirmDialog debe mostrar advertencia sobre tickets pendientes
    await waitFor(() => {
      expect(screen.getByText(/tickets pendientes/i)).toBeInTheDocument()
    })

    // Cancelar para mantener sesión
    await user.click(screen.getByText('Cancelar'))
  })

  it('navega correctamente al hacer click en un link', async () => {
    renderSidebar('/terminal')
    const user = userEvent.setup()

    // Click en "Productos"
    await user.click(screen.getByText('Productos'))

    // Verifica que el link apunta a /productos
    const link = screen.getByText('Productos').closest('a')
    expect(link).toHaveAttribute('href', '/productos')
  })
})
