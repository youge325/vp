import { GENERATED_SOURCE_ALLOWLIST } from './scripts/quality-allowlists.mjs'

export default {
  entry: ['src/main.ts'],
  project: ['src/**/*.{ts,tsx,vue}'],
  ignore: Object.keys(GENERATED_SOURCE_ALLOWLIST),
}
