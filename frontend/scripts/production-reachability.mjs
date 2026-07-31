export function collectReachableModules(dependencyGraph, roots) {
  const reachable = new Set()

  function visit(modulePath) {
    if (reachable.has(modulePath)) {
      return
    }
    reachable.add(modulePath)
    for (const dependency of dependencyGraph.get(modulePath) ?? []) {
      visit(dependency)
    }
  }

  for (const root of roots) {
    visit(root)
  }
  return reachable
}

export function collectUnreachableModules(
  dependencyGraph,
  roots,
  allowlist = new Set(),
) {
  const reachable = collectReachableModules(dependencyGraph, roots)
  return [...dependencyGraph.keys()]
    .filter((modulePath) => !reachable.has(modulePath) && !allowlist.has(modulePath))
    .sort()
}
