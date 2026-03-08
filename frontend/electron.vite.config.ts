import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined
  if (id.includes('react-router')) return 'router-vendor'
  if (id.includes('lucide-react')) return 'icons-vendor'
  if (id.includes('xlsx')) return 'xlsx-vendor'
  if (id.includes('/react/') || id.includes('react-dom')) return 'react-vendor'
  return 'vendor'
}

export default defineConfig({
  main: {},
  preload: {
    build: {
      rollupOptions: {
        external: []
      }
    }
  },
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks
        }
      }
    },
    plugins: [react()]
  }
})
