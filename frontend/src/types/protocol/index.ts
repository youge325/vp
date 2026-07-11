// 协议层入口 — re-export Rust 自动生成的 IPC 类型与协议常量。
//
// 只 re-export 前端实际消费的 ts-rs 类型；应用代码统一通过
// `@/types/protocol` 引用，不直接依赖 generated 深路径。
//
// 重新生成 generated: cd frontend/src-tauri && cargo test

export * from './events'
export * from './errors'

// --- Config payloads ---
export type { DecodeConfig } from '@/types/generated/DecodeConfig'
export type { EncodeConfig } from '@/types/generated/EncodeConfig'
export type { FilterStep } from '@/types/generated/FilterStep'
export type { FilterStepKind } from '@/types/generated/FilterStepKind'
export type { FpsMode } from '@/types/generated/FpsMode'
export type { OutputConfig } from '@/types/generated/OutputConfig'
export type { ProcessOrder } from '@/types/generated/ProcessOrder'
export type { RateControlMode } from '@/types/generated/RateControlMode'
export type { TaskRequest } from '@/types/generated/TaskRequest'
export type { TensorBackend } from '@/types/generated/TensorBackend'
export type { WorkbenchPreset } from '@/types/generated/WorkbenchPreset'
export type { WorkflowConfig } from '@/types/generated/WorkflowConfig'

// --- Task event payloads ---
export type { ResumeStatusPayload } from '@/types/generated/ResumeStatusPayload'
export type { TaskCancelledPayload } from '@/types/generated/TaskCancelledPayload'
export type { TaskCompletedPayload } from '@/types/generated/TaskCompletedPayload'
export type { TaskErrorPayload } from '@/types/generated/TaskErrorPayload'
export type { TaskLogPayload } from '@/types/generated/TaskLogPayload'
export type { TaskProgressPayload } from '@/types/generated/TaskProgressPayload'
export type { VideoInfo } from '@/types/generated/VideoInfo'

// --- Environment check payloads ---
export type { AlgorithmInfo } from '@/types/generated/AlgorithmInfo'
export type { CapabilityOptionSpec } from '@/types/generated/CapabilityOptionSpec'
export type { CodecProfileSpec } from '@/types/generated/CodecProfileSpec'
export type { EnvironmentCheckPayload } from '@/types/generated/EnvironmentCheckPayload'
export type { EnvironmentCheckResult } from '@/types/generated/EnvironmentCheckResult'
export type { EnvironmentCheckSource } from '@/types/generated/EnvironmentCheckSource'
export type { HardwareDeviceOptionSpec } from '@/types/generated/HardwareDeviceOptionSpec'
export type { InferenceEngine } from '@/types/generated/InferenceEngine'
export type { ModelVariantInfo } from '@/types/generated/ModelVariantInfo'
export type { RateControlModeSpec } from '@/types/generated/RateControlModeSpec'

import type { CapabilityChoice } from '@/types/generated/CapabilityChoice'
import type { CodecProfileFamily } from '@/types/generated/CodecProfileFamily'
import type { CodecProfileSpec } from '@/types/generated/CodecProfileSpec'

export type CapabilityValue = CapabilityChoice['value']
export type CodecFamily = CodecProfileFamily
export type DecoderProfileSpec = CodecProfileSpec
export type EncoderProfileSpec = CodecProfileSpec
