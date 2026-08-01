import type {
  ResumeInspectionResult,
  ResumeMode,
  ResumeStatusPayload,
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
  TaskRequest,
  TaskErrorPayload,
} from '@/types/protocol'
import type { BatchEvent, BatchState, ResumeConflictDescriptor } from '@/types/domain/batch'
import type {
  MediaItem,
  MediaRunState,
  MediaTaskState,
} from '@/types/domain/media'
import type { ResumeConflictAction } from '@/types/domain/batch'
import type { TaskContext } from '../../task-context'

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
  setTaskIssue: (issue: TaskErrorPayload | null) => void
}

export interface BatchStatePort {
  getBatch: () => BatchState
  dispatchBatch: (event: BatchEvent) => void
  setRuntimeIds: (ids: string[]) => void
  setPendingConflict: (descriptor: ResumeConflictDescriptor | null) => void
}

export interface TaskRequestFactory {
  buildRequest: (item: MediaItem, resumeMode?: ResumeMode) => TaskRequest
}

export interface TaskContextCapability {
  getCurrentTaskContext: () => TaskContext
}

export interface ConsoleTaskContextCapability {
  getConsoleTaskContext: () => TaskContext
}

export interface QueueContinuation {
  runNextQueuedItem: () => Promise<void>
  launchCurrentItem: (item: MediaItem, resumeMode?: ResumeMode) => Promise<void>
}

export interface QueueOperations {
  runNextQueuedItem: () => Promise<void>
  launchCurrentItem: (item: MediaItem, resumeMode?: ResumeMode) => Promise<void>
  start: (ids: string[]) => Promise<void>
}

export interface ErrorFinalizationCapability {
  handleErrored: (error: TaskErrorPayload) => Promise<void>
}

export interface FinalizationCapability {
  handleErrored: (error: TaskErrorPayload) => Promise<void>
  finalizeCurrent: (state: 'completed' | 'error' | 'cancelled') => Promise<void>
}

export interface ConflictCapability {
  resolveConflict: (action: ResumeConflictAction) => Promise<void>
  tryStashFromError: (error: TaskErrorPayload) => boolean
}

export interface ControlOperations {
  pause: () => Promise<void>
  resume: () => Promise<void>
  cancel: () => Promise<void>
}

export interface BatchRunner {
  start: (ids: string[]) => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
  cancel: () => Promise<void>
  resolveConflict: (action: ResumeConflictAction) => Promise<void>
  onProgress: (payload: TaskProgressPayload) => void
  onLog: (payload: TaskLogPayload) => void
  onCompleted: (payload: TaskCompletedPayload) => Promise<void>
  onError: (error: TaskErrorPayload) => Promise<void>
  onCancelled: (payload: TaskCancelledPayload) => Promise<void>
  onResumeStatus: (payload: ResumeStatusPayload) => void
}

export type BatchRunnerDeps =
  & TaskCommandPort
  & OutputLocationPort
  & MediaItemPort
  & MediaRunStatePort
  & TaskIssuePort
  & BatchStatePort
  & TaskRequestFactory
