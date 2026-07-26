// Shared current/console task context lookup and batch runtime cleanup.

import type { BatchLifecycleDeps } from './types'

export function createCommonHelpers(deps: BatchLifecycleDeps) {
  function resolveTaskContext(id: string | null) {
    return {
      item: id ? deps.getMediaItem(id) : null,
      runState: id ? deps.getItemRunState(id) : null,
    }
  }

  function getCurrentTaskContext() {
    return resolveTaskContext(deps.getBatch().currentId)
  }

  function getConsoleTaskContext() {
    const current = getCurrentTaskContext()
    if (current.item) {
      return current
    }
    return resolveTaskContext(deps.getActiveItemId())
  }

  function clearBatchRuntimeArtifacts(preserveLogs = false): void {
    deps.resetItemsRunState(new Set(deps.getRuntimeIds()), preserveLogs)
  }

  return {
    getCurrentTaskContext,
    getConsoleTaskContext,
    clearBatchRuntimeArtifacts,
  }
}
