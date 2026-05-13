// 应用层 — 批处理编排:把 batch-runner 与 stores、IPC 装配,提供 listener 桥。

import { computed, onScopeDispose } from 'vue'
import type { UnlistenFn } from '@/lib/ipc'
import { listenTaskEvents } from '@/lib/ipc/events'
import { taskIpc } from '@/lib/ipc/endpoints/task'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import { createBatchRunner, type BatchRunner } from '@/services/task/batch-runner'
import { buildTaskRequest } from '@/services/task/request-builder'

export function useTaskOrchestrator() {
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()

  let cachedRunner: BatchRunner | null = null
  let detachHandle: UnlistenFn | null = null

  onScopeDispose(() => {
    detachHandle?.()
    detachHandle = null
    cachedRunner = null
  })

  const batch = taskStore.batch
  const pendingConflict = taskStore.pendingConflict
  const currentTaskItem = computed(() =>
    mediaStore.mediaItems.find((item) => item.id === taskStore.batch.currentId) ?? null,
  )
  const consoleTaskItem = computed(() => currentTaskItem.value ?? mediaStore.activeItem)
  const canStartBatch = computed(
    () =>
      !taskStore.batch.isRunning &&
      mediaStore.selectedItems.length > 0 &&
      mediaStore.selectedItems.every((item) => Boolean(item.inputPath)),
  )
  const batchTotal = computed(() => taskStore.batchRuntimeIds.length || mediaStore.selectedItems.length)

  function getRunner(): BatchRunner {
    if (cachedRunner) {
      return cachedRunner
    }
    cachedRunner = createBatchRunner({
      startTask: taskIpc.start,
      cancelTask: taskIpc.cancel,
      pauseTask: taskIpc.pause,
      resumeTask: taskIpc.resume,
      checkResume: taskIpc.checkResume,
      openOutputLocation: taskIpc.openOutputLocation,
      getMediaItem: (id) => mediaStore.findItem(id),
      setItemTaskState: (id, state) => mediaStore.setItemTaskState(id, state),
      setItemIssue: (id, issue) => mediaStore.setItemIssue(id, issue),
      setItemLastOutputPath: (id, path) => mediaStore.setItemLastOutputPath(id, path),
      resetItemRunState: (id, preserveLogs) => mediaStore.resetItemRunState(id, preserveLogs),
      resetItemsRunState: (ids, preserveLogs) => mediaStore.resetItemsRunState(ids, preserveLogs),
      setActiveItem: (id) => mediaStore.setActive(id),
      getActiveItemId: () => mediaStore.activeItemId,
      getBatch: () => taskStore.batch,
      setBatch: (partial) => taskStore.setBatch(partial),
      getRuntimeIds: () => taskStore.batchRuntimeIds,
      setRuntimeIds: (ids) => taskStore.setRuntimeIds(ids),
      setPendingConflict: (descriptor) => taskStore.setPendingConflict(descriptor),
      buildRequest: (item, resumeMode) => buildTaskRequest(item, resumeMode),
    })
    return cachedRunner
  }

  async function startBatch(): Promise<void> {
    if (!canStartBatch.value) {
      return
    }
    await getRunner().start(mediaStore.selectedIds)
  }

  async function pauseCurrentTask(): Promise<void> {
    await getRunner().pause()
  }

  async function resumeCurrentTask(): Promise<void> {
    await getRunner().resume()
  }

  async function interruptBatch(): Promise<void> {
    await getRunner().cancel()
  }

  async function resolveConflict(action: Parameters<BatchRunner['resolveConflict']>[0]): Promise<void> {
    await getRunner().resolveConflict(action)
  }

  async function attachTaskListeners(): Promise<void> {
    if (detachHandle) {
      return
    }
    const runner = getRunner()
    detachHandle = await listenTaskEvents({
      onProgress: (payload) => runner.onProgress(payload),
      onLog: (payload) => runner.onLog(payload),
      onCompleted: (payload) => void runner.onCompleted(payload),
      onError: (error) => void runner.onError(error),
      onCancelled: (payload) => void runner.onCancelled(payload),
      onResumeStatus: (payload) => runner.onResumeStatus(payload),
    })
  }

  function detachTaskListeners(): void {
    detachHandle?.()
    detachHandle = null
  }

  return {
    batch,
    pendingConflict,
    currentTaskItem,
    consoleTaskItem,
    canStartBatch,
    batchTotal,
    startBatch,
    pauseCurrentTask,
    resumeCurrentTask,
    interruptBatch,
    cancelCurrentTask: interruptBatch,
    resolveConflict,
    attachTaskListeners,
    detachTaskListeners,
  }
}
