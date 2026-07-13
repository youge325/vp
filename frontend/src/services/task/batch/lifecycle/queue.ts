// Queue initialization, resume inspection and task launch.

import type { MediaItem } from '@/types/domain/media'
import { normalizeError } from '@/services/error/normalize'
import {
  TASK_ERROR_CODES,
  type ResumeInspectionResult,
  type ResumeMode,
} from '@/types/protocol'

import { createIdleTaskState } from '../../events'
import { buildResumeConflictDescriptor } from '../../resume-classifier'

import type { BatchLifecycleDeps } from './types'

interface QueueInternalRefs {
  handleErrored: (error: ReturnType<typeof normalizeError>) => Promise<void>
}

export function createQueueOps(
  deps: BatchLifecycleDeps,
  internal: QueueInternalRefs,
) {
  function resetBatchRunState(ids: string[]): void {
    deps.setRuntimeIds([...ids])
    deps.setBatch({
      queue: [...ids],
      currentId: null,
      completedCount: 0,
      failedCount: 0,
      isRunning: ids.length > 0,
      isPaused: false,
      isCancelling: false,
    })

    for (const id of ids) {
      deps.resetItemRunState(id)
    }
  }

  async function runNextQueuedItem(): Promise<void> {
    const queue = [...deps.getBatch().queue]
    const nextId = queue.shift() ?? null
    deps.setBatch({ queue })

    if (!nextId) {
      deps.setBatch({
        currentId: null,
        isRunning: false,
        isPaused: false,
        isCancelling: false,
      })
      return
    }

    const item = deps.getMediaItem(nextId)
    if (!item) {
      deps.setBatch({ currentId: null })
      await runNextQueuedItem()
      return
    }

    deps.setBatch({
      currentId: nextId,
      isPaused: false,
      isCancelling: false,
    })
    deps.setActiveItem(nextId)
    deps.setItemTaskState(nextId, {
      ...createIdleTaskState(),
      status: 'running',
    })

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
    if (ids.length === 0 || deps.getBatch().isRunning) {
      return
    }
    resetBatchRunState(ids)
    await runNextQueuedItem()
  }

  return { start, runNextQueuedItem, launchCurrentItem }
}
