import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Phase D.4.9 — vitest harness consolidated:
// - ``globals: true`` removes the need to ``import { describe, it, expect }``
//   in every spec; rely on the ambient definitions from ``vitest/globals``.
// - ``setupFiles`` points at a shared bootstrap so future Tauri / Pinia /
//   ResizeObserver mocks land in one place.
// - ``coverage`` is configured with the v8 provider but not enabled by
//   default (the ``@vitest/coverage-v8`` peer dep is intentionally not in
//   ``devDependencies`` to keep the install footprint small). Run with
//   ``vitest --coverage`` once installed.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: [
        'src/composables/**/*.ts',
        'src/services/**/*.ts',
        'src/stores/**/*.ts',
        'src/lib/**/*.ts',
      ],
      exclude: [
        'src/**/*.spec.ts',
        'src/**/__tests__/**',
        'src/types/generated/**',
      ],
    },
  },
})
