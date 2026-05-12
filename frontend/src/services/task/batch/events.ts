// NDJSON 事件订阅与归一 — 把 Tauri/Python 上抛的事件载荷映射到 store 状态。
// 不感知队列推进,仅做 "事件 → 当前/激活 item 的 taskState" 归一,
// 状态机迁移交给 [[lifecycle]] 完成。

import type { TaskError } from '@/types/domain/media'
import type {
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
  onCancelled(): Promise<void>
  onResumeStatus(payload: ResumeStatus): void
}

export function createEventHandlers(
  deps: EventHandlersDeps,
  lifecycle: BatchLifecycle,
  conflict: ConflictResolver,
): EventHandlers {
  function onProgress(payload: TaskProgressPayload): void {
    const item = lifecycle.getConsoleItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskProgress(item.taskState, payload))
    }
  }

  function onLog(payload: TaskLogPayload): void {
    const item = lifecycle.getConsoleItem()
    if (item) {
      deps.setItemTaskState(item.id, appendTaskLog(item.taskState, payload))
    }
  }

  async function onCompleted(payload: TaskCompletedPayload): Promise<void> {
    const item = lifecycle.getCurrentItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskCompleted(item.taskState, payload))
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

  async function onCancelled(): Promise<void> {
    const item = lifecycle.getCurrentItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskCancelled(item.taskState))
    }
    await lifecycle.finalizeCurrent('cancelled')
  }

  function onResumeStatus(payload: ResumeStatus): void {
    const item = lifecycle.getConsoleItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskResumeStatus(item.taskState, payload))
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
