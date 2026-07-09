// 队列推进 — start / runNextQueuedItem / launchCurrentItem / resetBatchRunState。
//
// Phase 7a — 从原 ``lifecycle.ts`` 抽出。负责把待处理 ids 推入队列,
// 逐个 ``checkResume`` → ``classifyResumeConflict`` → 启动任务的流程,
// 以及在 ``cancel`` / ``finalize`` 之后回到 idle 时的清理。
//
// 不直接管理终态回收:finalize.ts 的 ``finalizeCurrent`` 负责 completed /
// cancelled / error 的 batch 计数与递归调度,本文件只在每个任务的"启动
// 前"阶段工作,并通过传入的 ``internal.handleErrored`` 把启动失败转交给
// finalize 层处理。

import type { MediaItem } from '@/types/domain/media'
import type { ResumeInspectionResult, ResumeMode } from '@/types/domain/batch'
import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'

import { createIdleTaskState } from '../../events'
import { classifyResumeConflict } from '../../resume-classifier'

import type { createCommonHelpers } from './common'
import type { BatchLifecycleDeps } from './types'

type CommonHelpers = ReturnType<typeof createCommonHelpers>

interface QueueInternalRefs {
  handleErrored: (error: ReturnType<typeof normalizeError>) => Promise<void>
}

interface QueueOps {
  start(ids: string[]): Promise<void>
  runNextQueuedItem(): Promise<void>
  launchCurrentItem(item: MediaItem, resumeMode?: ResumeMode): Promise<void>
}

export function createQueueOps(
  deps: BatchLifecycleDeps,
  _helpers: CommonHelpers,
  internal: QueueInternalRefs,
): QueueOps {
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

    const conflict = classifyResumeConflict(inspection)
    if (conflict) {
      deps.setPendingConflict({
        itemId: nextId,
        kind: conflict,
        outputPath: inspection.outputPath,
        inspection,
      })
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
