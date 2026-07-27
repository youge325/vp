// Shared current/console task context lookup and batch runtime cleanup.

import {
  resolveConsoleTaskContext,
  resolveTaskContext,
} from '@/services/task/task-context'
import type { BatchLifecycleDeps } from './types'

export function createCommonHelpers(deps: BatchLifecycleDeps) {
  function getCurrentTaskContext() {
    return resolveTaskContext(deps, deps.getBatch().currentId)
  }

  function getConsoleTaskContext() {
    return resolveConsoleTaskContext(
      deps,
      deps.getBatch().currentId,
      deps.getActiveItemId(),
    )
  }

  function clearBatchRuntimeArtifacts(): void {
    deps.resetItemsRunState(new Set(deps.getRuntimeIds()))
  }

  return {
    getCurrentTaskContext,
    getConsoleTaskContext,
    clearBatchRuntimeArtifacts,
  }
}
