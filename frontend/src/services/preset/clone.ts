// pure: no Vue / no Pinia / no Tauri
// 配置克隆 — 单一深拷贝实现 ``clone<T>``,所有具名 helper 都委托给它。
//
// 实现细节:这里继续走 ``JSON.parse(JSON.stringify(...))`` 而不是
// ``structuredClone``。原因:本工具的实际输入是 Pinia store 中的
// reactive proxy 对象(``presetStore.draftPreset.*``),``structuredClone``
// 无法克隆 Proxy,在 vitest happy-dom 环境下会直接抛
// ``DOMException: #<Object> could not be cloned``。JSON 序列化路径会
// 把所有 proxy / reactive 包装层解构掉,落地为 plain object,完全够用。
// 我们的 Config 都是 ``serde``-friendly 的纯数据,无 Date / Map / undefined,
// 所以"JSON 丢失的语义"不影响实际使用。

import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '@/types/protocol'

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export const cloneWorkflowConfig = (config: WorkflowConfig): WorkflowConfig => clone(config)
export const cloneEncodeConfig = (config: EncodeConfig): EncodeConfig => clone(config)
export const cloneDecodeConfig = (config: DecodeConfig): DecodeConfig => clone(config)
export const cloneOutputConfig = (config: OutputConfig): OutputConfig => clone(config)
export const cloneWorkbenchPreset = (config: WorkbenchPreset): WorkbenchPreset => clone(config)
