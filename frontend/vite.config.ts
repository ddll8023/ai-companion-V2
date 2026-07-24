import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 9753,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18080',
        changeOrigin: true,
        // Axios baseURL='/api'，前端路径 '/api/v1/...' → 全路径 '/api/api/v1/...'
        // rewrite 去掉第一个 /api，让后端收到正确的 '/api/v1/...'
        rewrite: (path) => path.replace(/^\/api/, ''),
        // 开发模式下注入授权令牌（对应 backend/.env 中的 AUTH_TOKEN）
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Authorization', 'Bearer dev-auth-token-change-me');
          });
        },
      },
    },
  },
})
