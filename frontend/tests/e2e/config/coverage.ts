import { createHash } from 'node:crypto'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const E2E_COVERAGE_DIRECTORY = '.nyc_output'

export function prepareE2ECoverageDirectory(cwd: string, enabled: boolean): void {
  const outputDir = resolve(cwd, E2E_COVERAGE_DIRECTORY)
  rmSync(outputDir, { recursive: true, force: true })
  if (enabled) {
    mkdirSync(outputDir, { recursive: true })
  }
}

export function writeE2ESessionCoverage(
  cwd: string,
  specs: string[],
  serializedCoverage: string | null,
): string {
  if (!serializedCoverage || serializedCoverage === 'null') {
    throw new Error(`E2E coverage was not available for session: ${specs.join(', ')}`)
  }

  const outputDir = resolve(cwd, E2E_COVERAGE_DIRECTORY)
  mkdirSync(outputDir, { recursive: true })
  const groupId = createHash('sha256').update(specs.join('\n')).digest('hex').slice(0, 12)
  const outputPath = resolve(outputDir, `session-${groupId}-${process.pid}-${Date.now()}.json`)
  writeFileSync(outputPath, serializedCoverage)
  return outputPath
}
