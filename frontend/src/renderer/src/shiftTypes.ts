/** Shared shift types and localStorage helpers used by ShiftsTab, Terminal, App, and ShiftStartupModal. */

export type ShiftRecord = {
  id: string
  backendTurnId?: number
  terminalId: number
  openedAt: string
  openedBy: string
  openingCash: number
  status: 'open' | 'closed'
  salesCount?: number
  totalSales?: number
  cashSales?: number
  cardSales?: number
  transferSales?: number
  lastSaleAt?: string
  closedAt?: string
  closingCash?: number
  expectedCash?: number
  cashDifference?: number
  notes?: string
}

export const CURRENT_SHIFT_KEY = 'titan.currentShift'
export const SHIFT_HISTORY_KEY = 'titan.shiftHistory'

export function readCurrentShift(): ShiftRecord | null {
  try {
    const raw = localStorage.getItem(CURRENT_SHIFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ShiftRecord
    return parsed?.status === 'open' ? parsed : null
  } catch {
    return null
  }
}

export function saveCurrentShift(shift: ShiftRecord | null): void {
  try {
    if (!shift) {
      localStorage.removeItem(CURRENT_SHIFT_KEY)
      return
    }
    localStorage.setItem(CURRENT_SHIFT_KEY, JSON.stringify(shift))
  } catch {
    // QuotaExceededError — shift stays in memory state only
  }
}

export function readShiftHistory(): ShiftRecord[] {
  try {
    const raw = localStorage.getItem(SHIFT_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ShiftRecord[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveShiftHistory(history: ShiftRecord[]): void {
  try {
    localStorage.setItem(SHIFT_HISTORY_KEY, JSON.stringify(history.slice(0, 100)))
  } catch {
    // QuotaExceededError — history stays in memory state only
  }
}
