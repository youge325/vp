// Pure: no Vue / no Pinia / no Tauri.
// Batch state-machine composition root. Queue and finalization reference each
// other lazily; only the public BatchRunner operations leave this module.

import {
  resolveConsoleTaskContext,
  resolveTaskContext,
} from './task-context'
import { createControlOps } from './batch/lifecycle/control'
import { createFinalizeOps } from './batch/lifecycle/finalize'
import { createQueueOps } from './batch/lifecycle/queue'
import type { BatchRunner, BatchRunnerDeps } from './batch/lifecycle/types'
import { createConflictResolver } from './batch/conflict'
import { createEventHandlers } from './batch/events'

export function createBatchRunner(deps: BatchRunnerDeps): BatchRunner {
  const lookup = {
    getMediaItem: deps.getMediaItem,
    getItemRunState: deps.getItemRunState,
  }
  const currentContext = {
    getCurrentTaskContext: () => resolveTaskContext(lookup, deps.getBatch().currentId),
  }
  const consoleContext = {
    getConsoleTaskContext: () => resolveConsoleTaskContext(
      lookup,
      deps.getBatch().currentId,
      deps.getActiveItemId(),
    ),
  }
  const finalizeOps = createFinalizeOps(deps, currentContext, {
    runNextQueuedItem: () => queueOps.runNextQueuedItem(),
  })
  const queueOps = createQueueOps(deps, {
    handleErrored: (error) => finalizeOps.handleErrored(error),
  })
  const controlOps = createControlOps(deps)
  const lifecycle = {
    ...currentContext,
    ...consoleContext,
    launchCurrentItem: queueOps.launchCurrentItem,
    finalizeCurrent: finalizeOps.finalizeCurrent,
    handleErrored: finalizeOps.handleErrored,
  }
  const conflict = createConflictResolver(deps, lifecycle)
  const events = createEventHandlers(deps, lifecycle, conflict)

  return {
    start: queueOps.start,
    pause: controlOps.pause,
    resume: controlOps.resume,
    cancel: controlOps.cancel,
    resolveConflict: conflict.resolveConflict,
    onProgress: events.onProgress,
    onLog: events.onLog,
    onCompleted: events.onCompleted,
    onError: events.onError,
    onCancelled: events.onCancelled,
    onResumeStatus: events.onResumeStatus,
  }
}

export type { BatchRunner } from './batch/lifecycle/types'
