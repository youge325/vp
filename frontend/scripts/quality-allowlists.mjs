export const AMBIENT_SOURCE_ALLOWLIST = {
  'vite-env.d.ts': {
    reason: 'Vite injects this ambient declaration before the application entrypoint is evaluated.',
    evidenceFile: 'src/vite-env.d.ts',
    marker: 'vite/client',
  },
  'types/router.d.ts': {
    reason: 'Vue Router consumes this ambient route-meta augmentation through TypeScript.',
    evidenceFile: 'src/types/router.d.ts',
    marker: "declare module 'vue-router'",
  },
}

export const GENERATED_SOURCE_ALLOWLIST = {
  'src/types/generated/contracts.ts': {
    reason: 'Generated root JSON Schema binding checked by contract freshness.',
    evidenceFile: '../contracts/boundary.schema.json',
    marker: '"VpBoundaryContracts"',
  },
}

export const KNIP_DEPENDENCY_ALLOWLIST = {
  '@wdio/cli': {
    reason: 'The E2E launcher resolves the WDIO CLI executable dynamically.',
    evidenceFile: 'scripts/run-wdio.mjs',
    marker: "'@wdio', 'cli', 'bin', 'wdio.js'",
  },
  '@wdio/local-runner': {
    reason: 'WebdriverIO loads its configured local runner by package convention.',
    evidenceFile: 'wdio.conf.ts',
    marker: "runner: 'local'",
  },
  'brace-expansion': {
    reason: 'The local compatibility package is pinned through the npm override adapter.',
    evidenceFile: 'package.json',
    marker: '"brace-expansion": "$brace-expansion"',
  },
  'json-schema-to-typescript': {
    reason: 'The root contract generator invokes the package-provided json2ts binary.',
    evidenceFile: '../scripts/generate_contracts.py',
    marker: '"json2ts"',
  },
}
