// IPC events — Tauri 事件订阅桥。

import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { TASK_EVENT_NAMES } from '@/types/protocol'
import type { TaskEventName, TaskEventPayloadMap } from '@/types/protocol'
import { isTauriRuntime } from './client'

export type TaskEventListeners = {
  [Name in TaskEventName]: (payload: TaskEventPayloadMap[Name]) => void | Promise<void>
}

export type TaskEventListenerErrorHandler = (name: TaskEventName, error: unknown) => void

function subscribeTaskEvent<Name extends TaskEventName>(
  name: Name,
  listeners: TaskEventListeners,
  onListenerError: TaskEventListenerErrorHandler,
): Promise<UnlistenFn> {
  return listen<TaskEventPayloadMap[Name]>(name, (event) => {
    try {
      void Promise.resolve(listeners[name](event.payload)).catch((error: unknown) => {
        onListenerError(name, error)
      })
    } catch (error) {
      onListenerError(name, error)
    }
  })
}

export async function listenTaskEvents(
  listeners: TaskEventListeners,
  onListenerError: TaskEventListenerErrorHandler,
): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    return () => {}
  }

  const names = Object.values(TASK_EVENT_NAMES) as TaskEventName[]
  const unlisteners: UnlistenFn[] = []
  try {
    for (const name of names) {
      unlisteners.push(await subscribeTaskEvent(name, listeners, onListenerError))
    }
  } catch (error) {
    detachReverse(unlisteners)
    throw error
  }

  return () => {
    detachReverse(unlisteners)
  }
}

function detachReverse(unlisteners: readonly UnlistenFn[]): void {
  for (let index = unlisteners.length - 1; index >= 0; index -= 1) {
    try {
      unlisteners[index]?.()
    } catch {
      // Continue releasing earlier subscriptions when one detach fails.
    }
  }
}

export type { UnlistenFn }
