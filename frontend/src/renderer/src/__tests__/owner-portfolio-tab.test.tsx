import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import OwnerPortfolioTab from '../tabs/OwnerPortfolioTab'

describe('OwnerPortfolioTab', () => {
  beforeEach(() => {
    ;(
      window as Window & {
        api?: {
          agent?: {
            getOwnerPortfolio?: () => Promise<unknown>
            getOwnerEvents?: () => Promise<unknown>
            getOwnerBranchTimeline?: (branchId: number) => Promise<unknown>
            getOwnerCommercial?: () => Promise<unknown>
            getOwnerHealthSummary?: () => Promise<unknown>
            getOwnerAudit?: () => Promise<unknown>
          }
        }
      }
    ).api = {
      agent: {
        getOwnerPortfolio: vi.fn().mockResolvedValue({
          tenantName: 'Tenant Demo',
          tenantSlug: 'tenant-demo',
          branchesTotal: 2,
          online: 1,
          offline: 1,
          salesTodayTotal: 1550.5,
          alertsTotal: 1,
          branches: [{ id: 1, branch_name: 'Sucursal Centro', branch_slug: 'centro', is_online: 1 }],
          alerts: [{ kind: 'install_error', message: 'compose failed' }],
          lastError: null
        }),
        getOwnerEvents: vi.fn().mockResolvedValue({
          events: [{ event_type: 'heartbeat.ok', message: 'Heartbeat ok recibido', branch_name: 'Sucursal Centro' }],
          lastError: null
        }),
        getOwnerBranchTimeline: vi.fn().mockResolvedValue({
          timeline: [{ heartbeat_id: 101, status: 'ok', sales_today: 1550.5, disk_used_pct: 40 }],
          lastError: null
        }),
        getOwnerCommercial: vi.fn().mockResolvedValue({
          license: { license_type: 'monthly', status: 'active' },
          health: {
            days_until_valid: 12,
            days_until_support: 25,
            reminder_types: ['license_expiring']
          },
          events: [{ id: 1, event_type: 'license.renew', actor: 'admin', created_at: '2026-03-08T10:00:00' }],
          lastError: null
        }),
        getOwnerHealthSummary: vi.fn().mockResolvedValue({
          summary: {
            healthy: 1,
            critical: 1,
            stale_backups: 1,
            version_drift: 1,
            expected_pos_version: '2.1.0'
          },
          lastError: null
        }),
        getOwnerAudit: vi.fn().mockResolvedValue({
          audit: [
            {
              id: 7,
              action: 'tunnel.provision',
              actor: 'admin',
              branch_name: 'Sucursal Centro',
              created_at: '2026-03-08T10:05:00'
            }
          ],
          lastError: null
        })
      }
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete (window as Window & { api?: unknown }).api
  })

  it('renderiza estado comercial y portfolio remoto', async () => {
    render(<OwnerPortfolioTab />)

    await waitFor(() => {
      expect(screen.getByText('Portfolio del dueño')).toBeInTheDocument()
      expect(screen.getByText('Tenant Demo • tenant-demo')).toBeInTheDocument()
    })

    expect(screen.getByText('monthly')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText(/Atención requerida: license_expiring/i)).toBeInTheDocument()
    expect(screen.getByText('license.renew')).toBeInTheDocument()
    expect(screen.getByText('Salud de flota')).toBeInTheDocument()
    expect(screen.getByText('Auditoría central')).toBeInTheDocument()
    expect(screen.getByText('tunnel.provision')).toBeInTheDocument()
    expect(screen.getByText('Sucursal Centro')).toBeInTheDocument()
  })
})
