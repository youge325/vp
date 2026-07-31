// Terminal accounting, cleanup and queue continuation.

import type { TaskErrorPayload } from '@/types/protocol'

import { applyTaskError } from '../../events'

import type {
  BatchStatePort,
  FinalizationCapability,
  MediaRunStatePort,
  OutputLocationPort,
  QueueContinuation,
  TaskContextCapability,
  TaskIssuePort,
} from './types'

type FinalizeDeps =
  & Pick<BatchStatePort, 'getBatch' | 'setBatch'>
  & Pick<MediaRunStatePort, 'setItemTaskState'>
  & TaskIssuePort
  & OutputLocationPort

export function createFinalizeOps(
  deps: FinalizeDeps,
  helpers: TaskContextCapability,
  internal: Pick<QueueContinuation, 'runNextQueuedItem'>,
): FinalizationCapability {
  function finishBatchRun(): void {
    deps.setBatch({
      isRunning: false,
      isPaused: false,
      isCancelling: false,
      controlPending: null,
    })
  }

  async function finalizeCurrent(
    state: Parameters<FinalizationCapability['finalizeCurrent']>[0],
  ): Promise<void> {
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
      }
    }

    deps.setBatch({ currentId: null })
    if (deps.getBatch().queue.length > 0) {
      deps.setBatch({
        isPaused: false,
        isCancelling: false,
        controlPending: null,
      })
      await internal.runNextQueuedItem()
      return
    }

    finishBatchRun()
  }

  async function handleErrored(error: TaskErrorPayload): Promise<void> {
    const { item, runState } = helpers.getCurrentTaskContext()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskError(runState.taskState))
    }
    deps.setTaskIssue(error)
    await finalizeCurrent('error')
  }

  return { finalizeCurrent, handleErrored }
}
