// IPC events — Tauri 事件订阅桥。

import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { TASK_EVENT_NAMES } from '@/types/protocol'
import type { TaskEventName, TaskEventPayloadMap } from '@/types/protocol'
import { isTauriRuntime } from './client'

export type TaskEventListeners = {
  [Name in TaskEventName]: (payload: TaskEventPayloadMap[Name]) => void | Promise<void>
}

function subscribeTaskEvent<Name extends TaskEventName>(
  name: Name,
  listeners: TaskEventListeners,
): Promise<UnlistenFn> {
  return listen<TaskEventPayloadMap[Name]>(name, (event) => {
    void listeners[name](event.payload)
  })
}

export async function listenTaskEvents(listeners: TaskEventListeners): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    return () => {
      void listeners
    }
  }

  const names = Object.values(TASK_EVENT_NAMES) as TaskEventName[]
  const unlisteners = await Promise.all(names.map((name) => subscribeTaskEvent(name, listeners)))

  return () => {
    for (const unlisten of unlisteners) {
      unlisten()
    }
  }
}

export type { UnlistenFn }
