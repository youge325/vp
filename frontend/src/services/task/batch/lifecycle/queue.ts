// Queue initialization, resume inspection and task launch.

import type { MediaItem } from '@/types/domain/media'
import { normalizeError } from '@/lib/errors/normalize'
import {
  TASK_ERROR_CODES,
  type ResumeInspectionResult,
  type ResumeMode,
} from '@/types/protocol'

import { createIdleTaskState, transitionTaskStatus } from '../../events'
import { buildResumeConflictDescriptor } from '../../resume-classifier'

import type {
  BatchStatePort,
  ErrorFinalizationCapability,
  MediaItemPort,
  MediaRunStatePort,
  QueueOperations,
  TaskCommandPort,
  TaskRequestFactory,
} from './types'

type QueueDeps =
  & Pick<BatchStatePort, 'getBatch' | 'dispatchBatch' | 'setRuntimeIds' | 'setPendingConflict'>
  & Pick<MediaItemPort, 'getMediaItem' | 'setActiveItem'>
  & Pick<MediaRunStatePort, 'setItemTaskState' | 'resetItemRunState'>
  & Pick<TaskCommandPort, 'startTask' | 'checkResume'>
  & TaskRequestFactory

export function createQueueOps(
  deps: QueueDeps,
  internal: ErrorFinalizationCapability,
): QueueOperations {
  function resetBatchRunState(ids: string[]): void {
    deps.setRuntimeIds([...ids])
    deps.dispatchBatch({ type: 'started', ids })

    for (const id of ids) {
      deps.resetItemRunState(id)
    }
  }

  async function runNextQueuedItem(): Promise<void> {
    const queue = [...deps.getBatch().queue]
    const nextId = queue.shift() ?? null

    if (!nextId) {
      deps.dispatchBatch({ type: 'item-finalized' })
      return
    }

    deps.dispatchBatch({ type: 'queue-advanced', currentId: nextId, remaining: queue })

    const item = deps.getMediaItem(nextId)
    if (!item) {
      await runNextQueuedItem()
      return
    }

    deps.setActiveItem(nextId)
    deps.setItemTaskState(nextId, transitionTaskStatus(createIdleTaskState(), 'running'))

    let inspection: ResumeInspectionResult | null = null
    try {
      inspection = await deps.checkResume(deps.buildRequest(item))
    } catch (error) {
      await internal.handleErrored(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
      return
    }

    const conflict = buildResumeConflictDescriptor(inspection)
    if (conflict) {
      deps.setPendingConflict(conflict)
      return
    }

    await launchCurrentItem(item)
  }

  async function launchCurrentItem(item: MediaItem, resumeMode?: ResumeMode): Promise<void> {
    try {
      await deps.startTask(deps.buildRequest(item, resumeMode))
    } catch (error) {
      await internal.handleErrored(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    }
  }

  async function start(ids: string[]): Promise<void> {
    if (ids.length === 0 || deps.getBatch().phase !== 'idle') {
      return
    }
    resetBatchRunState(ids)
    await runNextQueuedItem()
  }

  return { start, runNextQueuedItem, launchCurrentItem }
}
