// Pause, resume and cancel IPC operations with state rollback on failure.

import { normalizeError } from '@/lib/errors/normalize'
import {
  TASK_ERROR_CODES,
  type TaskControlKind,
} from '@/types/protocol'
import type { BatchState } from '@/types/domain/batch'

import type {
  BatchStatePort,
  ControlOperations,
  TaskCommandPort,
  TaskIssuePort,
} from './types'

type ControlDeps =
  & Pick<BatchStatePort, 'getBatch' | 'dispatchBatch' | 'setPendingConflict'>
  & Pick<TaskCommandPort, 'cancelTask' | 'pauseTask' | 'resumeTask'>
  & TaskIssuePort

interface ControlAttempt {
  kind: TaskControlKind
  taskId: string | null
  token: number
  snapshot: BatchState
}

export function createControlOps(deps: ControlDeps): ControlOperations {
  let nextControlToken = 0
  let activeControlToken: number | null = null

  function beginControl(kind: TaskControlKind): ControlAttempt | null {
    const batch = deps.getBatch()
    if (batch.controlPending !== null) {
      return null
    }

    const attempt = {
      kind,
      taskId: batch.currentId,
      token: ++nextControlToken,
      snapshot: {
        ...batch,
        queue: [...batch.queue],
      },
    }
    deps.dispatchBatch({ type: 'control-requested', kind })
    if (deps.getBatch().controlPending !== kind) {
      return null
    }
    activeControlToken = attempt.token
    return attempt
  }

  function isCurrentAttempt(attempt: ControlAttempt): boolean {
    const batch = deps.getBatch()
    return activeControlToken === attempt.token
      && batch.currentId === attempt.taskId
      && batch.controlPending === attempt.kind
  }

  function completeAttempt(attempt: ControlAttempt): boolean {
    if (!isCurrentAttempt(attempt)) {
      if (activeControlToken === attempt.token) {
        activeControlToken = null
      }
      return false
    }

    activeControlToken = null
    deps.dispatchBatch({ type: 'control-succeeded', kind: attempt.kind })
    return true
  }

  function reportControlFailure(
    attempt: ControlAttempt,
    error: unknown,
  ): boolean {
    if (!isCurrentAttempt(attempt)) {
      if (activeControlToken === attempt.token) {
        activeControlToken = null
      }
      return false
    }
    activeControlToken = null
    deps.dispatchBatch({
      type: 'control-failed',
      kind: attempt.kind,
      snapshot: attempt.snapshot,
    })
    deps.setTaskIssue(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    return true
  }

  async function setPaused(paused: boolean): Promise<void> {
    const batch = deps.getBatch()
    if ((batch.phase === 'paused') === paused) {
      return
    }
    const attempt = beginControl(paused ? 'pause' : 'resume')
    if (!attempt) {
      return
    }

    try {
      await (paused ? deps.pauseTask() : deps.resumeTask())
      if (!completeAttempt(attempt)) {
        return
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
    const attempt = beginControl('cancel')
    if (!attempt) {
      return
    }

    deps.setPendingConflict(null)

    try {
      await deps.cancelTask()
      if (completeAttempt(attempt)) {
        deps.setTaskIssue(null)
      }
    } catch (error) {
      reportControlFailure(attempt, error)
    }
  }

  return { pause, resume, cancel }
}
