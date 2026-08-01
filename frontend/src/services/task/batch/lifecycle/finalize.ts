// Terminal accounting, cleanup and queue continuation.

import type { TaskErrorPayload } from '@/types/protocol'

import { transitionTaskStatus } from '../../events'

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
  & Pick<BatchStatePort, 'getBatch' | 'dispatchBatch'>
  & Pick<MediaRunStatePort, 'setItemTaskState'>
  & TaskIssuePort
  & OutputLocationPort

export function createFinalizeOps(
  deps: FinalizeDeps,
  helpers: TaskContextCapability,
  internal: Pick<QueueContinuation, 'runNextQueuedItem'>,
): FinalizationCapability {
  async function finalizeCurrent(
    state: Parameters<FinalizationCapability['finalizeCurrent']>[0],
  ): Promise<void> {
    const context = helpers.getCurrentTaskContext()
    const item = context.item
    if (!item) {
      const hasQueuedItems = deps.getBatch().queue.length > 0
      deps.dispatchBatch({ type: 'item-finalized' })
      if (hasQueuedItems) {
        await internal.runNextQueuedItem()
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
    }

    const hasQueuedItems = deps.getBatch().queue.length > 0
    deps.dispatchBatch({ type: 'item-finalized' })
    if (hasQueuedItems) {
      await internal.runNextQueuedItem()
    }
  }

  async function handleErrored(error: TaskErrorPayload): Promise<void> {
    const { item, runState } = helpers.getCurrentTaskContext()
    if (item && runState) {
      deps.setItemTaskState(item.id, transitionTaskStatus(runState.taskState, 'error'))
    }
    deps.setTaskIssue(error)
    await finalizeCurrent('error')
  }

  return { finalizeCurrent, handleErrored }
}
