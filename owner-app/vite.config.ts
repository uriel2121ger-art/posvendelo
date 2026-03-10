import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'TITAN Dueño',
        short_name: 'TITAN Dueño',
        description: 'Monitoreo remoto multi-sucursal para TITAN POS.',
        theme_color: '#0891b2',
        background_color: '#09090f',
        display: 'standalone',
        start_url: '/',
        icons: []
      }
    })
  ]
})
