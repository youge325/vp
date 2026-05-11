// 领域层 — 媒体项与任务错误模型。

import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '../protocol'
import type { ResumeStatus } from './batch'
import type { TaskStatus } from './workflow'

export interface TaskError {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export type OperationIssueScope = 'input' | 'encode' | 'output' | 'task'

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
