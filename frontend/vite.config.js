import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/games/HeartOfVirtue/',
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/test/**']
    }
  },
  server: {
    port: 3000,
    hmr: false,
    proxy: {
      '/games/HeartOfVirtue/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/games\/HeartOfVirtue/, '')
      },
      // Keep this for any hardcoded /api paths just in case
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
