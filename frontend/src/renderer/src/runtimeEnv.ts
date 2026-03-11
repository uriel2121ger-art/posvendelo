function readString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function readStringList(value: unknown, fallback: string[]): string[] {
  const raw = readString(value)
  if (!raw) return fallback
  const parsed = raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  return parsed.length > 0 ? parsed : fallback
}

function readPortList(value: unknown, fallback: number[]): number[] {
  const raw = readString(value)
  if (!raw) return fallback
  const parsed = raw
    .split(',')
    .map((item) => Number.parseInt(item.trim(), 10))
    .filter((port) => Number.isInteger(port) && port > 0 && port < 65536)
  return parsed.length > 0 ? parsed : fallback
}

const currentProtocol =
  typeof window !== 'undefined' && /^https?:$/.test(window.location.protocol)
    ? window.location.protocol
    : 'http:'
const currentHost =
  typeof window !== 'undefined' ? window.location.hostname || '127.0.0.1' : '127.0.0.1'
const browserPort = readString(import.meta.env.VITE_TITAN_BROWSER_PORT) ?? '5173'
const isDevBrowser =
  typeof window !== 'undefined' && import.meta.env.DEV && window.location.port === browserPort
const defaultDiscoverPorts = isDevBrowser ? [8000, 8080, 8090, 3000] : [8000, 8080]

export const TITAN_API_URL =
  readString(import.meta.env.VITE_TITAN_API_URL) ?? `${currentProtocol}//${currentHost}:8000`
export const TITAN_DISCOVER_HOSTS = readStringList(import.meta.env.VITE_TITAN_DISCOVER_HOSTS, [
  currentHost
])
export const TITAN_DISCOVER_PORTS = readPortList(
  import.meta.env.VITE_TITAN_DISCOVER_PORTS,
  defaultDiscoverPorts
)
export const TITAN_BROWSER_PORT = browserPort
export const TITAN_APP_LABEL = readString(import.meta.env.VITE_TITAN_APP_LABEL) ?? 'POSVENDELO'
export const TITAN_RELEASE_LABEL = readString(import.meta.env.VITE_TITAN_RELEASE_LABEL)
