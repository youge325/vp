// 协议层 — Tauri 事件常量与名称类型。
// 与 Rust protocol.rs 同步,不要手工编辑常量值。

import type { TaskEventName } from '@/types/generated/TaskEventName'

export const TASK_EVENT_NAMES = {
  TaskProgress: 'task-progress',
  TaskCompleted: 'task-completed',
  TaskError: 'task-error',
  TaskCancelled: 'task-cancelled',
  TaskLog: 'task-log',
  TaskResumeStatus: 'task-resume-status',
} as const satisfies Record<string, TaskEventName>

export const TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'

export type { TaskEventName }
