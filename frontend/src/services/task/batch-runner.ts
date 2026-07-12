// Pure: no Vue / no Pinia / no Tauri.
// 批处理状态机的 facade — 把 [[lifecycle]]/[[conflict]]/[[events]] 三个子模块装配为单一 BatchRunner 实例。
// 调度顺序: start → checkResume → (conflict ? pending : launch) → 事件回调 → finalize → next。
//
// 这一层故意保持薄,只负责复用类型与组合内部 API:旧导入路径
// (``@/services/task/batch-runner``) 保持不变,以便测试与编排层无感知。

import { createBatchLifecycle } from './batch/lifecycle'
import type { BatchLifecycleDeps } from './batch/lifecycle/types'
import { createConflictResolver } from './batch/conflict'
import { createEventHandlers } from './batch/events'

export function createBatchRunner(deps: BatchLifecycleDeps) {
  const lifecycle = createBatchLifecycle(deps)
  const conflict = createConflictResolver(deps, lifecycle)
  const events = createEventHandlers(deps, lifecycle, conflict)

  return {
    start: lifecycle.start,
    pause: lifecycle.pause,
    resume: lifecycle.resume,
    cancel: lifecycle.cancel,
    resolveConflict: conflict.resolveConflict,
    onProgress: events.onProgress,
    onLog: events.onLog,
    onCompleted: events.onCompleted,
    onError: events.onError,
    onCancelled: events.onCancelled,
    onResumeStatus: events.onResumeStatus,
  }
}

export type BatchRunner = ReturnType<typeof createBatchRunner>
