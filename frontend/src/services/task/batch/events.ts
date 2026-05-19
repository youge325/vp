// NDJSON 事件订阅与归一 — 把 Tauri/Python 上抛的事件载荷映射到 store 状态。
// 不感知队列推进,仅做 "事件 → 当前/激活 item 的 taskState" 归一,
// 状态机迁移交给 [[lifecycle]] 完成。
//
// Phase 13.1 — ``item.taskState`` 改读 ``lifecycle.getConsoleRunState`` /
// ``getCurrentRunState``。``MediaItem`` 已不持有运行时投影,事件 reducer
// 把上一帧 ``taskState`` 从 [[useMediaRunState]] 拉出来后再 apply 新载荷。

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
import type { ConflictResolver } from './conflict'

export type EventHandlersDeps = Pick<
  BatchLifecycleDeps,
  'setItemTaskState' | 'setItemLastOutputPath'
>

export interface EventHandlers {
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
  function onProgress(payload: TaskProgressPayload): void {
    const item = lifecycle.getConsoleItem()
    const runState = lifecycle.getConsoleRunState()
    if (item && runState) {
      deps.setItemTaskState(item.id, applyTaskProgress(runState.taskState, payload))
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
      deps.setItemTaskState(item.id, applyTaskCompleted(runState.taskState, payload))
      if (payload.outputPath) {
        deps.setItemLastOutputPath(item.id, payload.outputPath)
      }
    }
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
      deps.setItemTaskState(item.id, applyTaskCancelled(runState.taskState, payload))
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
