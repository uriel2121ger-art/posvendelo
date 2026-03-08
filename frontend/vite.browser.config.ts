import { resolve } from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined
  if (id.includes('react-router')) return 'router-vendor'
  if (id.includes('lucide-react')) return 'icons-vendor'
  if (id.includes('xlsx')) return 'xlsx-vendor'
  if (id.includes('/react/') || id.includes('react-dom')) return 'react-vendor'
  return 'vendor'
}

function readEnv(name: string, fallback: string): string {
  const value = process.env[name]?.trim()
  return value || fallback
}

const browserHost = readEnv('TITAN_BROWSER_HOST', '127.0.0.1')
const browserPort = Number.parseInt(readEnv('TITAN_BROWSER_PORT', '5173'), 10)
const browserOrigin = readEnv('TITAN_BROWSER_URL', `http://${browserHost}:${browserPort}`)
const apiBaseUrl = readEnv('TITAN_API_URL', 'http://127.0.0.1:8000')

// Standalone config for browser-only (no Electron).
// dev: modo desarrollo (HMR). build: producción (minificado). preview: sirve el build.
export default defineConfig(({ command, mode }) => ({
  mode: command === 'build' ? 'production' : 'development',
  root: resolve(__dirname, 'src/renderer'),
  resolve: {
    alias: {
      '@renderer': resolve(__dirname, 'src/renderer/src')
    }
  },
  plugins: [react()],
  build: {
    outDir: 'dist-browser',
    emptyOutDir: true,
    minify: mode === 'production',
    sourcemap: mode !== 'production',
    rollupOptions: {
      output: {
        manualChunks
      }
    }
  },
  preview: {
    port: browserPort,
    strictPort: true,
    open: browserOrigin,
    proxy: {
      '/api': { target: apiBaseUrl, changeOrigin: true },
      '/health': { target: apiBaseUrl, changeOrigin: true }
    }
  },
  server: {
    port: browserPort,
    strictPort: true,
    open: browserOrigin,
    proxy: {
      '/api': {
        target: apiBaseUrl,
        changeOrigin: true
      },
      '/health': {
        target: apiBaseUrl,
        changeOrigin: true
      }
    }
  }
}))
