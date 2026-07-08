// 应用层 — 批处理编排:把 batch-runner 与 stores、IPC 装配,提供 listener 桥。
//
// Runtime wiring lives in ``taskOrchestratorRuntime.ts`` so this composable
// can stay focused on UI-facing state projection and action methods.

import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import type { BatchRunner } from '@/services/task/batch-runner'
import { evaluateStartReadiness } from '@/services/task/preflight'
import {
  attachTaskListeners as attachRuntimeTaskListeners,
  getTaskRunner,
} from './taskOrchestratorRuntime'

export function useTaskOrchestrator() {
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()

  // ``storeToRefs`` keeps the reactive bindings for ref / computed fields
  // when callers destructure the returned object — without it,
  // ``pendingConflict`` would lose its reactivity at the destructure
  // site.
  const { pendingConflict } = storeToRefs(taskStore)

  const batch = taskStore.batch
  const currentTaskItem = computed(() =>
    mediaStore.mediaItems.find((item) => item.id === taskStore.batch.currentId) ?? null,
  )
  const consoleTaskItem = computed(() => currentTaskItem.value ?? mediaStore.activeItem)

  // Phase 18 — outputDir 强制必填。``canStartBatch`` 加 ``every(outputDir)``
  // guard,任一 selected item 的 outputConfig.outputDir 为 null 都阻止启动。
  // ``normalizeOutputDir`` 已保证空 / 纯空白写入前被转为 null,这里无需再 trim。
  // ``cannotStartReason`` 单点封装"按钮 disabled 时显示给用户的原因",让
  // RenderModuleView / StepRail 等 caller 无需重复算原因(避免多处 disabled
  // 文案漂移)。
  //
  // Phase A — 规则下沉到 ``services/task/preflight.ts``,这里只做投影。
  // 业务校验不再绑死 ``MediaItem`` schema,view / form 也可以复用同一规则。
  const preflightVerdict = computed(() =>
    evaluateStartReadiness({
      isRunning: taskStore.batch.isRunning,
      selectedItems: mediaStore.selectedItems.map((item) => ({
        displayName: item.displayName,
        inputPath: item.inputPath,
        outputDir: item.outputConfig.outputDir,
      })),
    }),
  )
  const canStartBatch = computed(() => preflightVerdict.value.ok)
  const cannotStartReason = computed(() => preflightVerdict.value.reason)
  const batchTotal = computed(() => taskStore.batchRuntimeIds.length || mediaStore.selectedItems.length)

  async function startBatch(): Promise<void> {
    if (!canStartBatch.value) {
      return
    }
    await getTaskRunner().start(mediaStore.selectedIds)
  }

  async function pauseCurrentTask(): Promise<void> {
    await getTaskRunner().pause()
  }

  async function resumeCurrentTask(): Promise<void> {
    await getTaskRunner().resume()
  }

  async function interruptBatch(): Promise<void> {
    await getTaskRunner().cancel()
  }

  async function resolveConflict(action: Parameters<BatchRunner['resolveConflict']>[0]): Promise<void> {
    await getTaskRunner().resolveConflict(action)
  }

  async function attachTaskListeners(): Promise<void> {
    await attachRuntimeTaskListeners()
  }

  // Phase 17 — ``detachTaskListeners`` 已从 public API 下线。production 端
  // 唯一关停入口是 ``disposeRunner``([[useBootstrap]] 在 onBeforeUnmount
  // 调用),既清 listener handle 又清 cached runner;暴露独立 detach 给
  // 任何 caller 反而是"任意 view 都能弄碎全局监听"的设计气味。
  //
  // ``cancelCurrentTask`` 也下线 —— 它只是 ``interruptBatch`` 的别名,无
  // production caller(grep 0 命中)。

  return {
    batch,
    pendingConflict,
    currentTaskItem,
    consoleTaskItem,
    canStartBatch,
    cannotStartReason,
    batchTotal,
    startBatch,
    pauseCurrentTask,
    resumeCurrentTask,
    interruptBatch,
    resolveConflict,
    attachTaskListeners,
  }
}
