// 视图 form-binding — 素材列表编辑器(读 + mutation)。

import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'

export function useMediaListEditor() {
  const mediaStore = useMediaStore()

  const items = computed(() => mediaStore.mediaItems)
  const activeItem = computed(() => mediaStore.activeItem)
  const activeItemId = computed(() => mediaStore.activeItemId)
  const selectedIds = computed(() => mediaStore.selectedIds)
  const allSelected = computed(() => mediaStore.allSelected)

  return {
    items,
    activeItem,
    activeItemId,
    selectedIds,
    allSelected,
    selectAll: (selected: boolean) => mediaStore.selectAll(selected),
    setActive: (id: string) => mediaStore.setActive(id),
    setSelected: (id: string, selected: boolean) => mediaStore.setSelected(id, selected),
    removeItem: (id: string) => mediaStore.removeItem(id),
  }
}
