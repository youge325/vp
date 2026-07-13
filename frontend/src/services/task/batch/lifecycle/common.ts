// Shared current/console item lookup and batch runtime cleanup.

import type { MediaItem, MediaRunState } from '@/types/domain/media'

import type { BatchLifecycleDeps } from './types'

export function createCommonHelpers(deps: BatchLifecycleDeps) {
  function getCurrentItem(): MediaItem | null {
    const id = deps.getBatch().currentId
    return id ? deps.getMediaItem(id) : null
  }

  function getConsoleItem(): MediaItem | null {
    const current = getCurrentItem()
    if (current) {
      return current
    }
    const activeId = deps.getActiveItemId()
    return activeId ? deps.getMediaItem(activeId) : null
  }

  function getCurrentRunState(): MediaRunState | null {
    const id = deps.getBatch().currentId
    return id ? deps.getItemRunState(id) : null
  }

  function getConsoleRunState(): MediaRunState | null {
    const currentId = deps.getBatch().currentId
    if (currentId) {
      return deps.getItemRunState(currentId)
    }
    const activeId = deps.getActiveItemId()
    return activeId ? deps.getItemRunState(activeId) : null
  }

  function clearBatchRuntimeArtifacts(preserveLogs = false): void {
    deps.resetItemsRunState(new Set(deps.getRuntimeIds()), preserveLogs)
  }

  return {
    getCurrentItem,
    getConsoleItem,
    getCurrentRunState,
    getConsoleRunState,
    clearBatchRuntimeArtifacts,
  }
}
