const DEFAULT_CP_URL =
  (import.meta.env.VITE_CONTROL_PLANE_URL as string | undefined)?.trim() || 'http://127.0.0.1:9090'

const TOKEN_KEY = 'titan.owner.cloudToken'

export type CloudAuthResponse = {
  session_token: string
  tenant_id: number
  tenant_slug: string
  expires_at?: string
  branch_id?: number
  branch_name?: string
  install_token?: string
}

export type CloudMe = {
  cloud_user: {
    id: number
    email: string
    full_name: string | null
    role: string
  }
  tenant: {
    id: number
    name: string
    slug: string
  }
  summary: {
    branches_total: number
    online: number
    offline: number
  }
}

function getBaseUrl(): string {
  return DEFAULT_CP_URL.replace(/\/$/, '')
}

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function apiFetch<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (auth) {
    const token = getStoredToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }
  const response = await fetch(`${getBaseUrl()}${path}`, { ...init, headers })
  const body = (await response.json().catch(() => null)) as
    | { success?: boolean; data?: T; detail?: string }
    | null
  if (response.status === 401) {
    clearToken()
  }
  if (!response.ok || body?.success === false) {
    throw new Error(body?.detail || `HTTP ${response.status}`)
  }
  return (body?.data as T) ?? (body as T)
}

export async function discoverCloud() {
  return apiFetch<{ cp_url: string; discover_url: string; status: string }>('/api/v1/cloud/discover', {}, false)
}

export async function loginCloud(email: string, password: string) {
  return apiFetch<CloudAuthResponse>(
    '/api/v1/cloud/login',
    {
      method: 'POST',
      body: JSON.stringify({ email, password })
    },
    false
  )
}

export async function registerCloud(input: {
  email: string
  password: string
  full_name?: string
  business_name?: string
  branch_name?: string
  link_code?: string
}) {
  return apiFetch<CloudAuthResponse>(
    '/api/v1/cloud/register',
    {
      method: 'POST',
      body: JSON.stringify(input)
    },
    false
  )
}

export async function getMe() {
  return apiFetch<CloudMe>('/api/v1/cloud/me')
}

export async function logoutCloud() {
  return apiFetch<{ revoked: boolean }>('/api/v1/cloud/logout', { method: 'POST' })
}

export async function listNotifications() {
  return apiFetch<Array<Record<string, unknown>>>('/api/v1/cloud/notifications')
}

export async function getPortfolio() {
  return apiFetch<Record<string, unknown>>('/api/v1/owner/portfolio')
}

export async function getOwnerEvents() {
  return apiFetch<Array<Record<string, unknown>>>('/api/v1/owner/events')
}

export async function getOwnerHealthSummary() {
  return apiFetch<Record<string, unknown>>('/api/v1/owner/health-summary')
}

export async function getOwnerAudit() {
  return apiFetch<Array<Record<string, unknown>>>('/api/v1/owner/audit')
}

export async function getOwnerCommercial() {
  return apiFetch<Record<string, unknown>>('/api/v1/owner/commercial')
}

export async function listRemoteRequests() {
  return apiFetch<Array<Record<string, unknown>>>('/api/v1/cloud/remote-requests')
}

export async function createRemoteRequest(input: {
  branch_id: number
  request_type: string
  payload: Record<string, unknown>
  approval_mode?: string
}) {
  return apiFetch<Record<string, unknown>>('/api/v1/cloud/remote-requests', {
    method: 'POST',
    body: JSON.stringify(input)
  })
}

export async function registerBranch(branchName: string) {
  return apiFetch<{ branch_id: number; branch_name: string; branch_slug: string; install_token: string }>(
    '/api/v1/cloud/register-branch',
    {
      method: 'POST',
      body: JSON.stringify({ branch_name: branchName })
    }
  )
}
