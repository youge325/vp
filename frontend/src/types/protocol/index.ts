// 协议层入口 — re-export Rust 自动生成的 IPC 类型与协议常量。
// 重新生成 generated: cd frontend/src-tauri && cargo test

export * from './events'
export * from './errors'

export type { AnimeConfig } from '@/types/generated/AnimeConfig'
export type { DecodeConfig } from '@/types/generated/DecodeConfig'
export type { EncodeConfig } from '@/types/generated/EncodeConfig'
export type { FilterStep } from '@/types/generated/FilterStep'
export type { InterpolationConfig } from '@/types/generated/InterpolationConfig'
export type { OutputConfig } from '@/types/generated/OutputConfig'
export type { PostprocessConfig } from '@/types/generated/PostprocessConfig'
export type { PreprocessConfig } from '@/types/generated/PreprocessConfig'
export type { RateControlConfig } from '@/types/generated/RateControlConfig'
export type { SuperResolutionConfig } from '@/types/generated/SuperResolutionConfig'
export type { TaskRequest } from '@/types/generated/TaskRequest'
export type { WorkbenchPreset } from '@/types/generated/WorkbenchPreset'
export type { WorkflowConfig } from '@/types/generated/WorkflowConfig'

export type { TaskProgressPayload } from '@/types/generated/TaskProgressPayload'
export type { TaskCompletedPayload } from '@/types/generated/TaskCompletedPayload'
export type { TaskLogPayload } from '@/types/generated/TaskLogPayload'
export type { TaskErrorPayload } from '@/types/generated/TaskErrorPayload'
export type { ResumeStatusPayload } from '@/types/generated/ResumeStatusPayload'
