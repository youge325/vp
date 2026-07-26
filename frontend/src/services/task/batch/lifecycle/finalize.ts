// Terminal accounting, cleanup and queue continuation.

import type { TaskError } from '@/types/domain/media'

import { applyTaskError } from '../../events'

import type { createCommonHelpers } from './common'
import type { BatchLifecycleDeps } from './types'

type CommonHelpers = ReturnType<typeof createCommonHelpers>

interface FinalizeInternalRefs {
  runNextQueuedItem: () => Promise<void>
}

export function createFinalizeOps(
  deps: BatchLifecycleDeps,
  helpers: CommonHelpers,
  internal: FinalizeInternalRefs,
) {
  function finishBatchRun(): void {
    deps.setBatch({
      isRunning: false,
      isPaused: false,
      isCancelling: false,
    })
    helpers.clearBatchRuntimeArtifacts(true)
    deps.setBatch({ completedCount: 0, failedCount: 0 })
    deps.setRuntimeIds([])
  }

  async function finalizeCurrent(state: 'completed' | 'error' | 'cancelled'): Promise<void> {
    const context = helpers.getCurrentTaskContext()
    const item = context.item
    if (!item) {
      const queue = deps.getBatch().queue
      deps.setBatch({ currentId: null })
      if (queue.length > 0) {
        await internal.runNextQueuedItem()
      } else {
        finishBatchRun()
      }
      return
    }

    if (state === 'completed' || state === 'cancelled') {
      const lastOutputPath = context.runState?.lastOutputPath ?? ''
      if (item.outputConfig.openOnComplete && lastOutputPath) {
        try {
          await deps.openOutputLocation(lastOutputPath)
        } catch {
          // Ignore shell-open failures after processing finished.
        }
      }
      const batch = deps.getBatch()
      if (state === 'completed') {
        deps.setBatch({ completedCount: batch.completedCount + 1 })
      } else {
        deps.setBatch({ failedCount: batch.failedCount + 1 })
      }
    } else {
      const batch = deps.getBatch()
      deps.setBatch({ failedCount: batch.failedCount + 1 })
    }

    deps.setBatch({ currentId: null })
    if (deps.getBatch().queue.length > 0) {
      deps.setBatch({ isPaused: false, isCancelling: false })
      await internal.runNextQueuedItem()
      return
    }

    finishBatchRun()
  }

  async function handleErrored(error: TaskError): Promise<void> {
    const { item, runState } = helpers.getCurrentTaskContext()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskError(runState.taskState))
    }
    deps.setTaskIssue(error)
    await finalizeCurrent('error')
  }

  return { finalizeCurrent, handleErrored }
}
