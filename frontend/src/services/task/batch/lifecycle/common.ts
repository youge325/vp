// 共享辅助:current/console item 查找、批运行时清理。
//
// Phase 7a — lifecycle.ts 拆分时抽出的"无所属"辅助函数。queue /
// finalize / control 子模块都会用到这一组,把它单独成文件避免循环依赖
// (queue 调 finalize、finalize 调 queue,common 只被两边引用,自身
// 不引任何 lifecycle 子模块)。

import type { MediaItem } from '@/types/domain/media'

import type { BatchLifecycleDeps } from './types'

export interface CommonHelpers {
  getCurrentItem(): MediaItem | null
  getConsoleItem(): MediaItem | null
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

  function clearBatchRuntimeArtifacts(preserveLogs = false): void {
    deps.resetItemsRunState(new Set(deps.getRuntimeIds()), preserveLogs)
  }

  return { getCurrentItem, getConsoleItem, clearBatchRuntimeArtifacts }
}
