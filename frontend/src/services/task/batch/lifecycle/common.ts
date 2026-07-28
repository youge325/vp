// Shared current/console task context lookup.

import {
  resolveConsoleTaskContext,
  resolveTaskContext,
} from '@/services/task/task-context'
import type {
  BatchStatePort,
  MediaItemPort,
  MediaRunStatePort,
} from './types'

type CommonDeps =
  & Pick<BatchStatePort, 'getBatch'>
  & Pick<MediaItemPort, 'getMediaItem' | 'getActiveItemId'>
  & Pick<MediaRunStatePort, 'getItemRunState'>

export function createCommonHelpers(deps: CommonDeps) {
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

  return {
    getCurrentTaskContext,
    getConsoleTaskContext,
  }
}
