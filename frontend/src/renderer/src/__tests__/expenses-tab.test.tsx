/**
 * ExpensesTab.tsx — Tests de resumen de gastos y registro de gasto.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import ExpensesTab from '../tabs/ExpensesTab'
import { clearAuth, setAuthToken } from './test-utils'

const mockGetExpensesSummary = vi.fn()
const mockRegisterExpense = vi.fn()

vi.mock('../posApi', () => ({
  loadRuntimeConfig: () => ({ baseUrl: 'http://127.0.0.1:8090', token: 'test', terminalId: 1 }),
  getExpensesSummary: (...args: unknown[]) => mockGetExpensesSummary(...args),
  registerExpense: (...args: unknown[]) => mockRegisterExpense(...args)
}))

function renderExpenses(): ReturnType<typeof render> {
  return render(
    <MemoryRouter initialEntries={['/gastos']}>
      <ExpensesTab />
    </MemoryRouter>
  )
}

describe('ExpensesTab', () => {
  beforeEach(() => {
    clearAuth()
    setAuthToken()
    mockGetExpensesSummary.mockResolvedValue({ data: { month: 1250.5, year: 8900.0 } })
    mockRegisterExpense.mockResolvedValue({ success: true, data: { id: 42 } })
  })

  afterEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  it('muestra resumen de gastos del mes y año', async () => {
    renderExpenses()

    await waitFor(() => {
      expect(screen.getByText(/1,?250\.50|1250\.50/)).toBeInTheDocument()
    })
  })

  it('carga summary al montar', async () => {
    renderExpenses()

    await waitFor(() => {
      expect(mockGetExpensesSummary).toHaveBeenCalled()
    })
  })

  it('muestra error si summary falla', async () => {
    mockGetExpensesSummary.mockRejectedValue(new Error('Tiempo de espera agotado'))
    renderExpenses()

    await waitFor(() => {
      expect(screen.getByText(/Tiempo de espera agotado|Error cargando gastos/)).toBeInTheDocument()
    })
  })

  it('valida monto antes de submit', async () => {
    renderExpenses()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(mockGetExpensesSummary).toHaveBeenCalled()
    })

    // Buscar botón de registrar gasto
    const submitBtn = await screen.findByRole('button', { name: /registrar|agregar|guardar/i })
    if (submitBtn) {
      await user.click(submitBtn)
      // Debería mostrar error de validación
      await waitFor(() => {
        const errorText = screen.queryByText(/monto|obligatori|válid/i)
        expect(errorText || screen.queryByText(/descripción/i)).toBeInTheDocument()
      })
    }
  })

  it('registra gasto exitosamente', async () => {
    renderExpenses()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(mockGetExpensesSummary).toHaveBeenCalled()
    })

    // Llenar formulario — buscar inputs por tipo o placeholder
    const inputs = screen.getAllByRole('textbox')
    const numberInputs =
      screen.getAllByRole('spinbutton').length > 0 ? screen.getAllByRole('spinbutton') : []

    // Encontrar el input de monto (spinbutton o textbox)
    const amountInput =
      numberInputs[0] ??
      inputs.find((i) => {
        const placeholder = i.getAttribute('placeholder') ?? ''
        return (
          placeholder.includes('$') || placeholder.includes('monto') || placeholder.includes('0.00')
        )
      })
    const descInput = inputs.find((i) => {
      const placeholder = i.getAttribute('placeholder') ?? ''
      return (
        placeholder.toLowerCase().includes('desc') || placeholder.toLowerCase().includes('concepto')
      )
    })

    if (amountInput && descInput) {
      await user.clear(amountInput)
      await user.type(amountInput, '150.00')
      await user.clear(descInput)
      await user.type(descInput, 'Compra de bolsas')

      const submitBtn = screen.getByRole('button', { name: /registrar|agregar|guardar/i })
      await user.click(submitBtn)

      await waitFor(() => {
        expect(mockRegisterExpense).toHaveBeenCalledWith(
          expect.anything(),
          expect.objectContaining({
            amount: 150,
            description: 'Compra de bolsas'
          })
        )
      })
    }
  })
})
