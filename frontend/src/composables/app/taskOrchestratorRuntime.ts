// Runtime adapter for the shared batch runner singleton.
//
// ``useTaskOrchestrator`` owns UI-facing computed state; this module owns the
// process-level wiring between stores, IPC endpoints, task event listeners and
// the pure ``BatchRunner`` facade.

import {
  listenTaskEvents,
  type TaskEventListeners,
  type UnlistenFn,
} from '@/lib/ipc/events'
import { taskIpc } from '@/lib/ipc/endpoints/task'
import { TASK_ERROR_CODES, TASK_EVENT_NAMES } from '@/types/protocol'
import { normalizeError } from '@/lib/errors/normalize'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'
import { createBatchRunner, type BatchRunner } from '@/services/task/batch-runner'
import { buildTaskRequest } from '@/services/task/request-builder'

let cachedRunner: BatchRunner | null = null
let detachHandle: UnlistenFn | null = null
let attachPromise: Promise<void> | null = null
let runtimeGeneration = 0

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
    resetItemRunState: (id) => mediaRunState.resetItemRunState(id),
    setActiveItem: (id) => mediaStore.setActive(id),
    getActiveItemId: () => mediaStore.activeItemId,
    getBatch: () => taskStore.batch,
    dispatchBatch: (event) => taskStore.dispatchBatch(event),
    setRuntimeIds: (ids) => taskStore.setRuntimeIds(ids),
    setPendingConflict: (descriptor) => taskStore.setPendingConflict(descriptor),
    buildRequest: (item, resumeMode) => buildTaskRequest(item, resumeMode),
  })

  return cachedRunner
}

export function disposeRunner(): void {
  runtimeGeneration += 1
  attachPromise = null
  detachHandle?.()
  detachHandle = null
  cachedRunner = null
}

export function attachTaskListeners(): Promise<void> {
  if (detachHandle) {
    return Promise.resolve()
  }
  if (attachPromise) {
    return attachPromise
  }

  const generation = runtimeGeneration
  const runner = getTaskRunner()
  const whileCurrent = <Payload>(
    listener: (payload: Payload) => void | Promise<void>,
  ): ((payload: Payload) => void | Promise<void>) => {
    return (payload) => {
      if (generation !== runtimeGeneration) {
        return
      }
      return listener(payload)
    }
  }
  const listeners = {
    [TASK_EVENT_NAMES.TaskProgress]: whileCurrent(runner.onProgress),
    [TASK_EVENT_NAMES.TaskLog]: whileCurrent(runner.onLog),
    [TASK_EVENT_NAMES.TaskCompleted]: whileCurrent(runner.onCompleted),
    [TASK_EVENT_NAMES.TaskError]: whileCurrent(runner.onError),
    [TASK_EVENT_NAMES.TaskCancelled]: whileCurrent(runner.onCancelled),
    [TASK_EVENT_NAMES.TaskResumeStatus]: whileCurrent(runner.onResumeStatus),
  } satisfies TaskEventListeners
  const attachment = listenTaskEvents(listeners, (_name, error) => {
    if (generation === runtimeGeneration) {
      useIssueStore().setIssue('task', normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    }
  }).then((detach) => {
    if (generation !== runtimeGeneration) {
      detach()
      return
    }
    detachHandle = detach
  })
  const sharedAttachment = attachment.finally(() => {
    if (attachPromise === sharedAttachment) {
      attachPromise = null
    }
  })
  attachPromise = sharedAttachment
  return sharedAttachment
}
