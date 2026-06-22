import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const isTauri = process.env.TAURI_ENV_PLATFORM !== undefined

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Tauri 빌드 시에는 프록시 불필요 (직접 서버 URL 사용)
  server: isTauri ? {} : {
    proxy: {
      '/api': 'http://localhost:8010',
      '/health': 'http://localhost:8010',
    },
  },
  // Tauri는 파일 프로토콜 사용
  base: isTauri ? './' : '/',
})
