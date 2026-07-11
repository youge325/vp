// Shared bootstrap for Vitest specs.
//
// Phase D.4.9 — vitest config points ``setupFiles`` here so future
// mocks (``@tauri-apps/api``, ResizeObserver, structuredClone polyfill,
// Pinia test instance) live in one place instead of being copy-pasted
// across spec files. Currently empty — add mocks here as the suite grows.
export {}
