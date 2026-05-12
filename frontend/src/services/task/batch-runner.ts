// pure: no Vue / no Pinia / no Tauri
// 批处理状态机 — 完全净化的工厂函数,所有副作用通过 deps 注入。
// 调度顺序: start → checkResume → (conflict ? pending : launch) → 事件回调 → finalize → next。

import type { TaskRequest } from '@/types/protocol'
import type { MediaItem, MediaTaskState, TaskError } from '@/types/domain/media'
import type {
  BatchState,
  ResumeConflictAction,
  ResumeConflictDescriptor,
  ResumeInspectionResult,
  ResumeMode,
  ResumeStatus,
} from '@/types/domain/batch'
import type { TaskCompletedPayload, TaskLogPayload, TaskProgressPayload } from '@/types/protocol'
import { TASK_ERROR_CODES } from '@/types/protocol'
import {
  appendTaskLog,
  applyTaskCancelled,
  applyTaskCancelling,
  applyTaskCompleted,
  applyTaskError,
  applyTaskPaused,
  applyTaskProgress,
  applyTaskResumeStatus,
  applyTaskResumed,
  createIdleTaskState,
} from './events'
import { buildInspectionFromError, classifyResumeConflict } from './resume-classifier'
import { normalizeError } from '@/services/error/normalize'

export interface BatchRunnerDeps {
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

export interface BatchRunner {
  start(ids: string[]): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  cancel(): Promise<void>
  resolveConflict(action: ResumeConflictAction): Promise<void>
  onProgress(payload: TaskProgressPayload): void
  onLog(payload: TaskLogPayload): void
  onCompleted(payload: TaskCompletedPayload): Promise<void>
  onError(error: TaskError): Promise<void>
  onCancelled(): Promise<void>
  onResumeStatus(payload: ResumeStatus): void
}

export function createBatchRunner(deps: BatchRunnerDeps): BatchRunner {
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
      await handleErrored(normalizeError(error, 'start_failed'))
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
      await handleErrored(normalizeError(error, 'start_failed'))
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
      throw normalizeError(error, 'pause_failed')
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
      throw normalizeError(error, 'resume_failed')
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
      throw normalizeError(error, 'cancel_failed')
    }
  }

  async function resolveConflict(action: ResumeConflictAction): Promise<void> {
    const batch = deps.getBatch()
    const conflictItem = batch.currentId ? deps.getMediaItem(batch.currentId) : null
    deps.setPendingConflict(null)

    if (!conflictItem) {
      await finalizeCurrent('cancelled')
      return
    }

    if (action === 'cancel') {
      deps.setBatch({ queue: [] })
      await finalizeCurrent('cancelled')
      return
    }

    if (action === 'skip') {
      await finalizeCurrent('cancelled')
      return
    }

    const mode: ResumeMode | undefined = action === 'fresh' ? 'force-fresh' : undefined
    await launchCurrentItem(conflictItem, mode)
  }

  function onProgress(payload: TaskProgressPayload): void {
    const item = getConsoleItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskProgress(item.taskState, payload))
    }
  }

  function onLog(payload: TaskLogPayload): void {
    const item = getConsoleItem()
    if (item) {
      deps.setItemTaskState(item.id, appendTaskLog(item.taskState, payload))
    }
  }

  async function onCompleted(payload: TaskCompletedPayload): Promise<void> {
    const item = getCurrentItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskCompleted(item.taskState, payload))
      if (payload.outputPath) {
        deps.setItemLastOutputPath(item.id, payload.outputPath)
      }
    }
    await finalizeCurrent('completed')
  }

  async function onError(error: TaskError): Promise<void> {
    if (error.code === TASK_ERROR_CODES.ResumeConflict) {
      const item = getCurrentItem()
      if (item) {
        const inspection = buildInspectionFromError(error, item.inputPath)
        deps.setPendingConflict({
          itemId: item.id,
          kind: inspection.signatureMatch ? 'final_exists_with_resume' : 'final_exists_only',
          outputPath: inspection.outputPath,
          inspection,
        })
        return
      }
    }
    await handleErrored(error)
  }

  async function onCancelled(): Promise<void> {
    const item = getCurrentItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskCancelled(item.taskState))
    }
    await finalizeCurrent('cancelled')
  }

  function onResumeStatus(payload: ResumeStatus): void {
    const item = getConsoleItem()
    if (item) {
      deps.setItemTaskState(item.id, applyTaskResumeStatus(item.taskState, payload))
    }
  }

  return {
    start,
    pause,
    resume,
    cancel,
    resolveConflict,
    onProgress,
    onLog,
    onCompleted,
    onError,
    onCancelled,
    onResumeStatus,
  }
}
