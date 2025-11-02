import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // 도커 환경에서 외부 접근 허용
    port: 30561,      // 업스테이지 제공 포트
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:30560',  // 백엔드 URL
        changeOrigin: true,
      },
    },
  },
})
