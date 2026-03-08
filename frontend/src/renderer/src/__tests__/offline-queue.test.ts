import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  clearQueuedRemoteActions,
  enqueueRemoteAction,
  loadQueuedRemoteActions,
  removeQueuedRemoteAction
} from '../utils/offlineQueue'

describe('offlineQueue', () => {
  beforeEach(() => clearQueuedRemoteActions())
  afterEach(() => clearQueuedRemoteActions())

  it('encola acciones remotas', () => {
    const queue = enqueueRemoteAction({
      kind: 'notification',
      summary: 'Mensaje urgente',
      payload: { title: 'Urgente', body: 'Revisar caja' }
    })

    expect(queue).toHaveLength(1)
    expect(queue[0].kind).toBe('notification')
    expect(loadQueuedRemoteActions()).toHaveLength(1)
  })

  it('remueve acciones por id', () => {
    const queue = enqueueRemoteAction({
      kind: 'stock_update',
      summary: 'Ajuste de stock',
      payload: { sku: 'ABC', quantity: 2 }
    })

    const remaining = removeQueuedRemoteAction(queue[0].id)
    expect(remaining).toHaveLength(0)
    expect(loadQueuedRemoteActions()).toHaveLength(0)
  })
})
