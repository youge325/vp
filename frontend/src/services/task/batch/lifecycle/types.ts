// 批生命周期 — 类型定义(deps + facade 接口)。
//
// Phase 7a — 单独成文件让 queue / finalize / control / common 都能
// 引用同一个 BatchLifecycleDeps,而 index.ts(facade)只承担组装职责。
// 与拆分前的 ``lifecycle.ts`` 公共 API 完全一致,callsite 不需要改动。
//
// Phase 13.1 — 新增 ``getItemRunState`` deps 与 ``getCurrentRunState`` /
// ``getConsoleRunState`` facade 入口。``MediaItem`` 已不再持有 ``taskState``
// / ``issue`` / ``lastOutputPath``,events.ts / control.ts / finalize.ts
// 改读 helpers.getCurrentRunState / getConsoleRunState,facade 把后者
// 一并暴露给 events.ts 调用。

import type { TaskRequest } from '@/types/protocol'
import type { MediaItem, MediaRunState, MediaTaskState, TaskError } from '@/types/domain/media'
import type {
  BatchState,
  ResumeConflictDescriptor,
  ResumeInspectionResult,
  ResumeMode,
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

export interface BatchLifecycle {
  getCurrentItem(): MediaItem | null
  getConsoleItem(): MediaItem | null
  getCurrentRunState(): MediaRunState | null
  getConsoleRunState(): MediaRunState | null
  runNextQueuedItem(): Promise<void>
  launchCurrentItem(item: MediaItem, resumeMode?: ResumeMode): Promise<void>
  finalizeCurrent(state: 'completed' | 'error' | 'cancelled'): Promise<void>
  handleErrored(error: TaskError): Promise<void>
  start(ids: string[]): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  cancel(): Promise<void>
}
