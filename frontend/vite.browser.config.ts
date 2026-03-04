import { resolve } from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

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
    sourcemap: mode !== 'production'
  },
  preview: {
    port: 5173,
    strictPort: true,
    open: 'http://127.0.0.1:5173',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  },
  server: {
    port: 5173,
    strictPort: true,
    open: 'http://127.0.0.1:5173',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
}))
