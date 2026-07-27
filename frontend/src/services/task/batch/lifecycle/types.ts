// Dependencies shared by the batch queue, control and finalization modules.

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
  resetItemRunState: (id: string) => void
  resetItemsRunState: (ids: Set<string>) => void
  setActiveItem: (id: string | null) => void
  getActiveItemId: () => string | null

  getBatch: () => BatchState
  setBatch: (partial: Partial<BatchState>) => void
  getRuntimeIds: () => string[]
  setRuntimeIds: (ids: string[]) => void
  setPendingConflict: (descriptor: ResumeConflictDescriptor | null) => void

  buildRequest: (item: MediaItem, resumeMode?: ResumeMode) => TaskRequest
}
