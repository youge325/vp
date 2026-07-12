// 批生命周期依赖定义。
//
// Phase 7a — 单独成文件让 queue / finalize / control / common 都能
// 引用同一个 BatchLifecycleDeps,而 index.ts(facade)负责组装并从返回值
// 推导 BatchLifecycle 类型。
//
// Phase 13.1 — 新增 ``getItemRunState`` deps 与 ``getCurrentRunState`` /
// ``getConsoleRunState`` facade 入口。``MediaItem`` 已不再持有 ``taskState``
// / ``issue`` / ``lastOutputPath``,events.ts / control.ts / finalize.ts
// 改读 helpers.getCurrentRunState / getConsoleRunState,facade 把后者
// 一并暴露给 events.ts 调用。

import type { ResumeInspectionResult, ResumeMode, TaskRequest } from '@/types/protocol'
import type { MediaItem, MediaRunState, MediaTaskState, TaskError } from '@/types/domain/media'
import type {
  BatchState,
  ResumeConflictDescriptor,
} from '@/types/domain/batch'

export interface BatchLifecycleDeps {
  startTask: (req: TaskRequest) => Promise<void>
  cancelTask: () => Promise<void>
  pauseTask: () => Promise<void>
  resumeTask: () => Promise<void>
  checkResume: (req: TaskRequest) => Promise<ResumeInspectionResult>
  openOutputLocation: (path: string) => Promise<void>

  getMediaItem: (id: string) => MediaItem | null
  getItemRunState: (id: string) => MediaRunState | null
  setItemTaskState: (id: string, state: MediaTaskState) => void
  setTaskIssue: (issue: TaskError | null) => void
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
