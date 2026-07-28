import type { ResumeInspectionResult, ResumeMode, TaskRequest } from '@/types/protocol'
import type { BatchState, ResumeConflictDescriptor } from '@/types/domain/batch'
import type { MediaItem, MediaRunState, MediaTaskState, TaskError } from '@/types/domain/media'

export interface TaskCommandPort {
  startTask: (request: TaskRequest) => Promise<void>
  cancelTask: () => Promise<void>
  pauseTask: () => Promise<void>
  resumeTask: () => Promise<void>
  checkResume: (request: TaskRequest) => Promise<ResumeInspectionResult>
}

export interface OutputLocationPort {
  openOutputLocation: (path: string) => Promise<void>
}

export interface MediaItemPort {
  getMediaItem: (id: string) => MediaItem | null
  setActiveItem: (id: string | null) => void
  getActiveItemId: () => string | null
}

export interface MediaRunStatePort {
  getItemRunState: (id: string) => MediaRunState | null
  setItemTaskState: (id: string, state: MediaTaskState) => void
  setItemLastOutputPath: (id: string, path: string) => void
  resetItemRunState: (id: string) => void
}

export interface TaskIssuePort {
  setTaskIssue: (issue: TaskError | null) => void
}

export interface BatchStatePort {
  getBatch: () => BatchState
  setBatch: (partial: Partial<BatchState>) => void
  getRuntimeIds: () => string[]
  setRuntimeIds: (ids: string[]) => void
  setPendingConflict: (descriptor: ResumeConflictDescriptor | null) => void
}

export interface TaskRequestFactory {
  buildRequest: (item: MediaItem, resumeMode?: ResumeMode) => TaskRequest
}

export type BatchRunnerDeps =
  & TaskCommandPort
  & OutputLocationPort
  & MediaItemPort
  & MediaRunStatePort
  & TaskIssuePort
  & BatchStatePort
  & TaskRequestFactory
