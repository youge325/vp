import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'

export function useMediaList() {
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
