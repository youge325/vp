// IPC events — Tauri 事件订阅桥。

import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { TASK_EVENT_NAMES } from '@/types/protocol'
import type {
  ResumeStatusPayload,
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/protocol'
import type { TaskError } from '@/types/domain/media'
import { isTauriRuntime } from './client'

interface TaskEventHandlers {
  onProgress: (payload: TaskProgressPayload) => void
  onLog: (payload: TaskLogPayload) => void
  onCompleted: (payload: TaskCompletedPayload) => void
  onError: (payload: TaskError) => void
  onCancelled: (payload: TaskCancelledPayload | null) => void
  onResumeStatus?: (payload: ResumeStatusPayload) => void
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
    listen<TaskCancelledPayload | null>(TASK_EVENT_NAMES.TaskCancelled, (event) =>
      handlers.onCancelled(event.payload ?? null),
    ),
    listen<ResumeStatusPayload>(TASK_EVENT_NAMES.TaskResumeStatus, (event) =>
      handlers.onResumeStatus?.(event.payload),
    ),
  ])

  return () => {
    for (const unlisten of unlisteners) {
      unlisten()
    }
  }
}

export type { UnlistenFn }
