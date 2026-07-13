// Pause, resume and cancel IPC operations with state rollback on failure.

import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol'

import { applyTaskCancelling, applyTaskPaused, applyTaskResumed } from '../../events'

import type { createCommonHelpers } from './common'
import type { BatchLifecycleDeps } from './types'

type CommonHelpers = ReturnType<typeof createCommonHelpers>

export function createControlOps(
  deps: BatchLifecycleDeps,
  helpers: CommonHelpers,
) {
  async function setPaused(paused: boolean): Promise<void> {
    const batch = deps.getBatch()
    if (!batch.isRunning || batch.isPaused === paused || batch.isCancelling) {
      return
    }

    try {
      await (paused ? deps.pauseTask() : deps.resumeTask())
      deps.setBatch({ isPaused: paused })
      const item = helpers.getCurrentItem()
      const runState = helpers.getCurrentRunState()
      if (item && runState) {
        const nextState = paused
          ? applyTaskPaused(runState.taskState)
          : applyTaskResumed(runState.taskState)
        deps.setItemTaskState(item.id, nextState)
      }
    } catch (error) {
      throw normalizeError(error, TASK_ERROR_CODES.ProcessFailed)
    }
  }

  async function pause(): Promise<void> {
    await setPaused(true)
  }

  async function resume(): Promise<void> {
    await setPaused(false)
  }

  async function cancel(): Promise<void> {
    const batch = deps.getBatch()
    if (!batch.isRunning || batch.isCancelling) {
      return
    }

    deps.setPendingConflict(null)

    const previousQueue = [...batch.queue]
    const wasPaused = batch.isPaused
    const item = helpers.getCurrentItem()
    const previousTaskState = helpers.getCurrentRunState()?.taskState ?? null

    deps.setBatch({
      queue: [],
      isPaused: false,
      isCancelling: true,
    })
    if (item && previousTaskState) {
      deps.setItemTaskState(item.id, applyTaskCancelling(previousTaskState))
    }

    try {
      await deps.cancelTask()
    } catch (error) {
      deps.setBatch({
        queue: previousQueue,
        isPaused: wasPaused,
        isCancelling: false,
      })
      if (item && previousTaskState) {
        deps.setItemTaskState(item.id, previousTaskState)
      }
      throw normalizeError(error, TASK_ERROR_CODES.ProcessFailed)
    }
  }

  return { pause, resume, cancel }
}
