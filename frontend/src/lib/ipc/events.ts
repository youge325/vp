// IPC events — Tauri 事件订阅桥。

import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { TASK_EVENT_NAMES } from '@/types/protocol'
import type {
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/protocol'
import type { ResumeStatus } from '@/types/domain/batch'
import type { TaskError } from '@/types/domain/media'
import { isTauriRuntime } from './client'

export interface TaskEventHandlers {
  onProgress: (payload: TaskProgressPayload) => void
  onLog: (payload: TaskLogPayload) => void
  onCompleted: (payload: TaskCompletedPayload) => void
  onError: (payload: TaskError) => void
  onCancelled: () => void
  onResumeStatus?: (payload: ResumeStatus) => void
}

export async function listenTaskEvents(handlers: TaskEventHandlers): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    return () => {
      void handlers
    }
  }

  const unlisteners = await Promise.all([
    listen<TaskProgressPayload>(TASK_EVENT_NAMES.TaskProgress, (event) => handlers.onProgress(event.payload)),
    listen<TaskLogPayload>(TASK_EVENT_NAMES.TaskLog, (event) => handlers.onLog(event.payload)),
    listen<TaskCompletedPayload>(TASK_EVENT_NAMES.TaskCompleted, (event) => handlers.onCompleted(event.payload)),
    listen<TaskError>(TASK_EVENT_NAMES.TaskError, (event) => handlers.onError(event.payload)),
    listen(TASK_EVENT_NAMES.TaskCancelled, () => handlers.onCancelled()),
    listen<ResumeStatus>(TASK_EVENT_NAMES.TaskResumeStatus, (event) => handlers.onResumeStatus?.(event.payload)),
  ])

  return () => {
    for (const unlisten of unlisteners) {
      unlisten()
    }
  }
}

export type { UnlistenFn }
