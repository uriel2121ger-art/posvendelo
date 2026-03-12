/**
 * App.tsx — Tests de routing, RequireAuth, y ErrorBoundary.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { clearAuth, setAuthToken } from './test-utils'

// Mock todos los tabs pesados para que no hagan fetch real
vi.mock('../tabs/Terminal', () => ({
  default: () => <div data-testid="terminal-tab">Terminal</div>
}))
vi.mock('../tabs/CustomersTab', () => ({
  default: () => <div data-testid="customers-tab">Clientes</div>
}))
vi.mock('../tabs/ProductsTab', () => ({
  default: () => <div data-testid="products-tab">Productos</div>
}))
vi.mock('../tabs/InventoryTab', () => ({
  default: () => <div data-testid="inventory-tab">Inventario</div>
}))
vi.mock('../tabs/ShiftsTab', () => ({ default: () => <div data-testid="shifts-tab">Turnos</div> }))
vi.mock('../tabs/ReportsTab', () => ({
  default: () => <div data-testid="reports-tab">Reportes</div>
}))
vi.mock('../tabs/HistoryTab', () => ({
  default: () => <div data-testid="history-tab">Historial</div>
}))
vi.mock('../tabs/SettingsTab', () => ({
  default: () => <div data-testid="settings-tab">Configuraciones</div>
}))
vi.mock('../tabs/DashboardStatsTab', () => ({
  default: () => <div data-testid="stats-tab">Estadísticas</div>
}))
vi.mock('../tabs/MermasTab', () => ({ default: () => <div data-testid="mermas-tab">Mermas</div> }))
vi.mock('../tabs/ExpensesTab', () => ({
  default: () => <div data-testid="expenses-tab">Gastos</div>
}))
vi.mock('../tabs/EmployeesTab', () => ({
  default: () => <div data-testid="employees-tab">Empleados</div>
}))
vi.mock('../tabs/RemoteTab', () => ({ default: () => <div data-testid="remote-tab">Remoto</div> }))
vi.mock('../tabs/FiscalTab', () => ({ default: () => <div data-testid="fiscal-tab">Fiscal</div> }))
vi.mock('../tabs/OwnerPortfolioTab', () => ({
  default: () => <div data-testid="owner-portfolio-tab">Portfolio</div>
}))
vi.mock('../tabs/CompanionDevicesTab', () => ({
  default: () => <div data-testid="companion-devices-tab">Dispositivos</div>
}))
vi.mock('../tabs/InitialSetupWizard', () => ({
  default: () => <div data-testid="initial-setup-wizard">Setup inicial</div>
}))

// Mock ShiftStartupModal — auto-resolve para no bloquear tests
function ShiftStartupModalMock({ onComplete }: { onComplete: () => void }): null {
  useEffect(() => {
    onComplete()
  }, [onComplete])
  return null
}

vi.mock('../tabs/ShiftStartupModal', () => ({
  default: ShiftStartupModalMock
}))

// Mock autoDiscoverBackend para Login
vi.mock('../posApi', () => ({
  autoDiscoverBackend: vi.fn().mockResolvedValue('http://127.0.0.1:8090'),
  loadRuntimeConfig: vi
    .fn()
    .mockReturnValue({ baseUrl: 'http://127.0.0.1:8090', token: 'test', terminalId: 1 }),
  saveRuntimeConfig: vi.fn(),
  getLicenseStatus: vi.fn().mockResolvedValue({
    success: true,
    data: { effective_status: 'active', days_remaining: 30 }
  }),
  createCashMovement: vi.fn().mockResolvedValue({}),
  openDrawerForSale: vi.fn().mockResolvedValue({}),
  getCurrentTurn: vi.fn().mockResolvedValue(null),
  pullTable: vi.fn().mockResolvedValue([]),
  getInitialSetupStatus: vi.fn().mockResolvedValue({ completed: true })
}))

// App usa HashRouter internamente, así que importamos directo
import App from '../App'

describe('App Routing', () => {
  beforeEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    clearAuth()
  })

  it('redirige a /login sin token cuando ya hay servidor configurado', async () => {
    localStorage.setItem('titan.baseUrl', 'http://127.0.0.1:8090')
    window.location.hash = '#/'
    render(<App />)

    await waitFor(() => {
      expect(window.location.hash).toBe('#/login')
    })
  })

  it('redirige a /configurar-servidor sin token ni URL configurada (primera vez / APK)', async () => {
    localStorage.removeItem('titan.baseUrl')
    window.location.hash = '#/'
    render(<App />)

    await waitFor(() => {
      expect(window.location.hash).toBe('#/configurar-servidor')
    })
  })

  it('redirige / a /terminal con token', async () => {
    setAuthToken()
    window.location.hash = '#/'
    render(<App />)

    await waitFor(() => {
      expect(window.location.hash).toBe('#/terminal')
    })
  })

  it('muestra Terminal en /terminal con token', async () => {
    setAuthToken()
    window.location.hash = '#/terminal'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('terminal-tab')).toBeInTheDocument()
    })
  })

  it('muestra Productos en /productos con token', async () => {
    setAuthToken()
    window.location.hash = '#/productos'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('products-tab')).toBeInTheDocument()
    })
  })

  it('muestra Clientes en /clientes con token', async () => {
    setAuthToken()
    window.location.hash = '#/clientes'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('customers-tab')).toBeInTheDocument()
    })
  })

  it('muestra Inventario en /inventario con token', async () => {
    setAuthToken()
    window.location.hash = '#/inventario'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('inventory-tab')).toBeInTheDocument()
    })
  })

  it('muestra Turnos en /turnos con token', async () => {
    setAuthToken()
    window.location.hash = '#/turnos'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('shifts-tab')).toBeInTheDocument()
    })
  })

  it('muestra Reportes en /reportes con token', async () => {
    setAuthToken()
    window.location.hash = '#/reportes'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('reports-tab')).toBeInTheDocument()
    })
  })

  it('muestra Historial en /historial con token', async () => {
    setAuthToken()
    window.location.hash = '#/historial'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('history-tab')).toBeInTheDocument()
    })
  })

  it('muestra Configuraciones en /configuraciones con token', async () => {
    setAuthToken()
    window.location.hash = '#/configuraciones'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-tab')).toBeInTheDocument()
    })
  })

  it('muestra Estadisticas en /estadisticas con token', async () => {
    setAuthToken()
    window.location.hash = '#/estadisticas'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('stats-tab')).toBeInTheDocument()
    })
  })

  it('muestra Mermas en /mermas con token', async () => {
    setAuthToken()
    window.location.hash = '#/mermas'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('mermas-tab')).toBeInTheDocument()
    })
  })

  it('muestra Gastos en /gastos con token', async () => {
    setAuthToken()
    window.location.hash = '#/gastos'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('expenses-tab')).toBeInTheDocument()
    })
  })

  it('muestra Hardware en /hardware con token', async () => {
    setAuthToken()
    window.location.hash = '#/hardware'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-tab')).toBeInTheDocument()
    })
  })

  it('muestra Empleados en /empleados con token', async () => {
    setAuthToken()
    window.location.hash = '#/empleados'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('employees-tab')).toBeInTheDocument()
    })
  })

  it('muestra Remoto en /remoto con token', async () => {
    setAuthToken()
    window.location.hash = '#/remoto'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('remote-tab')).toBeInTheDocument()
    })
  })

  it('muestra Fiscal en /fiscal con token', async () => {
    setAuthToken()
    window.location.hash = '#/fiscal'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('fiscal-tab')).toBeInTheDocument()
    })
  })

  it('ruta desconocida redirige a / → /terminal con token', async () => {
    setAuthToken()
    window.location.hash = '#/esta-ruta-no-existe'
    render(<App />)

    await waitFor(() => {
      expect(window.location.hash).toBe('#/terminal')
    })
  })


  it('redirige a /setup-inicial cuando el setup no está completo', async () => {
    const posApi = await import('../posApi')
    vi.mocked(posApi.getInitialSetupStatus).mockResolvedValueOnce({
      completed: false,
      completed_at: null,
      business_name: '',
      printer_name: ''
    })

    setAuthToken()
    window.location.hash = '#/terminal'
    render(<App />)

    await waitFor(() => {
      expect(window.location.hash).toBe('#/setup-inicial')
      expect(screen.getByTestId('initial-setup-wizard')).toBeInTheDocument()
    })
  })

  it('ruta protegida sin token redirige a /login cuando hay baseUrl', async () => {
    localStorage.setItem('titan.baseUrl', 'http://127.0.0.1:8090')
    window.location.hash = '#/productos'
    render(<App />)

    await waitFor(() => {
      expect(window.location.hash).toBe('#/login')
    })
  })
})

describe('F-key Navigation', () => {
  beforeEach(() => {
    clearAuth()
    setAuthToken()
  })

  afterEach(() => {
    clearAuth()
  })

  // F1-F6: navigation keys (navigate to tab routes)
  const fKeyNavMap: Array<[string, string, string]> = [
    ['F1', '#/terminal', 'terminal-tab'],
    ['F2', '#/clientes', 'customers-tab'],
    ['F3', '#/productos', 'products-tab'],
    ['F4', '#/inventario', 'inventory-tab'],
    ['F5', '#/turnos', 'shifts-tab'],
    ['F6', '#/reportes', 'reports-tab']
  ]

  for (const [key, expectedHash] of fKeyNavMap) {
    it(`${key} navega a ${expectedHash}`, async () => {
      window.location.hash = '#/terminal'
      render(<App />)

      // Wait for setup check + shift modal to resolve (async microtasks)
      await waitFor(() => {
        expect(screen.getByTestId('terminal-tab')).toBeInTheDocument()
      })
      // Allow ShiftStartupModal mock to mount and call onComplete
      await new Promise((r) => setTimeout(r, 50))

      fireEvent.keyDown(window, { key, bubbles: true })

      await waitFor(() => {
        expect(window.location.hash).toBe(expectedHash)
      })
    })
  }

  // F7-F9: operational keys (open modals, do NOT navigate)
  const fKeyModalMap: Array<[string, string]> = [
    ['F7', 'Entrada de efectivo'],
    ['F8', 'Retiro de efectivo'],
    ['F9', 'Verificador de precios']
  ]

  for (const [key, modalTitle] of fKeyModalMap) {
    it(`${key} abre modal "${modalTitle}" sin cambiar ruta`, async () => {
      window.location.hash = '#/terminal'
      render(<App />)

      await waitFor(() => {
        expect(screen.getByTestId('terminal-tab')).toBeInTheDocument()
      })
      await new Promise((r) => setTimeout(r, 50))

      fireEvent.keyDown(window, { key, bubbles: true })

      // Route must NOT change
      expect(window.location.hash).toBe('#/terminal')

      // Modal must appear
      await waitFor(() => {
        expect(screen.getByText(modalTitle)).toBeInTheDocument()
      })
    })
  }

  // F10-F11: handled by Terminal.tsx (capture phase), App does nothing
  for (const key of ['F10', 'F11']) {
    it(`${key} no navega (manejado por Terminal)`, async () => {
      window.location.hash = '#/terminal'
      render(<App />)

      await waitFor(() => {
        expect(screen.getByTestId('terminal-tab')).toBeInTheDocument()
      })

      fireEvent.keyDown(window, { key, bubbles: true })

      // Route must NOT change
      expect(window.location.hash).toBe('#/terminal')
    })
  }

  it('F-keys navegan incluso con focus en input (fix: F-keys no producen texto)', async () => {
    window.location.hash = '#/terminal'
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('terminal-tab')).toBeInTheDocument()
    })
    await new Promise((r) => setTimeout(r, 50))

    // Simular focus en input
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    fireEvent.keyDown(window, { key: 'F3', bubbles: true })

    // F-keys ahora navegan incluso con input focused (no producen texto)
    await waitFor(() => {
      expect(window.location.hash).toBe('#/productos')
    })

    document.body.removeChild(input)
  })
})
