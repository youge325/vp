// 批处理生命周期 — 状态机迁移与队列推进。
// 不感知 NDJSON 事件,也不感知 resume 冲突分类,只负责把内部状态从一个稳定态推到下一个稳定态。
// 由 [[batch-runner]] facade 汇总,与 [[conflict]] 和 [[events]] 共享 deps 引用。

import type { TaskRequest } from '@/types/protocol'
import type { MediaItem, MediaTaskState, TaskError } from '@/types/domain/media'
import type {
  BatchState,
  ResumeConflictDescriptor,
  ResumeInspectionResult,
  ResumeMode,
} from '@/types/domain/batch'
import {
  applyTaskCancelling,
  applyTaskError,
  applyTaskPaused,
  applyTaskResumed,
  createIdleTaskState,
} from '../events'
import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'
import { classifyResumeConflict } from '../resume-classifier'

export interface BatchLifecycleDeps {
  startTask: (req: TaskRequest) => Promise<void>
  cancelTask: () => Promise<void>
  pauseTask: () => Promise<void>
  resumeTask: () => Promise<void>
  checkResume: (req: TaskRequest) => Promise<ResumeInspectionResult>
  openOutputLocation: (path: string) => Promise<void>

  getMediaItem: (id: string) => MediaItem | null
  setItemTaskState: (id: string, state: MediaTaskState) => void
  setItemIssue: (id: string, issue: TaskError | null) => void
  setItemLastOutputPath: (id: string, path: string) => void
  resetItemRunState: (id: string, preserveLogs?: boolean) => void
  resetItemsRunState: (ids: Set<string>, preserveLogs?: boolean) => void
  setActiveItem: (id: string | null) => void
  getActiveItemId: () => string | null

  getBatch: () => BatchState
  setBatch: (partial: Partial<BatchState>) => void
  getRuntimeIds: () => string[]
  setRuntimeIds: (ids: string[]) => void
  setPendingConflict: (descriptor: ResumeConflictDescriptor | null) => void

  buildRequest: (item: MediaItem, resumeMode?: ResumeMode) => TaskRequest
}

export interface BatchLifecycle {
  getCurrentItem(): MediaItem | null
  getConsoleItem(): MediaItem | null
  runNextQueuedItem(): Promise<void>
  launchCurrentItem(item: MediaItem, resumeMode?: ResumeMode): Promise<void>
  finalizeCurrent(state: 'completed' | 'error' | 'cancelled'): Promise<void>
  handleErrored(error: TaskError): Promise<void>
  start(ids: string[]): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  cancel(): Promise<void>
}

export function createBatchLifecycle(deps: BatchLifecycleDeps): BatchLifecycle {
  function getCurrentItem(): MediaItem | null {
    const id = deps.getBatch().currentId
    return id ? deps.getMediaItem(id) : null
  }

  function getConsoleItem(): MediaItem | null {
    const current = getCurrentItem()
    if (current) {
      return current
    }
    const activeId = deps.getActiveItemId()
    return activeId ? deps.getMediaItem(activeId) : null
  }

  function clearBatchRuntimeArtifacts(preserveLogs = false): void {
    deps.resetItemsRunState(new Set(deps.getRuntimeIds()), preserveLogs)
  }

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
      startedAt: new Date().toISOString(),
    })

    let inspection: ResumeInspectionResult | null = null
    try {
      inspection = await deps.checkResume(deps.buildRequest(item))
    } catch (error) {
      await handleErrored(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
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
      await handleErrored(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    }
  }

  async function finalizeCurrent(state: 'completed' | 'error' | 'cancelled'): Promise<void> {
    const item = getCurrentItem()
    if (!item) {
      const queue = deps.getBatch().queue
      deps.setBatch({ currentId: null })
      if (queue.length > 0) {
        await runNextQueuedItem()
      } else {
        deps.setBatch({
          isRunning: false,
          isPaused: false,
          isCancelling: false,
        })
        clearBatchRuntimeArtifacts(true)
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
      await runNextQueuedItem()
      return
    }

    deps.setBatch({
      isRunning: false,
      isPaused: false,
      isCancelling: false,
    })
    clearBatchRuntimeArtifacts(true)
    deps.setBatch({ completedCount: 0, failedCount: 0 })
    deps.setRuntimeIds([])
  }

  async function handleErrored(error: TaskError): Promise<void> {
    const item = getCurrentItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskError(item.taskState, error))
      deps.setItemIssue(item.id, error)
    }
    await finalizeCurrent('error')
  }

  async function start(ids: string[]): Promise<void> {
    if (ids.length === 0 || deps.getBatch().isRunning) {
      return
    }
    resetBatchRunState(ids)
    await runNextQueuedItem()
  }

  async function pause(): Promise<void> {
    const batch = deps.getBatch()
    if (!batch.isRunning || batch.isPaused || batch.isCancelling) {
      return
    }

    try {
      await deps.pauseTask()
      deps.setBatch({ isPaused: true })
      const item = getCurrentItem()
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
      const item = getCurrentItem()
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
    const item = getCurrentItem()
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

  return {
    getCurrentItem,
    getConsoleItem,
    runNextQueuedItem,
    launchCurrentItem,
    finalizeCurrent,
    handleErrored,
    start,
    pause,
    resume,
    cancel,
  }
}
