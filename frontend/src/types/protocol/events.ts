// 协议层 — Tauri 事件常量与名称类型。
// 与 Rust protocol.rs::TaskEventName 同步。
//
// 编译期保证 TASK_EVENT_NAMES 的 values 集合 等于 generated TaskEventName 全集:
// - 如果 Rust 增加了一个新的 TaskEventName variant,ts-rs 重新生成 TaskEventName.ts
//   → 类型 `_VariantsCovered` 不再为 true → tsc 报错,前端必须补全这个 const 对象
// - 如果 TASK_EVENT_NAMES 的某个 value 不是合法 TaskEventName(typo)
//   → `as const satisfies` 直接报错
// 这避免了 strum / 额外 dump-bin / build script 的依赖,在 npm run build / vitest 都会触发检查。

import type { TaskEventName } from '@/types/generated/TaskEventName'

export const TASK_EVENT_NAMES = {
  TaskProgress: 'task-progress',
  TaskCompleted: 'task-completed',
  TaskError: 'task-error',
  TaskCancelled: 'task-cancelled',
  TaskLog: 'task-log',
  TaskResumeStatus: 'task-resume-status',
} as const satisfies Record<string, TaskEventName>

// 编译期校验: 必须覆盖 TaskEventName 的所有可能字符串。
// 如果新增了 Rust variant 但忘记补这里,以下类型会变成 never → 整个文件 type check 失败。
type _ValuesOf<T extends Record<string, unknown>> = T[keyof T]
type _VariantsCovered = TaskEventName extends _ValuesOf<typeof TASK_EVENT_NAMES> ? true : never
const _COVERAGE_CHECK: _VariantsCovered = true
void _COVERAGE_CHECK

export const TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'
