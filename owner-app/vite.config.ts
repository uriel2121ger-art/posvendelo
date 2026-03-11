import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'PosVendelo Dueño',
        short_name: 'PosVendelo Dueño',
        description: 'Monitoreo remoto multi-sucursal para POSVENDELO.',
        theme_color: '#0891b2',
        background_color: '#09090f',
        display: 'standalone',
        start_url: '/',
        icons: []
      }
    })
  ]
})
