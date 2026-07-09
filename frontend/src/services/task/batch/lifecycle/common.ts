// 共享辅助:current/console item 查找、批运行时清理。
//
// Phase 7a — lifecycle.ts 拆分时抽出的"无所属"辅助函数。queue /
// finalize / control 子模块都会用到这一组,把它单独成文件避免循环依赖
// (queue 调 finalize、finalize 调 queue,common 只被两边引用,自身
// 不引任何 lifecycle 子模块)。
//
// Phase 13.1 — 在 ``getCurrentItem`` / ``getConsoleItem`` 之外补两个
// ``…RunState`` 查找器,把 ``MediaItem`` 已经不再持有的运行时投影从
// ``useMediaRunState`` 取回。control / events / finalize 拿到 item 之后
// 想读 ``taskState`` 就走 ``helpers.getCurrentRunState()?.taskState ?? …``,
// 不需要每次再走一遍 ``deps.getItemRunState``。

import type { MediaItem, MediaRunState } from '@/types/domain/media'

import type { BatchLifecycleDeps } from './types'

interface CommonHelpers {
  getCurrentItem(): MediaItem | null
  getConsoleItem(): MediaItem | null
  getCurrentRunState(): MediaRunState | null
  getConsoleRunState(): MediaRunState | null
  clearBatchRuntimeArtifacts(preserveLogs?: boolean): void
}

export function createCommonHelpers(deps: BatchLifecycleDeps): CommonHelpers {
  function getCurrentItem(): MediaItem | null {
    const id = deps.getBatch().currentId
    return id ? deps.getMediaItem(id) : null
  }

  function getConsoleItem(): MediaItem | null {
    const current = getCurrentItem()
    if (current) {
      return current
    }
    const activeId = deps.getActiveItemId()
    return activeId ? deps.getMediaItem(activeId) : null
  }

  function getCurrentRunState(): MediaRunState | null {
    const id = deps.getBatch().currentId
    return id ? deps.getItemRunState(id) : null
  }

  function getConsoleRunState(): MediaRunState | null {
    const currentId = deps.getBatch().currentId
    if (currentId) {
      return deps.getItemRunState(currentId)
    }
    const activeId = deps.getActiveItemId()
    return activeId ? deps.getItemRunState(activeId) : null
  }

  function clearBatchRuntimeArtifacts(preserveLogs = false): void {
    deps.resetItemsRunState(new Set(deps.getRuntimeIds()), preserveLogs)
  }

  return {
    getCurrentItem,
    getConsoleItem,
    getCurrentRunState,
    getConsoleRunState,
    clearBatchRuntimeArtifacts,
  }
}
