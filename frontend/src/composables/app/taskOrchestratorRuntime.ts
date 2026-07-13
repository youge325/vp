// Runtime adapter for the shared batch runner singleton.
//
// ``useTaskOrchestrator`` owns UI-facing computed state; this module owns the
// process-level wiring between stores, IPC endpoints, task event listeners and
// the pure ``BatchRunner`` facade.

import { listenTaskEvents, type UnlistenFn } from '@/lib/ipc/events'
import { taskIpc } from '@/lib/ipc/endpoints/task'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'
import { createBatchRunner, type BatchRunner } from '@/services/task/batch-runner'
import { buildTaskRequest } from '@/services/task/request-builder'

let cachedRunner: BatchRunner | null = null
let detachHandle: UnlistenFn | null = null

export function getTaskRunner(): BatchRunner {
  if (cachedRunner) {
    return cachedRunner
  }

  const issueStore = useIssueStore()
  const mediaStore = useMediaStore()
  const mediaRunState = useMediaRunState()
  const taskStore = useTaskStore()

  cachedRunner = createBatchRunner({
    startTask: taskIpc.start,
    cancelTask: taskIpc.cancel,
    pauseTask: taskIpc.pause,
    resumeTask: taskIpc.resume,
    checkResume: taskIpc.checkResume,
    openOutputLocation: taskIpc.openOutputLocation,
    getMediaItem: (id) => mediaStore.findItem(id),
    getItemRunState: (id) => mediaRunState.getByItemId(id),
    setItemTaskState: (id, state) => mediaRunState.setTaskState(id, state),
    setTaskIssue: (issue) => {
      if (issue) {
        issueStore.setIssue('task', issue)
      } else {
        issueStore.clearIssue('task')
      }
    },
    setItemLastOutputPath: (id, path) => mediaRunState.setLastOutputPath(id, path),
    resetItemRunState: (id, preserveLogs) => mediaRunState.resetItemRunState(id, preserveLogs),
    resetItemsRunState: (ids, preserveLogs) => mediaRunState.resetItemsRunState(ids, preserveLogs),
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

export function disposeRunner(): void {
  detachHandle?.()
  detachHandle = null
  cachedRunner = null
}

export async function attachTaskListeners(): Promise<void> {
  if (detachHandle) {
    return
  }

  const runner = getTaskRunner()
  detachHandle = await listenTaskEvents(runner)
}
