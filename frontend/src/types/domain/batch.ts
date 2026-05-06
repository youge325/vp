// 领域层 — 批处理与续跑领域模型。

export interface ResumeStatus {
  resumed: boolean
  completedChunks: number
  completedOutputFrames: number
  startSourceFrame: number
  totalOutputFrames: number
}

export type ResumeMode = 'auto' | 'force-fresh' | 'force-resume'

export interface ResumeInspectionResult {
  type: 'resume_inspection'
  pipeline_kind: 'streaming' | 'format_conversion'
  outputPath: string
  inputPath: string
  finalExists: boolean
  sidecarExists: boolean
  signatureMatch: boolean
  completedChunks: number
  completedOutputFrames: number
  nextSourceFrame: number
  totalOutputFrames: number
}

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
