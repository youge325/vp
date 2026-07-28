import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, extname, relative, resolve } from 'node:path'
import process from 'node:process'

const sourceRoot = resolve(process.cwd(), 'src')
const sourceExtensions = new Set(['.ts', '.tsx', '.vue'])
const importPattern = /\b(?:from\s+|import\s*\(\s*)['"]([^'"]+)['"]/g

function walk(directory) {
  return readdirSync(directory)
    .flatMap((name) => {
      const path = resolve(directory, name)
      return statSync(path).isDirectory() ? walk(path) : [path]
    })
    .filter((path) => sourceExtensions.has(path.slice(path.lastIndexOf('.'))))
}

const sourceFiles = walk(sourceRoot)
const modulePaths = new Map()

for (const path of sourceFiles) {
  const owner = relative(sourceRoot, path).replaceAll('\\', '/')
  const withoutExtension = owner.slice(0, -extname(owner).length)
  const candidates = [owner, withoutExtension]
  if (withoutExtension.endsWith('/index')) {
    candidates.push(withoutExtension.slice(0, -'/index'.length))
  }
  for (const candidate of candidates) {
    modulePaths.set(candidate, owner)
  }
}

function resolveInternalImport(ownerPath, dependency) {
  let candidate
  if (dependency.startsWith('@/')) {
    candidate = dependency.slice(2)
  } else if (dependency.startsWith('.')) {
    const absolute = resolve(dirname(ownerPath), dependency)
    candidate = relative(sourceRoot, absolute).replaceAll('\\', '/')
  } else {
    return null
  }

  for (const path of [
    candidate,
    `${candidate}.ts`,
    `${candidate}.tsx`,
    `${candidate}.vue`,
    `${candidate}/index.ts`,
    `${candidate}/index.tsx`,
  ]) {
    const resolved = modulePaths.get(path)
    if (resolved) {
      return resolved
    }
  }
  return null
}

const violations = []
const dependencyGraph = new Map()
for (const path of sourceFiles) {
  const owner = relative(sourceRoot, path).replaceAll('\\', '/')
  const source = readFileSync(path, 'utf8')
  const imports = [...source.matchAll(importPattern)].map((match) => match[1])
  const internalDependencies = imports
    .map((dependency) => resolveInternalImport(path, dependency))
    .filter((dependency) => dependency !== null)
  dependencyGraph.set(owner, new Set(internalDependencies))

}

const states = new Map()
const stack = []
const cycles = new Set()

function visit(modulePath) {
  states.set(modulePath, 'visiting')
  stack.push(modulePath)
  for (const dependency of dependencyGraph.get(modulePath) ?? []) {
    if (!states.has(dependency)) {
      visit(dependency)
      continue
    }
    if (states.get(dependency) !== 'visiting') {
      continue
    }
    const members = stack.slice(stack.indexOf(dependency))
    const rotations = members.map((_, index) => [...members.slice(index), ...members.slice(0, index)])
    rotations.sort((left, right) => left.join('\0').localeCompare(right.join('\0')))
    const canonical = rotations[0]
    cycles.add([...canonical, canonical[0]].join(' -> '))
  }
  stack.pop()
  states.set(modulePath, 'visited')
}

for (const modulePath of dependencyGraph.keys()) {
  if (!states.has(modulePath)) {
    visit(modulePath)
  }
}
for (const cycle of [...cycles].sort()) {
  violations.push(`frontend dependency cycle: ${cycle}`)
}

if (violations.length > 0) {
  process.stderr.write(`${violations.join('\n')}\n`)
  process.exitCode = 1
} else {
  process.stdout.write('Frontend dependency graph is acyclic\n')
}
