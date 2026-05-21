// pure: no Vue / no Pinia / no Tauri
// Phase A — 批处理启动前置校验。原本散落在 ``useTaskOrchestrator`` 的
// ``canStartBatch`` / ``cannotStartReason`` 两个 computed 是纯业务规则
// (无响应式以外的副作用),与 ``services/task`` 同层职责重叠。下沉到
// 这里后,composable 只做 ``computed(() => evaluateStartReadiness(...))``
// 投影,view / form / orchestrator 三层不再各自重复推 disabled 原因。
//
// 输入是简化的"批处理项视图":只关心是否选中、inputPath 是否就绪、
// outputDir 是否填写,而不直接耦合 ``MediaItem`` / Pinia store。让规则
// 与具体 store 形状解耦,未来加新校验项时不会牵动 store schema。

export interface BatchPreflightItem {
  displayName: string
  inputPath: string | null | undefined
  outputDir: string | null | undefined
}

export interface BatchPreflightInput {
  isRunning: boolean
  selectedItems: BatchPreflightItem[]
}

export interface BatchPreflightVerdict {
  ok: boolean
  reason: string | null
}

export function evaluateStartReadiness(input: BatchPreflightInput): BatchPreflightVerdict {
  if (input.isRunning) {
    // 运行中按钮被 isRunning 自己管控,不展示额外 disabled 原因。
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
