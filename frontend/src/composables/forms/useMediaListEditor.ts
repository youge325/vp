// 视图 form-binding — 素材列表编辑器(读 + mutation)。
//
// Phase 16 — ``removeItem`` 同步触发 ``mediaRunState.dropItem`` —— 拆分后
// 运行时投影是独立 store,媒体被移除时它的 run-state 条目也必须释放,
// 否则在 ``useMediaRunState.state`` 里留下永不清理的孤儿(用户反复
// 导入/移除时累积成 memory leak)。

import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { formatNumber } from '@/services/format/numbers'
import { getWorkflowSummaryLabel } from '@/services/format/labels'
import type { MediaItem } from '@/types/domain/media'

export function useMediaListEditor() {
  const mediaStore = useMediaStore()
  const runStateStore = useMediaRunState()

  const items = computed(() => mediaStore.mediaItems)
  const activeItem = computed(() => mediaStore.activeItem)
  const activeItemId = computed(() => mediaStore.activeItemId)
  const selectedIds = computed(() => mediaStore.selectedIds)
  const allSelected = computed(() => mediaStore.allSelected)

  function removeItem(id: string): void {
    mediaStore.removeItem(id)
    runStateStore.dropItem(id)
  }

  return {
    items,
    activeItem,
    activeItemId,
    selectedIds,
    allSelected,
    fpsLabelOf: (item: MediaItem) =>
      item.info ? `${formatNumber(item.info.fps)} FPS` : '--',
    workflowLabelOf: (item: MediaItem) => getWorkflowSummaryLabel(item),
    selectAll: (selected: boolean) => mediaStore.selectAll(selected),
    setActive: (id: string) => mediaStore.setActive(id),
    setSelected: (id: string, selected: boolean) => mediaStore.setSelected(id, selected),
    removeItem,
  }
}
