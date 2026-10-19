import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // 浏览器始终请求同源 /api；仅本地测试可用环境变量改代理目标端口。
      '/api': process.env.JOB_API_TARGET || 'http://127.0.0.1:8000',
    },
  },
})
