import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'SNACKPRESS_')
  return {
    plugins: [react(), tailwindcss()],
    server: { proxy: { '/api': env.SNACKPRESS_API_PROXY || 'http://127.0.0.1:8000' } },
    build: { chunkSizeWarningLimit: 900 },
  }
})
