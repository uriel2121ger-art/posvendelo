export type QueuedRemoteActionKind = 'price_change' | 'stock_update' | 'notification'

export type QueuedRemoteAction = {
  id: string
  kind: QueuedRemoteActionKind
  summary: string
  createdAt: string
  payload: Record<string, unknown>
}

const STORAGE_KEY = 'pos.remoteActionQueue'

function safeRead(): QueuedRemoteAction[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? (parsed as QueuedRemoteAction[]) : []
  } catch {
    return []
  }
}

function safeWrite(actions: QueuedRemoteAction[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(actions))
  } catch {
    // Ignore quota/storage errors; queue is best-effort.
  }
}

export function loadQueuedRemoteActions(): QueuedRemoteAction[] {
  return safeRead()
}

export function enqueueRemoteAction(
  action: Omit<QueuedRemoteAction, 'id' | 'createdAt'>
): QueuedRemoteAction[] {
  const current = safeRead()
  const next: QueuedRemoteAction[] = [
    ...current,
    {
      ...action,
      id: typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      createdAt: new Date().toISOString()
    }
  ]
  safeWrite(next)
  return next
}

export function removeQueuedRemoteAction(actionId: string): QueuedRemoteAction[] {
  const next = safeRead().filter((item) => item.id !== actionId)
  safeWrite(next)
  return next
}

export function clearQueuedRemoteActions(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore storage errors.
  }
}
