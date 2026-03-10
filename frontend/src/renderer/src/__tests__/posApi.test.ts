/**
 * posApi.ts — Tests de auto-discovery, runtime config, apiFetch, y pullTable.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { clearAuth } from './test-utils'

// Importar después de setup de localStorage
import {
  autoDiscoverBackend,
  loadRuntimeConfig,
  saveRuntimeConfig,
  getUserRole,
  getCurrentTurn,
  getBackupStatus,
  listBackups,
  buildRestorePlan,
  cancelSale,
  remoteCancelSale
} from '../posApi'

const DEFAULT_HOST = window.location.hostname || '127.0.0.1'
const DEFAULT_BASE_URL = `http://${DEFAULT_HOST}:8000`

describe('loadRuntimeConfig', () => {
  beforeEach(() => clearAuth())
  afterEach(() => clearAuth())

  it('devuelve defaults cuando localStorage vacío', () => {
    const cfg = loadRuntimeConfig()
    expect(cfg.baseUrl).toBe(DEFAULT_BASE_URL)
    expect(cfg.token).toBe('')
    expect(cfg.terminalId).toBe(1)
  })

  it('lee valores de localStorage', () => {
    localStorage.setItem('titan.baseUrl', 'http://pos-sucursal.local:8090')
    localStorage.setItem('titan.token', 'jwt-xyz')
    localStorage.setItem('titan.terminalId', '3')

    const cfg = loadRuntimeConfig()
    expect(cfg.baseUrl).toBe('http://pos-sucursal.local:8090')
    expect(cfg.token).toBe('jwt-xyz')
    expect(cfg.terminalId).toBe(3)
  })

  it('terminalId mínimo es 1', () => {
    localStorage.setItem('titan.terminalId', '0')
    expect(loadRuntimeConfig().terminalId).toBe(1)

    localStorage.setItem('titan.terminalId', '-5')
    expect(loadRuntimeConfig().terminalId).toBe(1)

    localStorage.setItem('titan.terminalId', 'abc')
    expect(loadRuntimeConfig().terminalId).toBe(1)
  })
})

describe('saveRuntimeConfig', () => {
  beforeEach(() => clearAuth())
  afterEach(() => clearAuth())

  it('guarda config en localStorage', () => {
    saveRuntimeConfig({ baseUrl: 'http://test:9000', token: 'tok123', terminalId: 2 })
    expect(localStorage.getItem('titan.baseUrl')).toBe('http://test:9000')
    expect(localStorage.getItem('titan.token')).toBe('tok123')
    expect(localStorage.getItem('titan.terminalId')).toBe('2')
  })
})

describe('getUserRole', () => {
  beforeEach(() => clearAuth())
  afterEach(() => clearAuth())

  it('devuelve cashier por defecto', () => {
    expect(getUserRole()).toBe('cashier')
  })

  it('devuelve rol guardado', () => {
    localStorage.setItem('titan.role', 'manager')
    expect(getUserRole()).toBe('manager')
  })
})

describe('autoDiscoverBackend', () => {
  beforeEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  it('usa URL guardada si responde 401', async () => {
    localStorage.setItem('titan.baseUrl', 'http://127.0.0.1:8090')

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      body: { cancel: () => Promise.resolve() }
    })

    const result = await autoDiscoverBackend()
    expect(result).toBe('http://127.0.0.1:8090')

    // Solo debe haber hecho 1 fetch (la URL guardada)
    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8090/api/v1/auth/verify',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    )
  })

  it('descubre por puertos si URL guardada no responde', async () => {
    localStorage.setItem('titan.baseUrl', 'http://127.0.0.1:9999')
    localStorage.setItem('titan.discoverPorts', JSON.stringify([8000, 8080, 8090]))

    let callIdx = 0
    global.fetch = vi.fn().mockImplementation(() => {
      callIdx++
      // Primera llamada (URL guardada 9999): falla
      if (callIdx === 1) return Promise.reject(new Error('conn refused'))
      // Segunda llamada (puerto 8000): falla
      if (callIdx === 2) return Promise.reject(new Error('conn refused'))
      // Tercera llamada (puerto 8080): falla
      if (callIdx === 3) return Promise.reject(new Error('conn refused'))
      // Cuarta llamada (puerto 8090): éxito
      return Promise.resolve({
        ok: false,
        status: 401,
        body: { cancel: () => Promise.resolve() }
      })
    })

    const result = await autoDiscoverBackend()
    expect(result).toBe(`http://${DEFAULT_HOST}:8090`)
    expect(localStorage.getItem('titan.baseUrl')).toBe(`http://${DEFAULT_HOST}:8090`)
  })

  it('devuelve null si ningún puerto responde', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('conn refused'))

    const result = await autoDiscoverBackend()
    expect(result).toBeNull()
  })

  it('descubre sin URL guardada', async () => {
    // Sin baseUrl en localStorage

    let callIdx = 0
    global.fetch = vi.fn().mockImplementation(() => {
      callIdx++
      // Puerto 8000: éxito
      if (callIdx === 1) {
        return Promise.resolve({
          ok: false,
          status: 401,
          body: { cancel: () => Promise.resolve() }
        })
      }
      return Promise.reject(new Error('should not reach'))
    })

    const result = await autoDiscoverBackend()
    expect(result).toBe(DEFAULT_BASE_URL)
    expect(localStorage.getItem('titan.baseUrl')).toBe(DEFAULT_BASE_URL)
  })
})

describe('system recovery API helpers', () => {
  beforeEach(() => {
    clearAuth()
    vi.restoreAllMocks()
    localStorage.setItem('titan.token', 'jwt-xyz')
  })

  afterEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  it('consulta estado de respaldos', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: { backup_count: 2 } }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    })

    const cfg = loadRuntimeConfig()
    const body = await getBackupStatus(cfg)
    expect(body).toEqual({ success: true, data: { backup_count: 2 } })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/system/status'),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer jwt-xyz' })
      })
    )
  })

  it('lista respaldos disponibles', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: [{ name: 'backup.dump' }] }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    })

    const cfg = loadRuntimeConfig()
    const body = await listBackups(cfg)
    expect(body).toEqual({ success: true, data: [{ name: 'backup.dump' }] })
  })

  it('prepara plan de restore', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: { backup_file: 'backup.dump' } }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    })

    const cfg = loadRuntimeConfig()
    const body = await buildRestorePlan(cfg, 'backup.dump')
    expect(body).toEqual({ success: true, data: { backup_file: 'backup.dump' } })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/system/restore-plan'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ backup_file: 'backup.dump' })
      })
    )
  })

  it('consulta turno actual usando terminal_id del runtime', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: { id: 17, status: 'open' } }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    })

    localStorage.setItem('titan.terminalId', '7')
    const cfg = loadRuntimeConfig()
    const body = await getCurrentTurn(cfg)
    expect(body).toEqual({ id: 17, status: 'open' })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/turns/current?terminal_id=7'),
      expect.objectContaining({ headers: expect.objectContaining({ 'X-Terminal-Id': '7' }) })
    )
  })
})

describe('sales API helpers', () => {
  beforeEach(() => {
    clearAuth()
    vi.restoreAllMocks()
    localStorage.setItem('titan.token', 'jwt-xyz')
  })

  afterEach(() => {
    clearAuth()
    vi.restoreAllMocks()
  })

  it('envía manager_pin al cancelar venta', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: { id: 99, status: 'cancelled' } }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    })

    const cfg = loadRuntimeConfig()
    const body = await cancelSale(cfg, '99', {
      manager_pin: '1234',
      reason: 'cobro duplicado'
    })
    expect(body).toEqual({ success: true, data: { id: 99, status: 'cancelled' } })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/sales/99/cancel'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ manager_pin: '1234', reason: 'cobro duplicado' })
      })
    )
  })

  it('envía cancelación remota al endpoint de remote', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true, data: { id: 77, status: 'cancelled' } }),
      text: () => Promise.resolve(''),
      body: { cancel: () => Promise.resolve() }
    })

    const cfg = loadRuntimeConfig()
    const body = await remoteCancelSale(cfg, {
      sale_id: 77,
      manager_pin: '4321',
      reason: 'autorización remota'
    })
    expect(body).toEqual({ success: true, data: { id: 77, status: 'cancelled' } })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/remote/cancel-sale'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          sale_id: 77,
          manager_pin: '4321',
          reason: 'autorización remota'
        })
      })
    )
  })
})
