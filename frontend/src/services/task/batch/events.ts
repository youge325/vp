// NDJSON event adapter. It updates the current/console item and delegates
// terminal transitions through a narrow lifecycle capability.

import { TASK_ERROR_CODES } from '@/types/protocol'
import type { MediaTaskState, TaskError } from '@/types/domain/media'
import type {
  ResumeStatusPayload,
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/protocol'
import {
  appendTaskLog,
  applyTaskCancelled,
  applyTaskCompleted,
  applyTaskProgress,
  applyTaskResumeStatus,
} from '../events'
import type { createConflictResolver } from './conflict'
import type { createCommonHelpers } from './lifecycle/common'
import type { createFinalizeOps } from './lifecycle/finalize'
import type { BatchLifecycleDeps } from './lifecycle/types'

type EventHandlersDeps = Pick<
  BatchLifecycleDeps,
  'setItemTaskState' | 'setItemLastOutputPath' | 'setTaskIssue'
>
type EventLifecycle = Pick<
  ReturnType<typeof createCommonHelpers>,
  'getConsoleTaskContext' | 'getCurrentTaskContext'
> &
  Pick<ReturnType<typeof createFinalizeOps>, 'finalizeCurrent' | 'handleErrored'>

export function createEventHandlers(
  deps: EventHandlersDeps,
  lifecycle: EventLifecycle,
  conflict: ReturnType<typeof createConflictResolver>,
) {
  function updateConsoleTaskState(
    update: (state: MediaTaskState) => MediaTaskState,
  ): void {
    const { item, runState } = lifecycle.getConsoleTaskContext()
    if (item && runState) {
      deps.setItemTaskState(item.id, update(runState.taskState))
    }
  }

  function onProgress(_payload: TaskProgressPayload): void {
    updateConsoleTaskState(applyTaskProgress)
  }

  function onLog(payload: TaskLogPayload): void {
    updateConsoleTaskState((state) => appendTaskLog(state, payload))
  }

  async function onCompleted(payload: TaskCompletedPayload): Promise<void> {
    const { item, runState } = lifecycle.getCurrentTaskContext()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskCompleted(runState.taskState))
      if (payload.outputPath) {
        deps.setItemLastOutputPath(item.id, payload.outputPath)
      }
    }
    // Successful completion clears any sticky 'task' banner from the prior run.
    deps.setTaskIssue(null)
    await lifecycle.finalizeCurrent('completed')
  }

  async function onError(error: TaskError): Promise<void> {
    if (conflict.tryStashFromError(error)) {
      return
    }
    await lifecycle.handleErrored(error)
  }

  async function onCancelled(payload?: TaskCancelledPayload | null): Promise<void> {
    const { item, runState } = lifecycle.getCurrentTaskContext()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskCancelled(runState.taskState))
    }
    // A watchdog stall is exceptional; user cancellation remains silent.
    const reason = payload?.reason ?? 'user'
    if (reason === 'stalled') {
      const stalledError: TaskError = {
        code: TASK_ERROR_CODES.ProcessFailed,
        message: '后端进程在配置的超时时间内无任何进度,任务已被中止。',
        details: payload?.details ?? null,
      }
      deps.setTaskIssue(stalledError)
    } else {
      deps.setTaskIssue(null)
    }
    await lifecycle.finalizeCurrent('cancelled')
  }

  function onResumeStatus(payload: ResumeStatusPayload): void {
    updateConsoleTaskState((state) => applyTaskResumeStatus(state, payload))
  }

  return {
    onProgress,
    onLog,
    onCompleted,
    onError,
    onCancelled,
    onResumeStatus,
  }
}
