import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/personalities': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/story': 'http://localhost:8000'   // ← CRITICAL: forward /story to backend
    }
  }
})