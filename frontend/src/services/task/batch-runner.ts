// Pure: no Vue / no Pinia / no Tauri.
// 批处理状态机的 facade — 把 [[lifecycle]]/[[conflict]]/[[events]] 三个子模块装配为单一 BatchRunner 实例。
// 调度顺序: start → checkResume → (conflict ? pending : launch) → 事件回调 → finalize → next。
//
// 这一层故意保持薄,只负责复用类型与组合内部 API:旧导入路径
// (``@/services/task/batch-runner``) 保持不变,以便测试与编排层无感知。

import type {
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
  TaskRequest,
} from '@/types/protocol'
import type { MediaItem, MediaTaskState, TaskError } from '@/types/domain/media'
import type {
  BatchState,
  ResumeConflictAction,
  ResumeConflictDescriptor,
  ResumeInspectionResult,
  ResumeMode,
  ResumeStatus,
} from '@/types/domain/batch'
import { createBatchLifecycle } from './batch/lifecycle'
import { createConflictResolver } from './batch/conflict'
import { createEventHandlers } from './batch/events'

export interface BatchRunnerDeps {
  startTask: (req: TaskRequest) => Promise<void>
  cancelTask: () => Promise<void>
  pauseTask: () => Promise<void>
  resumeTask: () => Promise<void>
  checkResume: (req: TaskRequest) => Promise<ResumeInspectionResult>
  openOutputLocation: (path: string) => Promise<void>

  getMediaItem: (id: string) => MediaItem | null
  setItemTaskState: (id: string, state: MediaTaskState) => void
  setItemIssue: (id: string, issue: TaskError | null) => void
  setItemLastOutputPath: (id: string, path: string) => void
  resetItemRunState: (id: string, preserveLogs?: boolean) => void
  resetItemsRunState: (ids: Set<string>, preserveLogs?: boolean) => void
  setActiveItem: (id: string | null) => void
  getActiveItemId: () => string | null

  getBatch: () => BatchState
  setBatch: (partial: Partial<BatchState>) => void
  getRuntimeIds: () => string[]
  setRuntimeIds: (ids: string[]) => void
  setPendingConflict: (descriptor: ResumeConflictDescriptor | null) => void

  buildRequest: (item: MediaItem, resumeMode?: ResumeMode) => TaskRequest
}

export interface BatchRunner {
  start(ids: string[]): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  cancel(): Promise<void>
  resolveConflict(action: ResumeConflictAction): Promise<void>
  onProgress(payload: TaskProgressPayload): void
  onLog(payload: TaskLogPayload): void
  onCompleted(payload: TaskCompletedPayload): Promise<void>
  onError(error: TaskError): Promise<void>
  onCancelled(payload?: TaskCancelledPayload | null): Promise<void>
  onResumeStatus(payload: ResumeStatus): void
}

export function createBatchRunner(deps: BatchRunnerDeps): BatchRunner {
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
