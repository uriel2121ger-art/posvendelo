/**
 * posApi.ts — Tests de auto-discovery, runtime config, apiFetch, y pullTable.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { clearAuth, setAuthToken } from './test-utils'

// Importar después de setup de localStorage
import {
  autoDiscoverBackend,
  loadRuntimeConfig,
  saveRuntimeConfig,
  getUserRole,
} from '../posApi'

describe('loadRuntimeConfig', () => {
  beforeEach(() => clearAuth())
  afterEach(() => clearAuth())

  it('devuelve defaults cuando localStorage vacío', () => {
    const cfg = loadRuntimeConfig()
    expect(cfg.baseUrl).toBe('http://localhost:8000')
    expect(cfg.token).toBe('')
    expect(cfg.terminalId).toBe(1)
  })

  it('lee valores de localStorage', () => {
    localStorage.setItem('titan.baseUrl', 'http://192.168.1.50:8090')
    localStorage.setItem('titan.token', 'jwt-xyz')
    localStorage.setItem('titan.terminalId', '3')

    const cfg = loadRuntimeConfig()
    expect(cfg.baseUrl).toBe('http://192.168.1.50:8090')
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
      ok: false, status: 401,
      body: { cancel: () => Promise.resolve() },
    })

    const result = await autoDiscoverBackend()
    expect(result).toBe('http://127.0.0.1:8090')

    // Solo debe haber hecho 1 fetch (la URL guardada)
    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8090/api/v1/auth/verify',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('descubre por puertos si URL guardada no responde', async () => {
    localStorage.setItem('titan.baseUrl', 'http://127.0.0.1:9999')

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
        ok: false, status: 401,
        body: { cancel: () => Promise.resolve() },
      })
    })

    const result = await autoDiscoverBackend()
    expect(result).toBe('http://localhost:8090')
    expect(localStorage.getItem('titan.baseUrl')).toBe('http://localhost:8090')
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
          ok: false, status: 401,
          body: { cancel: () => Promise.resolve() },
        })
      }
      return Promise.reject(new Error('should not reach'))
    })

    const result = await autoDiscoverBackend()
    expect(result).toBe('http://localhost:8000')
    expect(localStorage.getItem('titan.baseUrl')).toBe('http://localhost:8000')
  })
})
