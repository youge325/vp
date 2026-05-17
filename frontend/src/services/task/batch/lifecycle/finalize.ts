// 终态回收 — finalizeCurrent / handleErrored。
//
// Phase 7a — 从原 ``lifecycle.ts`` 抽出。负责把当前任务在 completed /
// error / cancelled 终态后的所有副作用走完(打开输出文件、记账、清理
// runtime ids、推进下一个 queued item),并暴露 ``handleErrored`` 给
// queue 层做"启动失败"的统一汇集。
//
// 通过 ``internal.runNextQueuedItem`` 与 queue.ts 互相调用,组装在
// index.ts 里用 lazy closure 完成 forward reference。

import type { TaskError } from '@/types/domain/media'

import { applyTaskError } from '../../events'

import type { CommonHelpers } from './common'
import type { BatchLifecycleDeps } from './types'

export interface FinalizeInternalRefs {
  runNextQueuedItem: () => Promise<void>
}

export interface FinalizeOps {
  finalizeCurrent(state: 'completed' | 'error' | 'cancelled'): Promise<void>
  handleErrored(error: TaskError): Promise<void>
}

export function createFinalizeOps(
  deps: BatchLifecycleDeps,
  helpers: CommonHelpers,
  internal: FinalizeInternalRefs,
): FinalizeOps {
  async function finalizeCurrent(state: 'completed' | 'error' | 'cancelled'): Promise<void> {
    const item = helpers.getCurrentItem()
    if (!item) {
      const queue = deps.getBatch().queue
      deps.setBatch({ currentId: null })
      if (queue.length > 0) {
        await internal.runNextQueuedItem()
      } else {
        deps.setBatch({
          isRunning: false,
          isPaused: false,
          isCancelling: false,
        })
        helpers.clearBatchRuntimeArtifacts(true)
        deps.setBatch({ completedCount: 0, failedCount: 0 })
        deps.setRuntimeIds([])
      }
      return
    }

    if (state === 'completed' || state === 'cancelled') {
      if (item.outputConfig.openOnComplete && item.lastOutputPath) {
        try {
          await deps.openOutputLocation(item.lastOutputPath)
        } catch {
          // Ignore shell-open failures after processing finished.
        }
      }
      const batch = deps.getBatch()
      if (state === 'completed') {
        deps.setBatch({ completedCount: batch.completedCount + 1 })
      } else {
        deps.setBatch({ failedCount: batch.failedCount + 1 })
      }
    } else {
      const batch = deps.getBatch()
      deps.setBatch({ failedCount: batch.failedCount + 1 })
    }

    deps.setBatch({ currentId: null })
    if (deps.getBatch().queue.length > 0) {
      deps.setBatch({ isPaused: false, isCancelling: false })
      await internal.runNextQueuedItem()
      return
    }

    deps.setBatch({
      isRunning: false,
      isPaused: false,
      isCancelling: false,
    })
    helpers.clearBatchRuntimeArtifacts(true)
    deps.setBatch({ completedCount: 0, failedCount: 0 })
    deps.setRuntimeIds([])
  }

  async function handleErrored(error: TaskError): Promise<void> {
    const item = helpers.getCurrentItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskError(item.taskState, error))
      deps.setItemIssue(item.id, error)
    }
    await finalizeCurrent('error')
  }

  return { finalizeCurrent, handleErrored }
}
