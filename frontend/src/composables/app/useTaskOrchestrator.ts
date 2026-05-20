// 应用层 — 批处理编排:把 batch-runner 与 stores、IPC 装配,提供 listener 桥。
//
// Phase D.4.1 — runner / detach handle 提升到模块级单例。之前每个
// caller(useBootstrap / useStepRailState / useAppShellStatus /
// TaskConsole / RenderModuleView)都各自构造一个 BatchRunner closure,
// 跨 caller 调用 ``startBatch`` / ``pauseCurrentTask`` 时实际上各操作
// 不同实例,容易出现"以为在控制同一任务但其实是 R1/R2 各跑各的"。
// 现在 5 处 caller 共享同一 runner;listeners 也只挂一份。
//
// pinia store 本来就是单例,模块级缓存 runner 不会泄漏过期的 store 引用。
//
// Phase 7f — ADR 边界:
// - 单例的"持有方"是 *模块*,不是某个组件。组件只通过 ``useTaskOrchestrator()``
//   读取共享视图(views / computed),不拥有生命周期。
// - listener 绑定的所有权交给 ``useBootstrap`` —— 它是应用根组件的
//   composable,attach 在 ``onMounted``、detach 在 ``onBeforeUnmount``。
//   任何其他 caller 都不应主动 detach(注释里也写了);测试场景需要
//   完整重置(例如 ``setActivePinia`` 之后)时调用 ``disposeRunner``,
//   它会同时把 runner 与 detach handle 一并清掉,让下次 ``ensureRunner``
//   重新解析 Pinia store。

import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import type { UnlistenFn } from '@/lib/ipc'
import { listenTaskEvents } from '@/lib/ipc/events'
import { taskIpc } from '@/lib/ipc/endpoints/task'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'
import { createBatchRunner, type BatchRunner } from '@/services/task/batch-runner'
import { buildTaskRequest } from '@/services/task/request-builder'

// Module-level singletons. The factory in ``ensureRunner`` runs at most
// once per page load; subsequent calls (5 different composable sites)
// return the same instance.
let cachedRunner: BatchRunner | null = null
let detachHandle: UnlistenFn | null = null

function ensureRunner(): BatchRunner {
  if (cachedRunner) {
    return cachedRunner
  }
  // ``useXxxStore`` returns the pinia singleton, so resolving stores
  // here (instead of taking them as arguments) keeps the singleton
  // contract while preserving Pinia's lazy activation.
  //
  // Phase 13.1 — ``mediaRunState`` 是从 ``useMediaStore`` 拆出的运行时
  // 投影 store。``getItemRunState`` 把上一帧 taskState 暴露给 batch
  // lifecycle / events 做 reducer 输入,5 个 setter / reset 直写新 store。
  //
  // Phase 16 — ``setItemIssue`` 注入面下线,改注入 ``setTaskIssue`` 走
  // ``useIssueStore.setIssue('task', …)`` —— banner state 现在统一在
  // ``useIssueStore``,batch lifecycle 不再持有 per-item issue。
  const issueStore = useIssueStore()
  const mediaStore = useMediaStore()
  const mediaRunState = useMediaRunState()
  const taskStore = useTaskStore()
  cachedRunner = createBatchRunner({
    startTask: taskIpc.start,
    cancelTask: taskIpc.cancel,
    pauseTask: taskIpc.pause,
    resumeTask: taskIpc.resume,
    checkResume: taskIpc.checkResume,
    openOutputLocation: taskIpc.openOutputLocation,
    getMediaItem: (id) => mediaStore.findItem(id),
    getItemRunState: (id) => mediaRunState.getByItemId(id),
    setItemTaskState: (id, state) => mediaRunState.setTaskState(id, state),
    setTaskIssue: (issue) => {
      if (issue) {
        issueStore.setIssue('task', issue)
      } else {
        issueStore.clearIssue('task')
      }
    },
    setItemLastOutputPath: (id, path) => mediaRunState.setLastOutputPath(id, path),
    resetItemRunState: (id, preserveLogs) => mediaRunState.resetItemRunState(id, preserveLogs),
    resetItemsRunState: (ids, preserveLogs) => mediaRunState.resetItemsRunState(ids, preserveLogs),
    setActiveItem: (id) => mediaStore.setActive(id),
    getActiveItemId: () => mediaStore.activeItemId,
    getBatch: () => taskStore.batch,
    setBatch: (partial) => taskStore.setBatch(partial),
    getRuntimeIds: () => taskStore.batchRuntimeIds,
    setRuntimeIds: (ids) => taskStore.setRuntimeIds(ids),
    setPendingConflict: (descriptor) => taskStore.setPendingConflict(descriptor),
    buildRequest: (item, resumeMode) => buildTaskRequest(item, resumeMode),
  })
  return cachedRunner
}

/**
 * Tear down the module-level singleton so the next ``ensureRunner`` call
 * builds a fresh ``BatchRunner`` against whatever ``useXxxStore`` returns
 * at that point.
 *
 * Production code does not need this — the module lives as long as the
 * page does. It exists for:
 *   1. ``useBootstrap``'s ``onBeforeUnmount`` hook on the root component,
 *      so the app shutdown path doesn't leak the running listener.
 *   2. Tests that call ``setActivePinia(createPinia())`` between cases:
 *      without ``disposeRunner`` the cached runner still points at the
 *      previous Pinia's stores and every subsequent ``startBatch`` call
 *      writes to a detached store.
 *
 * Phase 7f — promoted from an internal detail of ``detachTaskListeners``
 * to a named export so the two callsites above can express intent.
 */
export function disposeRunner(): void {
  detachHandle?.()
  detachHandle = null
  cachedRunner = null
}

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
  const canStartBatch = computed(
    () =>
      !taskStore.batch.isRunning &&
      mediaStore.selectedItems.length > 0 &&
      mediaStore.selectedItems.every((item) => Boolean(item.inputPath)),
  )
  const batchTotal = computed(() => taskStore.batchRuntimeIds.length || mediaStore.selectedItems.length)

  async function startBatch(): Promise<void> {
    if (!canStartBatch.value) {
      return
    }
    await ensureRunner().start(mediaStore.selectedIds)
  }

  async function pauseCurrentTask(): Promise<void> {
    await ensureRunner().pause()
  }

  async function resumeCurrentTask(): Promise<void> {
    await ensureRunner().resume()
  }

  async function interruptBatch(): Promise<void> {
    await ensureRunner().cancel()
  }

  async function resolveConflict(action: Parameters<BatchRunner['resolveConflict']>[0]): Promise<void> {
    await ensureRunner().resolveConflict(action)
  }

  async function attachTaskListeners(): Promise<void> {
    // Idempotent across callers — only the first attach actually wires
    // the IPC listener; subsequent calls (e.g. from a remounted view)
    // are no-ops.
    if (detachHandle) {
      return
    }
    const runner = ensureRunner()
    detachHandle = await listenTaskEvents({
      onProgress: (payload) => runner.onProgress(payload),
      onLog: (payload) => runner.onLog(payload),
      onCompleted: (payload) => void runner.onCompleted(payload),
      onError: (error) => void runner.onError(error),
      onCancelled: (payload) => void runner.onCancelled(payload),
      onResumeStatus: (payload) => runner.onResumeStatus(payload),
    })
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
    batchTotal,
    startBatch,
    pauseCurrentTask,
    resumeCurrentTask,
    interruptBatch,
    resolveConflict,
    attachTaskListeners,
  }
}
