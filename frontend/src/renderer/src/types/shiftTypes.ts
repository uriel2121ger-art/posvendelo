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

function normalizeTerminalId(terminalId?: number | null): number {
  return Math.max(1, Number.parseInt(String(terminalId ?? 1), 10) || 1)
}

export function getCurrentShiftStorageKey(terminalId?: number | null): string {
  return `${CURRENT_SHIFT_KEY}.${normalizeTerminalId(terminalId)}`
}

export function getShiftHistoryStorageKey(terminalId?: number | null): string {
  return `${SHIFT_HISTORY_KEY}.${normalizeTerminalId(terminalId)}`
}

export function isShiftStorageKey(key: string | null): boolean {
  return (
    key === CURRENT_SHIFT_KEY ||
    key === SHIFT_HISTORY_KEY ||
    key?.startsWith(`${CURRENT_SHIFT_KEY}.`) === true ||
    key?.startsWith(`${SHIFT_HISTORY_KEY}.`) === true
  )
}

export function readCurrentShift(expectedTerminalId?: number | null): ShiftRecord | null {
  try {
    const terminalId = normalizeTerminalId(expectedTerminalId)
    const raw =
      localStorage.getItem(getCurrentShiftStorageKey(terminalId)) ??
      localStorage.getItem(CURRENT_SHIFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ShiftRecord
    if (parsed?.status !== 'open') return null
    if (
      expectedTerminalId != null &&
      Number.isFinite(expectedTerminalId) &&
      (parsed.terminalId ?? 1) !== expectedTerminalId
    ) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function saveCurrentShift(shift: ShiftRecord | null, terminalId?: number | null): void {
  try {
    const effectiveTerminalId = shift?.terminalId ?? normalizeTerminalId(terminalId)
    const storageKey = getCurrentShiftStorageKey(effectiveTerminalId)
    if (!shift) {
      localStorage.removeItem(storageKey)
      if (terminalId == null) {
        localStorage.removeItem(CURRENT_SHIFT_KEY)
      }
      return
    }
    localStorage.setItem(storageKey, JSON.stringify(shift))
  } catch {
    // QuotaExceededError — shift stays in memory state only
  }
}

export function readShiftHistory(terminalId?: number | null): ShiftRecord[] {
  try {
    const raw =
      localStorage.getItem(getShiftHistoryStorageKey(terminalId)) ??
      localStorage.getItem(SHIFT_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ShiftRecord[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveShiftHistory(history: ShiftRecord[], terminalId?: number | null): void {
  try {
    localStorage.setItem(
      getShiftHistoryStorageKey(terminalId),
      JSON.stringify(history.slice(0, 100))
    )
  } catch {
    // QuotaExceededError — history stays in memory state only
  }
}
