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
  if (!pattern.includes(wildcard)) {
    return path === pattern
  }
  const [prefix, suffix] = pattern.split(wildcard)
  return path.startsWith(`${prefix}/`) && path.endsWith(suffix.replace('*', ''))
}

describe('E2E spec grouping', () => {
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
