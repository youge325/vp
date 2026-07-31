import {
  collectReachableModules,
  collectUnreachableModules,
} from './production-reachability.mjs'

const fixture = new Map([
  ['src/main.ts', new Set(['src/live.ts'])],
  ['src/live.ts', new Set()],
  ['src/test-only-export.ts', new Set()],
  ['tests/test-reference.spec.ts', new Set(['src/test-only-export.ts'])],
])

const productionReachable = collectReachableModules(fixture, ['src/main.ts'])
if (productionReachable.has('src/test-only-export.ts')) {
  throw new Error('test-only imports must not keep production modules reachable')
}

const unreachable = collectUnreachableModules(
  fixture,
  ['src/main.ts'],
  new Set(['tests/test-reference.spec.ts']),
)
if (
  unreachable.length !== 1
  || unreachable[0] !== 'src/test-only-export.ts'
) {
  throw new Error(`unexpected reachability fixture result: ${unreachable.join(', ')}`)
}

process.stdout.write('Frontend production reachability self-test passed\n')
