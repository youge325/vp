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

export type BatchPhase = 'idle' | 'running' | 'paused' | 'cancelling'

type BatchRuntime = Readonly<{
  runtimeIds: readonly string[]
}>

type IdleBatchState = BatchRuntime & Readonly<{
  phase: 'idle'
  queue: readonly []
  currentId: null
  controlPending: null
}>

type RunningBatchState = BatchRuntime & Readonly<{
  phase: 'running'
  queue: readonly string[]
  currentId: string | null
  controlPending: Extract<TaskControlKind, 'pause'> | null
}>

type PausedBatchState = BatchRuntime & Readonly<{
  phase: 'paused'
  queue: readonly string[]
  currentId: string | null
  controlPending: Extract<TaskControlKind, 'resume'> | null
}>

type CancellingBatchState = BatchRuntime & Readonly<{
  phase: 'cancelling'
  queue: readonly []
  currentId: string | null
  controlPending: Extract<TaskControlKind, 'cancel'> | null
}>

export type BatchState =
  | IdleBatchState
  | RunningBatchState
  | PausedBatchState
  | CancellingBatchState

export type BatchEvent =
  | { readonly type: 'started'; readonly ids: readonly string[] }
  | {
    readonly type: 'queue-advanced'
    readonly currentId: string
    readonly remaining: readonly string[]
  }
  | { readonly type: 'queue-cleared' }
  | { readonly type: 'item-finalized' }
  | { readonly type: 'control-requested'; readonly kind: TaskControlKind }
  | { readonly type: 'control-succeeded'; readonly kind: TaskControlKind }
  | {
    readonly type: 'control-failed'
    readonly kind: TaskControlKind
    readonly snapshot: BatchState
  }
