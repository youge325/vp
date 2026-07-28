// IPC events — Tauri 事件订阅桥。

import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { TASK_EVENT_NAMES } from '@/types/protocol'
import type { TaskEventPayloadMap } from '@/types/protocol'
import { isTauriRuntime } from './client'

interface TaskEventHandlers {
  onProgress: (payload: TaskEventPayloadMap['task-progress']) => void
  onLog: (payload: TaskEventPayloadMap['task-log']) => void
  onCompleted: (payload: TaskEventPayloadMap['task-completed']) => void
  onError: (payload: TaskEventPayloadMap['task-error']) => void
  onCancelled: (payload: TaskEventPayloadMap['task-cancelled']) => void
  onResumeStatus: (payload: TaskEventPayloadMap['task-resume-status']) => void
}

export async function listenTaskEvents(handlers: TaskEventHandlers): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    return () => {
      void handlers
    }
  }

  const unlisteners = await Promise.all([
    listen<TaskEventPayloadMap['task-progress']>(TASK_EVENT_NAMES.TaskProgress, (event) =>
      handlers.onProgress(event.payload),
    ),
    listen<TaskEventPayloadMap['task-log']>(TASK_EVENT_NAMES.TaskLog, (event) =>
      handlers.onLog(event.payload),
    ),
    listen<TaskEventPayloadMap['task-completed']>(TASK_EVENT_NAMES.TaskCompleted, (event) =>
      handlers.onCompleted(event.payload),
    ),
    listen<TaskEventPayloadMap['task-error']>(TASK_EVENT_NAMES.TaskError, (event) =>
      handlers.onError(event.payload),
    ),
    listen<TaskEventPayloadMap['task-cancelled']>(TASK_EVENT_NAMES.TaskCancelled, (event) =>
      handlers.onCancelled(event.payload),
    ),
    listen<TaskEventPayloadMap['task-resume-status']>(TASK_EVENT_NAMES.TaskResumeStatus, (event) =>
      handlers.onResumeStatus(event.payload),
    ),
  ])

  return () => {
    for (const unlisten of unlisteners) {
      unlisten()
    }
  }
}

export type { UnlistenFn }
