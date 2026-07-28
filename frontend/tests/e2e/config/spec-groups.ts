export const E2E_ALL_SPECS_PATTERN = './tests/e2e/**/*.spec.ts'

const TASK_UI_SPECS = [
  './tests/e2e/task/render-ui.spec.ts',
  './tests/e2e/task/resume-dialog.spec.ts',
] as const

const TASK_RUNTIME_SPECS = [
  './tests/e2e/task/runtime.spec.ts',
] as const

export const E2E_SPEC_GROUPS = [
  ['./tests/e2e/app/startup-timing.spec.ts'],
  [
    './tests/e2e/app/navigation.spec.ts',
    './tests/e2e/app/security.spec.ts',
    './tests/e2e/app/smoke.spec.ts',
    './tests/e2e/app/validation.spec.ts',
    './tests/e2e/home/**/*.spec.ts',
    './tests/e2e/input/**/*.spec.ts',
    './tests/e2e/preset/**/*.spec.ts',
  ],
  ['./tests/e2e/env/**/*.spec.ts'],
  ['./tests/e2e/decode/**/*.spec.ts'],
  ['./tests/e2e/encode/**/*.spec.ts'],
  ['./tests/e2e/enhance/**/*.spec.ts'],
  ['./tests/e2e/filter/**/*.spec.ts'],
  [...TASK_UI_SPECS],
  [...TASK_RUNTIME_SPECS],
] as const satisfies readonly (readonly string[])[]

export function splitSpecPatterns(value: string | undefined): string[] | undefined {
  const patterns = value
    ?.split(/[\n,;]/)
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)
  return patterns && patterns.length > 0 ? patterns : undefined
}

interface ResolveE2ESpecsOptions {
  selectedPatterns?: string[]
  watchMode?: boolean
  cliSpecMode?: boolean
}

export function resolveE2ESpecs({
  selectedPatterns,
  watchMode = false,
  cliSpecMode = false,
}: ResolveE2ESpecsOptions = {}): (string | string[])[] {
  if (watchMode || cliSpecMode) {
    return selectedPatterns ? [...selectedPatterns] : [E2E_ALL_SPECS_PATTERN]
  }
  if (selectedPatterns) {
    return [[...selectedPatterns]]
  }
  return E2E_SPEC_GROUPS.map((group) => [...group])
}
