/**
 * HardwareTab.tsx — Tests de secciones, configuración, discover y acciones.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import HardwareTab from '../HardwareTab'
import { clearAuth, setAuthToken } from './test-utils'

// Mock posApi — cada función devuelve datos realistas
const mockGetHardwareConfig = vi.fn()
const mockUpdateHardwareConfig = vi.fn()
const mockDiscoverPrinters = vi.fn()
const mockTestPrint = vi.fn()
const mockTestDrawer = vi.fn()

vi.mock('../posApi', () => ({
  loadRuntimeConfig: () => ({ baseUrl: 'http://127.0.0.1:8090', token: 'test', terminalId: 1 }),
  getHardwareConfig: (...args: unknown[]) => mockGetHardwareConfig(...args),
  updateHardwareConfig: (...args: unknown[]) => mockUpdateHardwareConfig(...args),
  discoverPrinters: (...args: unknown[]) => mockDiscoverPrinters(...args),
  testPrint: (...args: unknown[]) => mockTestPrint(...args),
  testDrawer: (...args: unknown[]) => mockTestDrawer(...args),
}))

const MOCK_HW_CONFIG = {
  printer: {
    name: 'TICKET',
    enabled: true,
    paper_width: 58,
    char_width: 32,
    auto_print: true,
    mode: 'basic',
    cut_type: 'partial',
  },
  business: {
    name: 'TITAN POS Demo',
    legal_name: 'Demo SA de CV',
    rfc: 'XAXX010101000',
    regimen: '601',
    phone: '5555555555',
    address: 'Av. Ejemplo 123 CDMX',
    footer: 'Gracias por su compra',
  },
  scanner: {
    enabled: true,
    prefix: '',
    suffix: '',
    min_speed_ms: 50,
    auto_submit: true,
  },
  drawer: {
    enabled: true,
    printer_name: 'TICKET',
    auto_open_cash: true,
    auto_open_card: false,
    auto_open_transfer: false,
  },
}

function renderHW() {
  return render(
    <MemoryRouter initialEntries={['/hardware']}>
      <HardwareTab />
    </MemoryRouter>,
  )
}

describe('HardwareTab', () => {
  beforeEach(() => {
    clearAuth()
    setAuthToken()
    mockGetHardwareConfig.mockResolvedValue(structuredClone(MOCK_HW_CONFIG))
    mockUpdateHardwareConfig.mockResolvedValue(undefined)
    mockDiscoverPrinters.mockResolvedValue([])
    mockTestPrint.mockResolvedValue(undefined)
    mockTestDrawer.mockResolvedValue(undefined)
  })

  afterEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  it('muestra loading mientras carga config', () => {
    // No resolver getHardwareConfig
    mockGetHardwareConfig.mockReturnValue(new Promise(() => {}))
    renderHW()
    expect(screen.getByText('Cargando configuracion de hardware...')).toBeInTheDocument()
  })

  it('muestra título y 4 secciones después de cargar', async () => {
    renderHW()
    await waitFor(() => {
      expect(screen.getByText('Configuracion de Hardware')).toBeInTheDocument()
    })

    expect(screen.getByText('Impresora')).toBeInTheDocument()
    expect(screen.getByText('Negocio')).toBeInTheDocument()
    expect(screen.getByText('Scanner')).toBeInTheDocument()
    expect(screen.getByText('Cajon')).toBeInTheDocument()
  })

  it('sección Impresora visible por defecto con nombre TICKET', async () => {
    renderHW()
    await waitFor(() => {
      expect(screen.getByText('Impresora de Tickets')).toBeInTheDocument()
    })

    expect(screen.getByDisplayValue('TICKET')).toBeInTheDocument()
    expect(screen.getByText('Detectar Impresoras')).toBeInTheDocument()
    expect(screen.getByText('Imprimir Prueba')).toBeInTheDocument()
    expect(screen.getByText('Guardar Impresora')).toBeInTheDocument()
  })

  it('cambiar a sección Negocio muestra campos del negocio', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Impresora')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Negocio'))

    expect(screen.getByText('Datos del Negocio')).toBeInTheDocument()
    expect(screen.getByDisplayValue('TITAN POS Demo')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Demo SA de CV')).toBeInTheDocument()
    expect(screen.getByDisplayValue('XAXX010101000')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Av. Ejemplo 123 CDMX')).toBeInTheDocument()
    expect(screen.getByText('Guardar Datos del Negocio')).toBeInTheDocument()
  })

  it('cambiar a sección Scanner muestra toggles del scanner', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Scanner')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Scanner'))

    expect(screen.getByText('Lector de Codigo de Barras')).toBeInTheDocument()
    expect(screen.getByText('Scanner habilitado')).toBeInTheDocument()
    expect(screen.getByText('Auto-submit al escanear')).toBeInTheDocument()
    expect(screen.getByText('Guardar Scanner')).toBeInTheDocument()
  })

  it('cambiar a sección Cajón muestra botón de prueba y toggles', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Cajon')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Cajon'))

    expect(screen.getByText('Cajon de Dinero')).toBeInTheDocument()
    expect(screen.getByText('Probar Cajon')).toBeInTheDocument()
    expect(screen.getByText('Cajon habilitado')).toBeInTheDocument()
    expect(screen.getByText('Abrir con pago en efectivo')).toBeInTheDocument()
    expect(screen.getByText('Guardar Cajon')).toBeInTheDocument()
  })

  it('Detectar Impresoras llama discoverPrinters', async () => {
    mockDiscoverPrinters.mockResolvedValue([
      { name: 'TICKET', status: 'idle', enabled: true, is_default: true },
      { name: 'PDF', status: 'idle', enabled: true, is_default: false },
    ])

    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Detectar Impresoras')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Detectar Impresoras'))

    await waitFor(() => {
      expect(mockDiscoverPrinters).toHaveBeenCalledTimes(1)
      expect(screen.getByText('2 impresora(s) detectada(s)')).toBeInTheDocument()
    })

    // Tabla de impresoras
    expect(screen.getByText('TICKET')).toBeInTheDocument()
    expect(screen.getByText('PDF')).toBeInTheDocument()
  })

  it('Imprimir Prueba llama testPrint', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Imprimir Prueba')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Imprimir Prueba'))

    await waitFor(() => {
      expect(mockTestPrint).toHaveBeenCalledTimes(1)
      expect(screen.getByText('Ticket de prueba enviado')).toBeInTheDocument()
    })
  })

  it('Probar Cajón llama testDrawer', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Cajon')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Cajon'))
    await user.click(screen.getByText('Probar Cajon'))

    await waitFor(() => {
      expect(mockTestDrawer).toHaveBeenCalledTimes(1)
      expect(screen.getByText('Cajon de prueba abierto')).toBeInTheDocument()
    })
  })

  it('Guardar Impresora llama updateHardwareConfig con datos correctos', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Guardar Impresora')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Guardar Impresora'))

    await waitFor(() => {
      expect(mockUpdateHardwareConfig).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://127.0.0.1:8090' }),
        'printer',
        expect.objectContaining({
          receipt_printer_name: 'TICKET',
          receipt_printer_enabled: true,
          receipt_paper_width: 58,
        }),
      )
    })
  })

  it('Guardar Negocio envía datos del negocio', async () => {
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Negocio')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Negocio'))
    await user.click(screen.getByText('Guardar Datos del Negocio'))

    await waitFor(() => {
      expect(mockUpdateHardwareConfig).toHaveBeenCalledWith(
        expect.anything(),
        'business',
        expect.objectContaining({
          business_name: 'TITAN POS Demo',
          business_rfc: 'XAXX010101000',
        }),
      )
    })
  })

  it('error al cargar config permanece en estado loading', async () => {
    // Cuando getHardwareConfig falla, hw queda null → se muestra loading
    // El msg de error se setea pero solo es visible cuando hw != null
    mockGetHardwareConfig.mockRejectedValue(new Error('Conexion rechazada'))
    renderHW()

    // El componente sigue mostrando loading porque hw nunca se setea
    await waitFor(() => {
      expect(mockGetHardwareConfig).toHaveBeenCalled()
    })
    expect(screen.getByText('Cargando configuracion de hardware...')).toBeInTheDocument()
  })

  it('error en testPrint muestra mensaje de error', async () => {
    mockTestPrint.mockRejectedValue(new Error('Impresora desconectada'))
    renderHW()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Imprimir Prueba')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Imprimir Prueba'))

    await waitFor(() => {
      expect(screen.getByText('Error: Impresora desconectada')).toBeInTheDocument()
    })
  })
})
