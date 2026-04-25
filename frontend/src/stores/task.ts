import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { UnlistenFn } from '@tauri-apps/api/event'
import {
  cancelTask,
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
  applyTaskResumed,
  createIdleTaskState,
} from '@/lib/task-events'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import type { BatchState, TaskCompletedPayload, TaskError, TaskLogPayload, TaskProgressPayload } from '@/types'

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
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()

  const batch = reactive<BatchState>(createInitialBatch())
  const batchRuntimeIds = ref<string[]>([])

  let detachListenersHandle: UnlistenFn | null = null

  const selectedIds = computed(() => mediaStore.selectedIds)
  const selectedItems = computed(() => mediaStore.selectedItems)
  const currentTaskItem = computed(() => mediaStore.mediaItems.find((item) => item.id === batch.currentId) ?? null)
  const consoleTaskItem = computed(() => currentTaskItem.value ?? mediaStore.activeItem)

  const canStartBatch = computed(
    () => !batch.isRunning && selectedItems.value.length > 0 && selectedItems.value.every((item) => Boolean(item.inputPath)),
  )
  const batchTotal = computed(() => batchRuntimeIds.value.length || selectedItems.value.length)
  const globalTaskStatus = computed(() => {
    if (batch.isRunning) {
      return currentTaskItem.value?.taskState.status ?? 'running'
    }
    return 'idle'
  })

  function resetItemRunState(item: { taskState: ReturnType<typeof createIdleTaskState>; issue: TaskError | null; lastOutputPath: string }, preserveLogs: boolean = false): void {
    const existingLogs = preserveLogs ? item.taskState.logs : []
    item.taskState = { ...createIdleTaskState(), logs: existingLogs }
    item.issue = null
    item.lastOutputPath = ''
  }

  function clearBatchRuntimeArtifacts(preserveLogs: boolean = false): void {
    const runtimeIds = new Set(batchRuntimeIds.value)
    for (const item of mediaStore.mediaItems) {
      if (!runtimeIds.has(item.id)) {
        continue
      }
      resetItemRunState(item, preserveLogs)
    }
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
      resetItemRunState(item)
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
    mediaStore.activeItemId = nextId
    item.taskState = {
      ...createIdleTaskState(),
      status: 'running',
      startedAt: new Date().toISOString(),
    }

    try {
      await startTask(buildTaskRequest(item))
    } catch (error) {
      await handleCurrentTaskErrored(normalizeTaskError(error, 'start_failed'))
    }
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
      if (item.outputConfig.openOnComplete) {
        const fallbackDir = envStore.env.checkResult?.resources?.output_dir
        const openPath = item.lastOutputPath || item.outputConfig.outputDir || (typeof fallbackDir === 'string' ? fallbackDir : '')
        if (openPath) {
          try {
            await openOutputLocation(openPath)
          } catch {
            // Ignore shell-open failures after processing finished.
          }
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
    envStore.clearOperationIssue('task')
    envStore.clearOperationIssue('output')
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
      envStore.clearOperationIssue('task')
    } catch (error) {
      envStore.setOperationIssue('task', normalizeTaskError(error, 'pause_failed'))
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
      envStore.clearOperationIssue('task')
    } catch (error) {
      envStore.setOperationIssue('task', normalizeTaskError(error, 'resume_failed'))
    }
  }

  async function interruptBatch(): Promise<void> {
    if (!batch.isRunning || batch.isCancelling) {
      return
    }

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
      envStore.clearOperationIssue('task')
    } catch (error) {
      batch.queue = previousQueue
      batch.isPaused = wasPaused
      batch.isCancelling = false
      if (item && previousTaskState) {
        item.taskState = previousTaskState
      }
      envStore.setOperationIssue('task', normalizeTaskError(error, 'cancel_failed'))
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
        void handleCurrentTaskErrored(error)
      },
      onCancelled() {
        void handleCurrentTaskCancelled()
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
    selectedIds,
    selectedItems,
    currentTaskItem,
    consoleTaskItem,
    canStartBatch,
    batchTotal,
    globalTaskStatus,
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
  }
})
