// 协议层入口 — re-export 中立 JSON Schema 生成的 IPC 类型与协议常量。
//
// 只 re-export 前端实际消费的类型；应用代码统一通过
// `@/types/protocol` 引用，不直接依赖 generated 深路径。

export * from './events'
export * from './errors'
export { APPLICATION_DEFAULTS } from '../generated/application-defaults'
export { FILTER_FIELD_CONSTRAINTS } from '../generated/filter-constraints'

export type {
  AlgorithmInfo,
  CapabilityOptionSpec,
  CodecProfileFamily,
  CodecProfileSpec,
  DecodeConfig,
  EncodeConfig,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  EnvironmentCheckSource,
  FilterStep,
  FilterStepKind,
  FpsMode,
  HardwareDeviceOptionSpec,
  InferenceEngine,
  ModelLicenseInfo,
  ModelVariantInfo,
  OutputConfig,
  ProcessOrder,
  RateControlMode,
  RateControlModeSpec,
  ResumeInspectionResult,
  ResumeMode,
  ResumeStatusPayload,
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskControlKind,
  TaskErrorPayload,
  TaskLogPayload,
  TaskProgressPayload,
  TaskRequest,
  TensorBackend,
  VideoInfo,
  WorkbenchPreset,
  WorkflowConfig,
} from '@/types/generated/contracts'

import type {
  CapabilityChoice,
} from '@/types/generated/contracts'

export type CapabilityValue = CapabilityChoice['value']
