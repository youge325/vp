// IPC 协议层入口 — barrel re-export。

export { isTauriRuntime, safeInvoke } from './client'
export { listenTaskEvents } from './events'
export type { TaskEventHandlers, UnlistenFn } from './events'

export { envIpc } from './endpoints/env'
export { mediaIpc } from './endpoints/media'
export { presetIpc } from './endpoints/preset'
export { taskIpc } from './endpoints/task'
