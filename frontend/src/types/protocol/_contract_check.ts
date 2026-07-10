// Build-time cross-layer contract checks (Phase 4.3).
//
// 用 TypeScript `satisfies` 操作符在 `pnpm tsc --noEmit` 阶段对几个核心 IPC
// 类型做"形状反向锁"。当 ts-rs 在 `cd frontend/src-tauri && cargo test`
// 期间重新生成 `types/generated/*.ts` 时,如果某个字段被改名、删除、改类型,
// 或新增 required 字段,本文件中对应的 satisfies 断言会立即编译失败,
// 把契约漂移挡在编译阶段,而不是等到运行时再从 IPC payload 收到的形状里
// 反推出来。
//
// 该文件与 `scripts/check_error_code_drift.py` 互补:
//   - drift.py 在 git pre-commit / CI 上检查 Rust ↔ Python ↔ TS 在
//     *string-enum 字面量*(TaskErrorCode 等)层面对齐
//   - 本文件检查 *TS 端的结构字段*没有偏离前端代码所依赖的形状
//
// 文件名以下划线开头,提醒读者它不是常规协议入口,不应被 `index.ts`
// re-export;也不期望被任何运行时代码 import。Tsc 会通过
// `tsconfig.app.json` 的 `include: src/**/*.ts` 把它纳入类型检查。

import type {
  EnvironmentCheckPayload,
  ResumeStatusPayload,
  TaskErrorCode,
  TaskErrorPayload,
  TaskProgressPayload,
  TaskRequest,
  WorkbenchPreset,
} from './index'

// --- TaskRequest --------------------------------------------------------
// 前端通过 `safeInvoke('start_task', { request })` 跨层传 TaskRequest。
// 字段消失或类型改变都会让下面的常量断言编译失败。
const _TASK_REQUEST_CONTRACT = {
  inputPath: '',
  decodeConfig: {} as TaskRequest['decodeConfig'],
  workflowConfig: {} as TaskRequest['workflowConfig'],
  encodeConfig: {} as TaskRequest['encodeConfig'],
  outputConfig: {} as TaskRequest['outputConfig'],
} satisfies TaskRequest

// --- WorkbenchPreset ---------------------------------------------------
// preset 持久化 / 导入导出走这条形状,需要与 TaskRequest 子集严格对齐。
const _WORKBENCH_PRESET_CONTRACT = {
  decodeConfig: {} as WorkbenchPreset['decodeConfig'],
  workflowConfig: {} as WorkbenchPreset['workflowConfig'],
  encodeConfig: {} as WorkbenchPreset['encodeConfig'],
  outputConfig: {} as WorkbenchPreset['outputConfig'],
} satisfies WorkbenchPreset

// --- TaskProgressPayload -----------------------------------------------
// 前端进度条渲染依赖 current/total/percent + stage 三元;metrics 是
// 可选自由 bag(Phase D.2.3),不进硬契约。
const _TASK_PROGRESS_CONTRACT = {
  current: 0,
  total: 0,
  percent: 0,
  stage: '',
  stageIndex: 0,
  stageTotal: 0,
} satisfies TaskProgressPayload

// --- TaskErrorPayload --------------------------------------------------
// IPC 错误响应的硬形状:code 必须是 TaskErrorCode union,details 是
// `Record<string, unknown> | null` 而非 undefined / object literal。
const _TASK_ERROR_CONTRACT = {
  code: 'process_failed' as TaskErrorCode,
  message: '',
  details: null,
} satisfies TaskErrorPayload

// --- ResumeStatusPayload -----------------------------------------------
// `inspect-output` 命令的返回 payload,batch lifecycle 与续传 UI 依赖。
const _RESUME_STATUS_CONTRACT = {
  resumed: false,
  completedChunks: 0,
  completedOutputFrames: 0,
  startSourceFrame: 0,
  totalOutputFrames: 0,
} satisfies ResumeStatusPayload

// --- EnvironmentCheckPayload -------------------------------------------
// `check` 命令的环境探测结果,启动流程必读。result 内部结构由
// EnvironmentCheckResult 单独锁定(`@/types/generated/`),这里只断言外壳。
const _ENVIRONMENT_CHECK_CONTRACT = {
  result: {} as EnvironmentCheckPayload['result'],
  source: '',
  checkedAt: '',
} satisfies EnvironmentCheckPayload

void _TASK_REQUEST_CONTRACT
void _WORKBENCH_PRESET_CONTRACT
void _TASK_PROGRESS_CONTRACT
void _TASK_ERROR_CONTRACT
void _RESUME_STATUS_CONTRACT
void _ENVIRONMENT_CHECK_CONTRACT
