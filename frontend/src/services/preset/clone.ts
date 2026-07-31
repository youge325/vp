// pure: no Vue / no Pinia / no Tauri
// 配置克隆 — 仅接受预设及其四个配置 section。
//
// 实现细节:这里继续走 ``JSON.parse(JSON.stringify(...))`` 而不是
// ``structuredClone``。原因:本工具的实际输入是 Pinia store 中的
// reactive proxy 对象(``presetStore.draftPreset.*``),``structuredClone``
// 无法克隆 Proxy,在 vitest happy-dom 环境下会直接抛
// ``DOMException: #<Object> could not be cloned``。JSON 序列化路径会
// 把所有 proxy / reactive 包装层解构掉,落地为 plain object,完全够用。
// 我们的 Config 都是 ``serde``-friendly 的纯数据,无 Date / Map / undefined,
// 所以"JSON 丢失的语义"不影响实际使用。

import type { WorkbenchPreset } from '@/types/protocol'

type PresetData =
  | WorkbenchPreset
  | WorkbenchPreset['decodeConfig']
  | WorkbenchPreset['workflowConfig']
  | WorkbenchPreset['encodeConfig']
  | WorkbenchPreset['outputConfig']

export function clonePresetData<T extends PresetData>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
