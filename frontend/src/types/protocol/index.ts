// 协议层入口 — re-export Rust 自动生成的 IPC 类型与协议常量。
//
// Phase D.4.7 — 全量 re-export 所有 ts-rs 生成的类型,前端代码统一通过
// `@/types/protocol` 引用,不应再出现 `@/types/generated/Xxx` 的深路径
// import。这样:
//   1. 命名空间在一处声明,改名时 grep 一处即可
//   2. ESLint `no-restricted-imports` 可以一行禁掉深引,新人不会绕过 barrel
//
// 重新生成 generated: cd frontend/src-tauri && cargo test

export * from './events'
export * from './errors'

// --- Config payloads ---
export type { DecodeConfig } from '@/types/generated/DecodeConfig'
export type { DecodeMode } from '@/types/generated/DecodeMode'
export type { EncodeConfig } from '@/types/generated/EncodeConfig'
export type { FilterStep } from '@/types/generated/FilterStep'
export type { FilterStepKind } from '@/types/generated/FilterStepKind'
export type { FpsMode } from '@/types/generated/FpsMode'
export type { InterpolationConfig } from '@/types/generated/InterpolationConfig'
export type { OutputConfig } from '@/types/generated/OutputConfig'
export type { PostprocessConfig } from '@/types/generated/PostprocessConfig'
export type { PreprocessConfig } from '@/types/generated/PreprocessConfig'
export type { ProcessOrder } from '@/types/generated/ProcessOrder'
export type { RateControlConfig } from '@/types/generated/RateControlConfig'
export type { RateControlMode } from '@/types/generated/RateControlMode'
export type { SuperResolutionConfig } from '@/types/generated/SuperResolutionConfig'
export type { TaskRequest } from '@/types/generated/TaskRequest'
export type { TensorBackend } from '@/types/generated/TensorBackend'
export type { WorkbenchPreset } from '@/types/generated/WorkbenchPreset'
export type { WorkflowConfig } from '@/types/generated/WorkflowConfig'

// --- Task event payloads ---
export type { ResumeStatusPayload } from '@/types/generated/ResumeStatusPayload'
export type { TaskCancelledPayload } from '@/types/generated/TaskCancelledPayload'
export type { TaskCancelledReason } from '@/types/generated/TaskCancelledReason'
export type { TaskCompletedPayload } from '@/types/generated/TaskCompletedPayload'
export type { TaskErrorPayload } from '@/types/generated/TaskErrorPayload'
export type { TaskEventName } from '@/types/generated/TaskEventName'
export type { TaskLogPayload } from '@/types/generated/TaskLogPayload'
export type { TaskProgressPayload } from '@/types/generated/TaskProgressPayload'
export type { VideoInfo } from '@/types/generated/VideoInfo'

// --- Environment check payloads ---
export type { AlgorithmInfo } from '@/types/generated/AlgorithmInfo'
export type { BackendDeviceSupport } from '@/types/generated/BackendDeviceSupport'
export type { EnvironmentCheckPayload } from '@/types/generated/EnvironmentCheckPayload'
export type { EnvironmentCheckResult } from '@/types/generated/EnvironmentCheckResult'
export type { FfmpegInfo } from '@/types/generated/FfmpegInfo'
export type { GpuInfo } from '@/types/generated/GpuInfo'
export type { TensorEngines } from '@/types/generated/TensorEngines'
