// 视图 form-binding — 素材列表编辑器(仅保留联动逻辑与格式化辅助)。
//
// Phase 16 — ``removeItem`` 同步触发 ``mediaRunState.dropItem`` —— 拆分后
// 运行时投影是独立 store,媒体被移除时它的 run-state 条目也必须释放,
// 否则在 ``useMediaRunState.state`` 里留下永不清理的孤儿(用户反复
// 导入/移除时累积成 memory leak)。
//
// Phase 1.4 — 删除所有直接透传 store 的 computed/method。视图直接消费
// ``useMediaStore``,减少无意义中间层。

import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { getWorkflowSummaryLabel } from '@/services/format/labels'
import type { MediaItem } from '@/types/domain/media'

function formatFps(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.01) {
    return `${Math.round(value)}`
  }
  return value.toFixed(2).replace(/\.?0+$/, '')
}

export function useMediaListEditor() {
  const mediaStore = useMediaStore()
  const runStateStore = useMediaRunState()

  function removeItem(id: string): void {
    mediaStore.removeItem(id)
    runStateStore.dropItem(id)
  }

  return {
    removeItem,
    fpsLabelOf: (item: MediaItem) =>
      item.info ? `${formatFps(item.info.fps)} FPS` : '--',
    workflowLabelOf: (item: MediaItem) => getWorkflowSummaryLabel(item),
  }
}
