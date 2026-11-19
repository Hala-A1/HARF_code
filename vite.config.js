import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: { deny: ['**/.env', '**/.env.*', '**/*.{crt,pem}', '**/.git/**', '**/backend/**', '**/Copywriter/**', '**/instructions/**', '**/backups/**', '**/reports/**', '**/tmp/**', '**/output/**'] },
    watch: { ignored: ['**/reports/**', '**/backend/**', '**/Copywriter/**', '**/instructions/**', '**/~$*', '**/*.tmp'] },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        configure(proxy) {
          proxy.on('error', (_error, _request, response) => {
            if (!response || response.headersSent || typeof response.writeHead !== 'function') return
            response.writeHead(503, { 'Content-Type': 'application/json' })
            response.end(JSON.stringify({ detail: 'The application server is unavailable. Please retry in a moment. If this continues, contact your administrator.' }))
          })
        },
      },
    },
  },
})
