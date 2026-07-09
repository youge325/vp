// NDJSON 事件订阅与归一 — 把 Tauri/Python 上抛的事件载荷映射到 store 状态。
// 不感知队列推进,仅做 "事件 → 当前/激活 item 的 taskState" 归一,
// 状态机迁移交给 [[lifecycle]] 完成。
//
// Phase 13.1 — ``item.taskState`` 改读 ``lifecycle.getConsoleRunState`` /
// ``getCurrentRunState``。``MediaItem`` 已不持有运行时投影,事件 reducer
// 把上一帧 ``taskState`` 从 [[useMediaRunState]] 拉出来后再 apply 新载荷。
//
// Phase 16 — ``onCancelled`` 在 stalled reason 下额外把构造的 banner
// error 写到 ``deps.setTaskIssue`` (``useIssueStore('task')``)。user
// 手动取消不写 banner —— "任务已取消" 是正常 UX 流转,不该弹错误条;
// 而 stalled 是 watchdog 主动判定的系统错误,需要 surfacing 给用户看
// stderr details。

import { TASK_ERROR_CODES } from '@/types/protocol'
import type { TaskError } from '@/types/domain/media'
import type {
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/protocol'
import type { ResumeStatus } from '@/types/domain/batch'
import {
  appendTaskLog,
  applyTaskCancelled,
  applyTaskCompleted,
  applyTaskProgress,
  applyTaskResumeStatus,
} from '../events'
import type { BatchLifecycle, BatchLifecycleDeps } from './lifecycle'
import type { createConflictResolver } from './conflict'

type ConflictResolver = ReturnType<typeof createConflictResolver>

type EventHandlersDeps = Pick<
  BatchLifecycleDeps,
  'setItemTaskState' | 'setItemLastOutputPath' | 'setTaskIssue'
>

interface EventHandlers {
  onProgress(payload: TaskProgressPayload): void
  onLog(payload: TaskLogPayload): void
  onCompleted(payload: TaskCompletedPayload): Promise<void>
  onError(error: TaskError): Promise<void>
  onCancelled(payload?: TaskCancelledPayload | null): Promise<void>
  onResumeStatus(payload: ResumeStatus): void
}

export function createEventHandlers(
  deps: EventHandlersDeps,
  lifecycle: BatchLifecycle,
  conflict: ConflictResolver,
): EventHandlers {
  function onProgress(): void {
    const item = lifecycle.getConsoleItem()
    const runState = lifecycle.getConsoleRunState()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskProgress(runState.taskState))
    }
  }

  function onLog(payload: TaskLogPayload): void {
    const item = lifecycle.getConsoleItem()
    const runState = lifecycle.getConsoleRunState()
    if (item && runState) {
      deps.setItemTaskState(item.id, appendTaskLog(runState.taskState, payload))
    }
  }

  async function onCompleted(payload: TaskCompletedPayload): Promise<void> {
    const item = lifecycle.getCurrentItem()
    const runState = lifecycle.getCurrentRunState()
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
    const item = lifecycle.getCurrentItem()
    const runState = lifecycle.getCurrentRunState()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskCancelled(runState.taskState))
    }
    // Phase D.1.2 — stall is a cancellation with reason "stalled". Surface
    // it as ProcessFailed in the 'task' banner. User-initiated cancels stay
    // silent (banner is for unexpected errors, not normal UX flow).
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

  function onResumeStatus(payload: ResumeStatus): void {
    const item = lifecycle.getConsoleItem()
    const runState = lifecycle.getConsoleRunState()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskResumeStatus(runState.taskState, payload))
    }
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
