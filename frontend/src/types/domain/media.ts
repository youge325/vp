// 领域层 — 媒体项与任务错误模型。

import type { TaskErrorPayload } from '@/types/generated/TaskErrorPayload'
import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '../protocol'
import type { ResumeStatus } from './batch'
import type { TaskStatus } from './workflow'

/// Phase 6b — `TaskError` 不再单独维护,而是 generated `TaskErrorPayload`
/// 的 type alias。这让 `code` 字段从开放的 `string` 收紧为 14 项
/// `TaskErrorCode` union,避免与 Rust ↔ Python ↔ TS 三层 SSOT 漂移。
/// 旧 `code: string` 形状下,callsite 在 fallback 路径上可以传任意字符串
/// (如 `'pause_failed'`),那是 Phase 6c 一起清理掉的 magic string。
export type TaskError = TaskErrorPayload

export type OperationIssueScope = 'input' | 'encode' | 'output' | 'task' | 'preset'

export interface OperationIssue {
  scope: OperationIssueScope
  error: TaskError
}

/**
 * Per-item snapshot of the workbench preset, taken when the media item is
 * created. Same shape as ``WorkbenchPreset`` but semantically distinct: this
 * is the immutable run-time config locked to one media file, whereas
 * ``WorkbenchPreset`` in the preset store is the mutable draft the user is
 * editing.
 */
export type ItemConfigSnapshot = Pick<
  WorkbenchPreset,
  'decodeConfig' | 'workflowConfig' | 'encodeConfig' | 'outputConfig'
>

export interface VideoInfoResult {
  type: 'info'
  fps: number
  frames: number
  duration: number
  width: number
  height: number
  hasAudio: boolean
  videoCodec: string
}

export interface MediaTaskState {
  status: TaskStatus
  percent: number
  current: number
  total: number
  stage: string
  stageIndex: number
  stageTotal: number
  logs: string[]
  outputPath: string
  processedFrames: number
  timeSeconds: number
  error: TaskError | null
  startedAt: string | null
  finishedAt: string | null
  resumeStatus: ResumeStatus | null
}

export interface MediaItem {
  id: string
  inputPath: string
  displayName: string
  selected: boolean
  inspecting: boolean
  info: VideoInfoResult | null
  issue: TaskError | null
  decodeConfig: DecodeConfig
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
  taskState: MediaTaskState
  lastOutputPath: string
}
