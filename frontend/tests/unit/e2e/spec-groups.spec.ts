import { readdirSync } from 'node:fs'
import { relative, resolve } from 'node:path'
import {
  E2E_ALL_SPECS_PATTERN,
  E2E_SPEC_GROUPS,
  resolveE2ESpecs,
  splitSpecPatterns,
} from '../../e2e/config/spec-groups'

const e2eRoot = resolve(process.cwd(), 'tests', 'e2e')

const listSpecFiles = (directory: string): string[] => readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => {
    const path = resolve(directory, entry.name)
    return entry.isDirectory() ? listSpecFiles(path) : [path]
  })
  .filter((path) => path.endsWith('.spec.ts'))
  .map((path) => `./tests/e2e/${relative(e2eRoot, path).replaceAll('\\', '/')}`)

const matchesPattern = (path: string, pattern: string) => {
  const wildcard = '/**/'
  const segments = pattern.split(wildcard)
  const unsupported = () => new Error(`unsupported E2E spec pattern: ${pattern}`)
  if (segments.length === 1) {
    if (pattern.includes('*')) {
      throw unsupported()
    }
    return path === pattern
  }
  if (segments.length !== 2) {
    throw unsupported()
  }
  const [prefix, wildcardSuffix] = segments
  if (
    !prefix
    || prefix.includes('*')
    || !wildcardSuffix.startsWith('*')
    || wildcardSuffix.slice(1).includes('*')
  ) {
    throw unsupported()
  }
  return path.startsWith(`${prefix}/`) && path.endsWith(wildcardSuffix.slice(1))
}

describe('E2E spec grouping', () => {
  it('matches only the supported exact and recursive spec pattern grammar', () => {
    expect(matchesPattern(
      './tests/e2e/app/smoke.spec.ts',
      './tests/e2e/app/smoke.spec.ts',
    )).toBe(true)
    expect(matchesPattern(
      './tests/e2e/home/nested/content.spec.ts',
      './tests/e2e/home/**/*.spec.ts',
    )).toBe(true)
    expect(matchesPattern(
      './tests/e2e/home/nested/content.ts',
      './tests/e2e/home/**/*.spec.ts',
    )).toBe(false)
    expect(() => matchesPattern(
      './tests/e2e/home/content.spec.ts',
      './tests/e2e/home/**/*.*.ts',
    )).toThrow('unsupported E2E spec pattern')
    expect(() => matchesPattern(
      './tests/e2e/home/nested/content.spec.ts',
      './tests/e2e/**/nested/**/*.spec.ts',
    )).toThrow('unsupported E2E spec pattern')
  })

  it('covers every native spec exactly once in no more than ten sessions', () => {
    const specFiles = listSpecFiles(e2eRoot)
    expect(E2E_SPEC_GROUPS.length).toBeLessThanOrEqual(10)
    for (const specFile of specFiles) {
      const matchingGroups = E2E_SPEC_GROUPS.filter((group) =>
        group.some((pattern) => matchesPattern(specFile, pattern)),
      )
      expect(matchingGroups, specFile).toHaveLength(1)
    }
  })

  it('keeps cold startup isolated from reusable sessions', () => {
    expect(E2E_SPEC_GROUPS[0]).toEqual(['./tests/e2e/app/startup-timing.spec.ts'])
  })

  it('runs environment-selected specs in one session', () => {
    const selected = ['./tests/e2e/app/*.spec.ts', './tests/e2e/env/*.spec.ts']
    expect(resolveE2ESpecs({ selectedPatterns: selected })).toEqual([selected])
  })

  it('keeps watch and CLI --spec modes ungrouped', () => {
    expect(resolveE2ESpecs({ watchMode: true })).toEqual([E2E_ALL_SPECS_PATTERN])
    expect(resolveE2ESpecs({ selectedPatterns: ['one.spec.ts'], cliSpecMode: true }))
      .toEqual(['one.spec.ts'])
  })

  it('normalizes environment pattern lists', () => {
    expect(splitSpecPatterns(' one.spec.ts,\ntwo.spec.ts; three.spec.ts ')).toEqual([
      'one.spec.ts',
      'two.spec.ts',
      'three.spec.ts',
    ])
    expect(splitSpecPatterns('  ')).toBeUndefined()
  })
})
