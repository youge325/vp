// pure: no Vue / no Pinia / no Tauri
// 批处理启动前置校验的唯一业务规则入口。
// 输入是简化的"批处理项视图":只关心是否选中、inputPath 是否就绪、
// outputDir 是否填写,而不直接耦合 ``MediaItem`` / Pinia store。让规则
// 与具体 store 形状解耦,未来加新校验项时不会牵动 store schema。

import type { BatchPhase } from '@/types/domain/batch'

interface BatchPreflightItem {
  displayName: string
  inputPath: string | null | undefined
  outputDir: string | null | undefined
}

interface BatchPreflightInput {
  phase: BatchPhase
  selectedItems: BatchPreflightItem[]
}

export function evaluateStartReadiness(input: BatchPreflightInput) {
  if (input.phase !== 'idle') {
    // 活动批次由 phase 单点管控,不展示额外 disabled 原因。
    return { ok: false, reason: null }
  }
  if (input.selectedItems.length === 0) {
    return { ok: false, reason: '请先勾选要处理的素材' }
  }
  if (!input.selectedItems.every((item) => Boolean(item.inputPath))) {
    return { ok: false, reason: '存在素材尚未解析输入路径' }
  }
  const missingOutput = input.selectedItems.find((item) => !item.outputDir)
  if (missingOutput) {
    return {
      ok: false,
      reason: `素材 "${missingOutput.displayName}" 未填输出目录(必填),请在"编码与输出"页选择或填写。`,
    }
  }
  return { ok: true, reason: null }
}
