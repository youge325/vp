// Pause, resume and cancel IPC operations with state rollback on failure.

import { normalizeError } from '@/lib/errors/normalize'
import {
  TASK_ERROR_CODES,
  type TaskControlKind,
} from '@/types/protocol'
import type { BatchState } from '@/types/domain/batch'

import { applyTaskCancelling, applyTaskPaused, applyTaskResumed } from '../../events'

import type {
  BatchStatePort,
  ControlOperations,
  MediaRunStatePort,
  TaskContextCapability,
  TaskCommandPort,
  TaskIssuePort,
} from './types'

type ControlDeps =
  & Pick<BatchStatePort, 'getBatch' | 'setBatch' | 'setPendingConflict'>
  & Pick<MediaRunStatePort, 'setItemTaskState'>
  & Pick<TaskCommandPort, 'cancelTask' | 'pauseTask' | 'resumeTask'>
  & TaskIssuePort

interface ControlAttempt {
  kind: TaskControlKind
  taskId: string | null
  token: number
}

export function createControlOps(
  deps: ControlDeps,
  helpers: TaskContextCapability,
): ControlOperations {
  let nextControlToken = 0
  let activeControlToken: number | null = null

  function beginControl(kind: TaskControlKind): ControlAttempt | null {
    const batch = deps.getBatch()
    if (!batch.isRunning || batch.isCancelling || batch.controlPending !== null) {
      return null
    }

    const attempt = {
      kind,
      taskId: batch.currentId,
      token: ++nextControlToken,
    }
    activeControlToken = attempt.token
    deps.setBatch({ controlPending: kind })
    return attempt
  }

  function isCurrentAttempt(attempt: ControlAttempt): boolean {
    const batch = deps.getBatch()
    return activeControlToken === attempt.token
      && batch.isRunning
      && batch.currentId === attempt.taskId
      && batch.controlPending === attempt.kind
  }

  function completeAttempt(
    attempt: ControlAttempt,
    update: Partial<BatchState>,
  ): boolean {
    if (!isCurrentAttempt(attempt)) {
      if (activeControlToken === attempt.token) {
        activeControlToken = null
      }
      return false
    }

    activeControlToken = null
    deps.setBatch({ ...update, controlPending: null })
    return true
  }

  function reportControlFailure(
    attempt: ControlAttempt,
    error: unknown,
    rollback: Partial<BatchState> = {},
  ): boolean {
    if (!completeAttempt(attempt, rollback)) {
      return false
    }
    deps.setTaskIssue(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    return true
  }

  async function setPaused(paused: boolean): Promise<void> {
    const batch = deps.getBatch()
    if (batch.isPaused === paused) {
      return
    }
    const attempt = beginControl(paused ? 'pause' : 'resume')
    if (!attempt) {
      return
    }

    try {
      await (paused ? deps.pauseTask() : deps.resumeTask())
      if (!completeAttempt(attempt, { isPaused: paused })) {
        return
      }
      const { item, runState } = helpers.getCurrentTaskContext()
      if (item && runState) {
        const nextState = paused
          ? applyTaskPaused(runState.taskState)
          : applyTaskResumed(runState.taskState)
        deps.setItemTaskState(item.id, nextState)
      }
      deps.setTaskIssue(null)
    } catch (error) {
      reportControlFailure(attempt, error)
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
    const attempt = beginControl('cancel')
    if (!attempt) {
      return
    }

    deps.setPendingConflict(null)

    const previousQueue = [...batch.queue]
    const wasPaused = batch.isPaused
    const { item, runState } = helpers.getCurrentTaskContext()
    const previousTaskState = runState?.taskState ?? null

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
      if (completeAttempt(attempt, {})) {
        deps.setTaskIssue(null)
      }
    } catch (error) {
      const restored = reportControlFailure(attempt, error, {
        queue: previousQueue,
        isPaused: wasPaused,
        isCancelling: false,
      })
      if (restored && item && previousTaskState) {
        deps.setItemTaskState(item.id, previousTaskState)
      }
    }
  }

  return { pause, resume, cancel }
}
