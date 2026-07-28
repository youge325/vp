// 领域层 — 批处理与续跑领域模型。

import type { TaskControlKind } from '@/types/protocol'

type ResumeConflictKind =
  | 'final_exists_with_resume'
  | 'final_exists_only'

interface ResumeConflictProgress {
  completedChunks: number
  completedOutputFrames: number
  totalOutputFrames: number
}

export interface ResumeConflictDescriptor {
  kind: ResumeConflictKind
  outputPath: string
  progress: ResumeConflictProgress
}

export type ResumeConflictAction = 'resume' | 'fresh' | 'skip' | 'cancel'

export interface BatchState {
  queue: string[]
  currentId: string | null
  completedCount: number
  isRunning: boolean
  isPaused: boolean
  isCancelling: boolean
  controlPending: TaskControlKind | null
}
