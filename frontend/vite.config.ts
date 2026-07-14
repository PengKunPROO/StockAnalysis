import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        proxyTimeout: 300000, // 5 min timeout for long-running SSE (AI diagnosis)
        timeout: 300000,
      }
    }
  },
  build: { outDir: '../backend/static', emptyOutDir: true },
})
