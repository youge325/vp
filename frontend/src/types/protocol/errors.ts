// 协议层 — Tauri 错误码常量与类型。
// 与 Rust protocol.rs 同步,不要手工编辑常量值。

import type { TaskErrorCode } from '@/types/generated/TaskErrorCode'

export const TASK_ERROR_CODES = {
  MissingFfmpeg: 'missing_ffmpeg',
  MissingModel: 'missing_model',
  MissingTensorBackend: 'missing_tensor_backend',
  Cancelled: 'cancelled',
  ProcessFailed: 'process_failed',
  InvalidInput: 'invalid_input',
  InvalidConfig: 'invalid_config',
  ResumeConflict: 'resume_conflict',
} as const satisfies Record<string, TaskErrorCode>

export type { TaskErrorCode }
