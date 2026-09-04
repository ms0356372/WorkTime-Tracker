import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['icon.svg'],
    manifest: {
      name: '工時管家', short_name: '工時管家', description: '離線優先的工時與假別管理工具',
      theme_color: '#0b6b61', background_color: '#f4f7f6', display: 'standalone',
      start_url: '/', lang: 'zh-Hant', orientation: 'portrait-primary',
      icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }],
    },
    workbox: { navigateFallback: 'index.html', globPatterns: ['**/*.{js,css,html,svg}'] },
  })],
})
