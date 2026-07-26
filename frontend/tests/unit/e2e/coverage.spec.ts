import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import {
  E2E_COVERAGE_DIRECTORY,
  prepareE2ECoverageDirectory,
  writeE2ESessionCoverage,
} from '../../e2e/config/coverage'

describe('E2E session coverage', () => {
  let root: string

  beforeEach(() => {
    root = mkdtempSync(resolve(tmpdir(), 'vp-e2e-coverage-'))
  })

  afterEach(() => {
    rmSync(root, { recursive: true, force: true })
  })

  it('removes stale data before an instrumented run', () => {
    const outputDir = resolve(root, E2E_COVERAGE_DIRECTORY)
    mkdirSync(outputDir)
    writeFileSync(resolve(outputDir, 'stale.json'), '{}')

    prepareE2ECoverageDirectory(root, true)

    expect(existsSync(outputDir)).toBe(true)
    expect(readdirSync(outputDir)).toEqual([])
  })

  it('does not recreate the output directory for a non-instrumented run', () => {
    prepareE2ECoverageDirectory(root, false)
    expect(existsSync(resolve(root, E2E_COVERAGE_DIRECTORY))).toBe(false)
  })

  it('writes one renderer-serialized payload for a worker session', () => {
    prepareE2ECoverageDirectory(root, true)
    const serialized = JSON.stringify({ '/src/App.vue': { s: { 0: 1 } } })

    const outputPath = writeE2ESessionCoverage(root, ['one.spec.ts', 'two.spec.ts'], serialized)

    expect(readdirSync(resolve(root, E2E_COVERAGE_DIRECTORY))).toHaveLength(1)
    expect(readFileSync(outputPath, 'utf8')).toBe(serialized)
  })

  it('rejects an instrumented session without coverage', () => {
    expect(() => writeE2ESessionCoverage(root, ['one.spec.ts'], null))
      .toThrow('E2E coverage was not available')
  })
})
