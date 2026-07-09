// 批生命周期 facade — 把 queue / finalize / control / common 装配成
// 与拆分前完全一致的 ``BatchLifecycle`` 公共接口。
//
// Phase 7a — 此前 ``lifecycle.ts`` 一个文件就是 321 LOC,把队列推进、
// 终态回收、控制信号、辅助查找都揉在一起。拆分后:
//   - ``common.ts``    getCurrentItem / getConsoleItem / clearBatchRuntimeArtifacts
//   - ``queue.ts``     start / runNextQueuedItem / launchCurrentItem
//   - ``finalize.ts``  finalizeCurrent / handleErrored
//   - ``control.ts``   pause / resume / cancel
//   - ``types.ts``     BatchLifecycleDeps / BatchLifecycle 接口
//   - ``index.ts``     这个文件,组装 + forward reference
//
// queue 与 finalize 互相调用(queue.runNextQueuedItem → finalize.handleErrored;
// finalize.finalizeCurrent → queue.runNextQueuedItem),通过先后初始化 +
// closure 在调用时 evaluate 完成 forward reference。

import { createCommonHelpers } from './common'
import { createControlOps } from './control'
import { createFinalizeOps } from './finalize'
import { createQueueOps } from './queue'
import type { BatchLifecycle, BatchLifecycleDeps } from './types'

export type { BatchLifecycle, BatchLifecycleDeps } from './types'

export function createBatchLifecycle(deps: BatchLifecycleDeps): BatchLifecycle {
  const helpers = createCommonHelpers(deps)

  // Forward reference: queue uses finalize, finalize uses queue.
  // We initialise both with ``let`` + closure indirection so each side
  // sees the fully-constructed sibling when it actually invokes the
  // delegated function (not at construction time).
  let finalizeOps: ReturnType<typeof createFinalizeOps>
  let queueOps: ReturnType<typeof createQueueOps>

  queueOps = createQueueOps(deps, helpers, {
    handleErrored: (error) => finalizeOps.handleErrored(error),
  })

  finalizeOps = createFinalizeOps(deps, helpers, {
    runNextQueuedItem: () => queueOps.runNextQueuedItem(),
  })

  const controlOps = createControlOps(deps, helpers)

  return {
    getCurrentItem: helpers.getCurrentItem,
    getConsoleItem: helpers.getConsoleItem,
    getCurrentRunState: helpers.getCurrentRunState,
    getConsoleRunState: helpers.getConsoleRunState,
    runNextQueuedItem: queueOps.runNextQueuedItem,
    launchCurrentItem: queueOps.launchCurrentItem,
    finalizeCurrent: finalizeOps.finalizeCurrent,
    handleErrored: finalizeOps.handleErrored,
    start: queueOps.start,
    pause: controlOps.pause,
    resume: controlOps.resume,
    cancel: controlOps.cancel,
  }
}
