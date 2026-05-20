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

export type OperationIssueScope = 'input' | 'encode' | 'task' | 'preset'

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

// Phase 16 — ``error: TaskError | null`` 字段移除。Phase 13.1 拆分后这个
// 字段在视图 / batch 任何地方都没有 reader,reducer 链路写入是纯 dead
// write;真正展示任务错误的链路是 ``useIssueStore.setIssue('task', …)``
// (见 [[finalize.ts]] ``handleErrored`` 与 [[batch/events.ts]]
// ``onCancelled`` 的 stalled 分支)。
//
// Phase 17 — 大幅瘦身:删 11 个 dead 字段(percent / current / total /
// stage / stageIndex / stageTotal / processedFrames / timeSeconds /
// outputPath / startedAt / finishedAt)。这些在视图 / component /
// composable 中 **零 reader**(grep 验证):reducer 之间仅做 transfer,
// spec 测试有断言但实际不驱动 UI。视图侧只读 ``status / logs /
// resumeStatus`` 三个字段,batch 粒度的进度条用 ``batch.completedCount /
// batchTotal``(见 [[TaskConsole.vue]] L18-22)。
export interface MediaTaskState {
  status: TaskStatus
  logs: string[]
  resumeStatus: ResumeStatus | null
}

export interface MediaItem {
  id: string
  inputPath: string
  displayName: string
  selected: boolean
  inspecting: boolean
  info: VideoInfoResult | null
  decodeConfig: DecodeConfig
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
}

// Phase 13.1 — 运行时投影,从 ``MediaItem`` 拆出到独立的
// ``useMediaRunState`` store。``MediaItem`` 现在只描述列表实体(身份 +
// 配置),不再承载会跨多个写入者(batch lifecycle / IPC 事件)持续刷新
// 的字段。
//
// Phase 16 — ``issue: TaskError | null`` 字段移除。Phase 14 后唯一 writer
// 是 [[finalize.ts]] ``handleErrored``,但视图侧没有任何 reader 读
// ``mediaRunState.getByItemId(id)?.issue``。任务错误现在统一写入
// ``useIssueStore.setIssue('task', …)``,IssueBanner 通过
// ``useOperationIssue('task')`` 直接消费。
export interface MediaRunState {
  taskState: MediaTaskState
  lastOutputPath: string
}
