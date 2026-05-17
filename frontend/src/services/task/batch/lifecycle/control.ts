// 控制信号 — pause / resume / cancel。
//
// Phase 7a — 从原 ``lifecycle.ts`` 抽出。这三个函数都是"对运行中任务发
// 出 IPC 控制信号 + 同步 batch 标志位 + 在失败时回滚"的对称结构,集中
// 到一个文件后将来想统一加 retry / 信号节流时只改这里一处。
//
// 与 queue / finalize 不同,control 不需要前向引用 — pause/resume/cancel
// 不调用对方,失败也只是把状态翻回去并抛错,由 caller(orchestrator /
// UI)决定下一步。

import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'

import { applyTaskCancelling, applyTaskPaused, applyTaskResumed } from '../../events'

import type { CommonHelpers } from './common'
import type { BatchLifecycleDeps } from './types'

export interface ControlOps {
  pause(): Promise<void>
  resume(): Promise<void>
  cancel(): Promise<void>
}

export function createControlOps(
  deps: BatchLifecycleDeps,
  helpers: CommonHelpers,
): ControlOps {
  async function pause(): Promise<void> {
    const batch = deps.getBatch()
    if (!batch.isRunning || batch.isPaused || batch.isCancelling) {
      return
    }

    try {
      await deps.pauseTask()
      deps.setBatch({ isPaused: true })
      const item = helpers.getCurrentItem()
      if (item) {
        deps.setItemTaskState(item.id, applyTaskPaused(item.taskState))
      }
    } catch (error) {
      throw normalizeError(error, TASK_ERROR_CODES.ProcessFailed)
    }
  }

  async function resume(): Promise<void> {
    const batch = deps.getBatch()
    if (!batch.isRunning || !batch.isPaused || batch.isCancelling) {
      return
    }

    try {
      await deps.resumeTask()
      deps.setBatch({ isPaused: false })
      const item = helpers.getCurrentItem()
      if (item) {
        deps.setItemTaskState(item.id, applyTaskResumed(item.taskState))
      }
    } catch (error) {
      throw normalizeError(error, TASK_ERROR_CODES.ProcessFailed)
    }
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
    const previousTaskState = item?.taskState ?? null

    deps.setBatch({
      queue: [],
      isPaused: false,
      isCancelling: true,
    })
    if (item) {
      deps.setItemTaskState(item.id, applyTaskCancelling(item.taskState))
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
