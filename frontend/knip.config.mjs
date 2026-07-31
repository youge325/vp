import {
  GENERATED_SOURCE_ALLOWLIST,
  KNIP_DEPENDENCY_ALLOWLIST,
} from './scripts/quality-allowlists.mjs'

export default {
  entry: [
    'scripts/*.mjs',
    'knip*.config.mjs',
    'tests/unit/**/*.spec.ts',
    'tests/e2e/**/*.spec.ts',
  ],
  project: [
    'src/**/*.{ts,tsx,vue}',
    'scripts/**/*.{ts,mjs}',
    'tests/**/*.ts',
    '*.{ts,mjs}',
  ],
  ignore: Object.keys(GENERATED_SOURCE_ALLOWLIST),
  ignoreDependencies: Object.keys(KNIP_DEPENDENCY_ALLOWLIST),
  ignoreBinaries: ['rustc', 'tauri-driver'],
}
