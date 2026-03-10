import { afterEach, describe, expect, it } from 'vitest'
import {
  getCurrentShiftStorageKey,
  readCurrentShift,
  readShiftHistory,
  saveCurrentShift,
  saveShiftHistory,
  type ShiftRecord
} from '../types/shiftTypes'

const OPEN_SHIFT: ShiftRecord = {
  id: 'shift-1',
  backendTurnId: 501,
  terminalId: 7,
  openedAt: '2026-03-08T10:00:00.000Z',
  openedBy: 'Cajero 1',
  openingCash: 100,
  status: 'open'
}

afterEach(() => {
  localStorage.clear()
})

describe('shiftTypes terminal isolation', () => {
  it('guarda y lee el turno actual por terminal', () => {
    saveCurrentShift(OPEN_SHIFT, 7)

    expect(readCurrentShift(7)?.backendTurnId).toBe(501)
    expect(readCurrentShift(8)).toBeNull()
    expect(localStorage.getItem(getCurrentShiftStorageKey(7))).toBeTruthy()
  })

  it('mantiene historial separado por terminal', () => {
    saveShiftHistory([{ ...OPEN_SHIFT, status: 'closed', closedAt: '2026-03-08T11:00:00.000Z' }], 7)
    saveShiftHistory([{ ...OPEN_SHIFT, id: 'shift-2', terminalId: 8, status: 'closed' }], 8)

    expect(readShiftHistory(7)).toHaveLength(1)
    expect(readShiftHistory(7)[0]?.terminalId).toBe(7)
    expect(readShiftHistory(8)).toHaveLength(1)
    expect(readShiftHistory(8)[0]?.terminalId).toBe(8)
  })
})
