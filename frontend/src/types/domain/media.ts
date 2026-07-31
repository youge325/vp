// 领域层 — 媒体项与任务错误模型。

import type {
  DecodeConfig,
  EncodeConfig,
  OutputConfig,
  ResumeStatusPayload,
  TaskErrorPayload,
  VideoInfo,
  WorkflowConfig,
} from '../protocol'

type TaskStatus = 'idle' | 'running' | 'paused' | 'cancelling' | 'completed' | 'error' | 'cancelled'

export type OperationIssueScope = 'input' | 'encode' | 'task' | 'preset'

export interface OperationIssue {
  scope: OperationIssueScope
  error: TaskErrorPayload
}

// 只保留视图实际消费的任务投影;批次级进度由 ``BatchState`` 管理。
export interface MediaTaskState {
  status: TaskStatus
  logs: string[]
  resumeStatus: ResumeStatusPayload | null
}

export interface MediaItem {
  id: string
  inputPath: string
  displayName: string
  selected: boolean
  inspecting: boolean
  info: VideoInfo | null
  decodeConfig: DecodeConfig
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
}

// 运行时状态与媒体实体分离,避免任务事件持续改写列表实体。
export interface MediaRunState {
  taskState: MediaTaskState
  lastOutputPath: string
}
