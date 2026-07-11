// 领域层 — 批处理与续跑领域模型。

import type { ResumeInspectionResult } from '@/types/protocol'

export type ResumeConflictKind =
  | 'resume_available'
  | 'final_exists_with_resume'
  | 'final_exists_only'

export interface ResumeConflictDescriptor {
  itemId: string
  kind: ResumeConflictKind
  outputPath: string
  inspection: ResumeInspectionResult
}

export type ResumeConflictAction = 'resume' | 'fresh' | 'skip' | 'cancel'

export interface BatchState {
  queue: string[]
  currentId: string | null
  completedCount: number
  failedCount: number
  isRunning: boolean
  isPaused: boolean
  isCancelling: boolean
}
