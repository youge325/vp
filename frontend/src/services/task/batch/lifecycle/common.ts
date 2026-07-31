// Shared current/console task context lookup.

import {
  resolveConsoleTaskContext,
  resolveTaskContext,
} from '@/services/task/task-context'
import type {
  BatchStatePort,
  ConsoleTaskContextCapability,
  MediaItemPort,
  MediaRunStatePort,
  TaskContextCapability,
} from './types'

type CommonDeps =
  & Pick<BatchStatePort, 'getBatch'>
  & Pick<MediaItemPort, 'getMediaItem' | 'getActiveItemId'>
  & Pick<MediaRunStatePort, 'getItemRunState'>

export function createCommonHelpers(
  deps: CommonDeps,
): TaskContextCapability & ConsoleTaskContextCapability {
  function getCurrentTaskContext() {
    return resolveTaskContext(
      {
        getMediaItem: deps.getMediaItem,
        getItemRunState: deps.getItemRunState,
      },
      deps.getBatch().currentId,
    )
  }

  function getConsoleTaskContext() {
    return resolveConsoleTaskContext(
      {
        getMediaItem: deps.getMediaItem,
        getItemRunState: deps.getItemRunState,
      },
      deps.getBatch().currentId,
      deps.getActiveItemId(),
    )
  }

  return {
    getCurrentTaskContext,
    getConsoleTaskContext,
  }
}
