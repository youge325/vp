// pure: no Vue / no Pinia / no Tauri
// 配置克隆 — 通过 JSON 序列化 deep clone,避免响应式对象副作用泄漏。

import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '@/types/protocol'

export function cloneWorkflowConfig(config: WorkflowConfig): WorkflowConfig {
  return JSON.parse(JSON.stringify(config)) as WorkflowConfig
}

export function cloneEncodeConfig(config: EncodeConfig): EncodeConfig {
  return JSON.parse(JSON.stringify(config)) as EncodeConfig
}

export function cloneDecodeConfig(config: DecodeConfig): DecodeConfig {
  return JSON.parse(JSON.stringify(config)) as DecodeConfig
}

export function cloneOutputConfig(config: OutputConfig): OutputConfig {
  return JSON.parse(JSON.stringify(config)) as OutputConfig
}

export function cloneWorkbenchPreset(config: WorkbenchPreset): WorkbenchPreset {
  return JSON.parse(JSON.stringify(config)) as WorkbenchPreset
}
