import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import istanbul from 'vite-plugin-istanbul'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    ...(process.env.E2E_COVERAGE === '1'
      ? [istanbul({
          include: 'src/*',
          exclude: ['node_modules', 'test/', '**/*.spec.ts', '**/__tests__/**', 'src/types/generated/**'],
          extension: ['.js', '.ts', '.vue'],
          forceBuildInstrument: true,
        })]
      : []),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Tauri 桌面应用,目标用户都是较新的 Chromium,可放心用现代语法
    target: 'es2022',
    rollupOptions: {
      output: {
        // 将体积较大的第三方依赖拆出独立 vendor chunk,减少首屏与
        // 模块视图分包之间的重复打包。
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes('vue-router') || id.includes('/vue/') || id.endsWith('/vue') || id.includes('pinia')) {
            return 'vendor-vue'
          }
          if (id.includes('@tauri-apps')) {
            return 'vendor-tauri'
          }
          if (id.includes('@vicons')) {
            return 'vendor-icons'
          }
          return 'vendor'
        },
      },
    },
  },
})
