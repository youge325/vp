import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { UnlistenFn } from '@tauri-apps/api/event'
import {
  cancelTask,
  checkResumeState,
  listenTaskEvents,
  openOutputLocation,
  pauseTask,
  resumeTask,
  startTask,
} from '@/lib/tauri'
import { buildTaskRequest, normalizeTaskError } from '@/lib/task-mapper'
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
} from '@/lib/task-events'
import { useMediaStore } from '@/stores/media'
import { TASK_ERROR_CODES } from '@/types'
import type {
  BatchState,
  ResumeConflictAction,
  ResumeConflictDescriptor,
  ResumeConflictKind,
  ResumeInspectionResult,
  ResumeMode,
  ResumeStatus,
  TaskCompletedPayload,
  TaskError,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types'

function createInitialBatch(): BatchState {
  return {
    queue: [],
    currentId: null,
    completedCount: 0,
    failedCount: 0,
    isRunning: false,
    isPaused: false,
    isCancelling: false,
  }
}

export const useTaskStore = defineStore('task', () => {
  const mediaStore = useMediaStore()

  const batch = reactive<BatchState>(createInitialBatch())
  const batchRuntimeIds = ref<string[]>([])
  const pendingConflict = ref<ResumeConflictDescriptor | null>(null)

  let detachListenersHandle: UnlistenFn | null = null

  const selectedIds = computed(() => mediaStore.selectedIds)
  const selectedItems = computed(() => mediaStore.selectedItems)
  const currentTaskItem = computed(() => mediaStore.mediaItems.find((item) => item.id === batch.currentId) ?? null)
  const consoleTaskItem = computed(() => currentTaskItem.value ?? mediaStore.activeItem)

  const canStartBatch = computed(
    () => !batch.isRunning && selectedItems.value.length > 0 && selectedItems.value.every((item) => Boolean(item.inputPath)),
  )
  const batchTotal = computed(() => batchRuntimeIds.value.length || selectedItems.value.length)

  function clearBatchRuntimeArtifacts(preserveLogs: boolean = false): void {
    mediaStore.resetItemsRunState(new Set(batchRuntimeIds.value), preserveLogs)
  }

  function resetBatchCounters(): void {
    batch.completedCount = 0
    batch.failedCount = 0
  }

  function resetBatchRunState(ids: string[]): void {
    batchRuntimeIds.value = [...ids]
    batch.queue = [...ids]
    batch.currentId = null
    resetBatchCounters()
    batch.isRunning = ids.length > 0
    batch.isPaused = false
    batch.isCancelling = false

    const queuedIds = new Set(ids)
    for (const item of mediaStore.mediaItems) {
      if (!queuedIds.has(item.id)) {
        continue
      }
      mediaStore.resetItemRunState(item)
    }
  }

  async function runNextQueuedItem(): Promise<void> {
    const nextId = batch.queue.shift() ?? null
    if (!nextId) {
      batch.currentId = null
      batch.isRunning = false
      batch.isPaused = false
      batch.isCancelling = false
      return
    }

    const item = mediaStore.findItem(nextId)
    if (!item) {
      batch.currentId = null
      await runNextQueuedItem()
      return
    }

    batch.currentId = nextId
    batch.isPaused = false
    batch.isCancelling = false
    mediaStore.setActiveItem(nextId)
    item.taskState = {
      ...createIdleTaskState(),
      status: 'running',
      startedAt: new Date().toISOString(),
    }

    let inspection: ResumeInspectionResult | null = null
    try {
      inspection = await checkResumeState(buildTaskRequest(item))
    } catch (error) {
      // Pre-flight failure: emit the error and move on to the next item.
      await handleCurrentTaskErrored(normalizeTaskError(error, 'start_failed'))
      return
    }

    const conflict = _classifyConflict(inspection)
    if (conflict) {
      pendingConflict.value = {
        itemId: nextId,
        kind: conflict,
        outputPath: inspection.outputPath,
        inspection,
      }
      // Hold the item in 'running' state but defer the actual startTask
      // until the user resolves the dialog via resolveConflict().
      return
    }

    await _launchCurrentItem(item)
  }

  async function _launchCurrentItem(
    item: ReturnType<typeof mediaStore.findItem> & {},
    resumeMode?: ResumeMode,
  ): Promise<void> {
    try {
      await startTask(buildTaskRequest(item, resumeMode))
    } catch (error) {
      await handleCurrentTaskErrored(normalizeTaskError(error, 'start_failed'))
    }
  }

  function _classifyConflict(inspection: ResumeInspectionResult): ResumeConflictKind | null {
    if (!inspection.finalExists) {
      return null
    }
    if (inspection.signatureMatch && inspection.completedChunks > 0) {
      return 'final_exists_with_resume'
    }
    return 'final_exists_only'
  }

  async function resolveConflict(action: ResumeConflictAction): Promise<void> {
    const conflict = pendingConflict.value
    pendingConflict.value = null
    if (!conflict) {
      return
    }
    const item = mediaStore.findItem(conflict.itemId)
    if (!item) {
      await finalizeCurrentTask('cancelled')
      return
    }

    if (action === 'cancel') {
      // Cancel the entire batch; the running item is not yet started.
      batch.queue = []
      await finalizeCurrentTask('cancelled')
      return
    }

    if (action === 'skip') {
      await finalizeCurrentTask('cancelled')
      return
    }

    const mode: ResumeMode | undefined = action === 'fresh' ? 'force-fresh' : undefined
    await _launchCurrentItem(item, mode)
  }

  async function finalizeCurrentTask(state: 'completed' | 'error' | 'cancelled'): Promise<void> {
    const item = currentTaskItem.value
    if (!item) {
      batch.currentId = null
      if (batch.queue.length > 0) {
        await runNextQueuedItem()
      } else {
        batch.isRunning = false
        batch.isPaused = false
        batch.isCancelling = false
        clearBatchRuntimeArtifacts(true)
        resetBatchCounters()
        batchRuntimeIds.value = []
      }
      return
    }

    if (state === 'completed') {
      if (item.outputConfig.openOnComplete && item.lastOutputPath) {
        try {
          await openOutputLocation(item.lastOutputPath)
        } catch {
          // Ignore shell-open failures after processing finished.
        }
      }
      batch.completedCount += 1
    } else if (state === 'cancelled') {
      if (item.outputConfig.openOnComplete && item.lastOutputPath) {
        try {
          await openOutputLocation(item.lastOutputPath)
        } catch {
          // Ignore shell-open failures after processing finished.
        }
      }
      batch.failedCount += 1
    } else {
      batch.failedCount += 1
    }

    batch.currentId = null
    if (batch.queue.length > 0) {
      batch.isPaused = false
      batch.isCancelling = false
      await runNextQueuedItem()
      return
    }

    batch.isRunning = false
    batch.isPaused = false
    batch.isCancelling = false
    clearBatchRuntimeArtifacts(true)
    resetBatchCounters()
    batchRuntimeIds.value = []
  }

  async function handleCurrentTaskCompleted(payload: TaskCompletedPayload): Promise<void> {
    const item = currentTaskItem.value
    if (item) {
      item.taskState = applyTaskCompleted(item.taskState, payload)
      item.lastOutputPath = payload.outputPath ?? item.lastOutputPath
    }
    await finalizeCurrentTask('completed')
  }

  async function handleCurrentTaskErrored(error: TaskError): Promise<void> {
    const item = currentTaskItem.value
    if (item) {
      item.taskState = applyTaskError(item.taskState, error)
      item.issue = error
    }
    await finalizeCurrentTask('error')
  }

  async function handleCurrentTaskCancelled(): Promise<void> {
    const item = currentTaskItem.value
    if (item) {
      item.taskState = applyTaskCancelled(item.taskState)
    }
    await finalizeCurrentTask('cancelled')
  }

  async function startBatch(): Promise<void> {
    if (!canStartBatch.value) {
      return
    }
    resetBatchRunState(selectedIds.value)
    await runNextQueuedItem()
  }

  async function pauseCurrentTask(): Promise<void> {
    if (!batch.isRunning || batch.isPaused || batch.isCancelling) {
      return
    }

    try {
      await pauseTask()
      batch.isPaused = true
      const item = currentTaskItem.value
      if (item) {
        item.taskState = applyTaskPaused(item.taskState)
      }
    } catch (error) {
      throw normalizeTaskError(error, 'pause_failed')
    }
  }

  async function resumeCurrentTask(): Promise<void> {
    if (!batch.isRunning || !batch.isPaused || batch.isCancelling) {
      return
    }

    try {
      await resumeTask()
      batch.isPaused = false
      const item = currentTaskItem.value
      if (item) {
        item.taskState = applyTaskResumed(item.taskState)
      }
    } catch (error) {
      throw normalizeTaskError(error, 'resume_failed')
    }
  }

  async function interruptBatch(): Promise<void> {
    if (!batch.isRunning || batch.isCancelling) {
      return
    }

    // Drop any pending conflict modal — the user is interrupting the batch.
    pendingConflict.value = null

    const previousQueue = [...batch.queue]
    const wasPaused = batch.isPaused
    const item = currentTaskItem.value
    const previousTaskState = item?.taskState ?? null

    batch.queue = []
    batch.isPaused = false
    batch.isCancelling = true
    if (item) {
      item.taskState = applyTaskCancelling(item.taskState)
    }

    try {
      await cancelTask()
    } catch (error) {
      batch.queue = previousQueue
      batch.isPaused = wasPaused
      batch.isCancelling = false
      if (item && previousTaskState) {
        item.taskState = previousTaskState
      }
      throw normalizeTaskError(error, 'cancel_failed')
    }
  }

  async function cancelCurrentTask(): Promise<void> {
    await interruptBatch()
  }

  async function attachTaskListeners(): Promise<void> {
    if (detachListenersHandle) {
      return
    }

    detachListenersHandle = await listenTaskEvents({
      onProgress(payload) {
        const item = currentTaskItem.value ?? mediaStore.activeItem
        if (item) {
          item.taskState = applyTaskProgress(item.taskState, payload as TaskProgressPayload)
        }
      },
      onLog(payload) {
        const item = currentTaskItem.value ?? mediaStore.activeItem
        if (item) {
          item.taskState = appendTaskLog(item.taskState, payload as TaskLogPayload)
        }
      },
      onCompleted(payload) {
        void handleCurrentTaskCompleted(payload as TaskCompletedPayload)
      },
      onError(error) {
        // The backend may emit a resume_conflict if the pre-flight raced with
        // a filesystem change; surface it through the same dialog as the
        // pre-flight detection to keep the UX consistent.
        if (error.code === TASK_ERROR_CODES.ResumeConflict) {
          const item = currentTaskItem.value
          if (item) {
            const details = (error.details ?? {}) as Record<string, unknown>
            const inspection: ResumeInspectionResult = {
              type: 'resume_inspection',
              pipeline_kind: 'streaming',
              outputPath: typeof details.outputPath === 'string' ? details.outputPath : '',
              inputPath: typeof details.inputPath === 'string' ? details.inputPath : item.inputPath,
              finalExists: true,
              sidecarExists: Boolean(details.sidecarSignatureMatch),
              signatureMatch: Boolean(details.sidecarSignatureMatch),
              completedChunks: Number(details.completedChunks ?? 0),
              completedOutputFrames: Number(details.completedOutputFrames ?? 0),
              nextSourceFrame: 0,
              totalOutputFrames: 0,
            }
            pendingConflict.value = {
              itemId: item.id,
              kind: inspection.signatureMatch ? 'final_exists_with_resume' : 'final_exists_only',
              outputPath: inspection.outputPath,
              inspection,
            }
            return
          }
        }
        void handleCurrentTaskErrored(error)
      },
      onCancelled() {
        void handleCurrentTaskCancelled()
      },
      onResumeStatus(payload) {
        const item = currentTaskItem.value ?? mediaStore.activeItem
        if (item) {
          item.taskState = applyTaskResumeStatus(item.taskState, payload as ResumeStatus)
        }
      },
    })
  }

  function detachTaskListeners(): void {
    detachListenersHandle?.()
    detachListenersHandle = null
  }

  return {
    batch,
    batchRuntimeIds,
    pendingConflict,
    selectedIds,
    selectedItems,
    currentTaskItem,
    consoleTaskItem,
    canStartBatch,
    batchTotal,
    startBatch,
    runNextQueuedItem,
    pauseCurrentTask,
    resumeCurrentTask,
    interruptBatch,
    cancelCurrentTask,
    attachTaskListeners,
    detachTaskListeners,
    handleCurrentTaskCompleted,
    handleCurrentTaskErrored,
    handleCurrentTaskCancelled,
    resolveConflict,
  }
})
