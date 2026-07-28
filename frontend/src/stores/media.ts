import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { DecodeConfig, EncodeConfig, OutputConfig, VideoInfo, WorkflowConfig } from '@/types/protocol'
import type { MediaItem } from '@/types/domain/media'

// 只管理媒体列表、激活项、选中项与探测结果。运行状态和用户可见错误
// 分别由 ``useMediaRunState`` 与 ``useIssueStore`` 管理。

export const useMediaStore = defineStore('media', () => {
  const mediaItems = ref<MediaItem[]>([])
  const activeItemId = ref<string | null>(null)

  const selectedIds = computed(() => mediaItems.value.filter((item) => item.selected).map((item) => item.id))
  const selectedItems = computed(() => mediaItems.value.filter((item) => item.selected))
  const activeItem = computed(() => mediaItems.value.find((item) => item.id === activeItemId.value) ?? null)
  const allSelected = computed(
    () => mediaItems.value.length > 0 && mediaItems.value.every((item) => item.selected),
  )

  function findItem(id: string | null): MediaItem | null {
    if (!id) {
      return null
    }
    return mediaItems.value.find((item) => item.id === id) ?? null
  }

  function getEditableTargetIds(): Set<string> {
    const targetIds = new Set<string>(selectedIds.value)
    if (activeItemId.value) {
      targetIds.add(activeItemId.value)
    }
    return targetIds
  }

  function appendItems(items: MediaItem[]): void {
    if (items.length === 0) {
      return
    }
    mediaItems.value.push(...items)
    if (!activeItemId.value) {
      activeItemId.value = items[0]?.id ?? null
    }
  }

  function removeItem(id: string): void {
    const index = mediaItems.value.findIndex((item) => item.id === id)
    if (index < 0) {
      return
    }
    mediaItems.value.splice(index, 1)
    if (activeItemId.value === id) {
      activeItemId.value = mediaItems.value[0]?.id ?? null
    }
  }

  function setActive(id: string | null): void {
    if (id === null) {
      activeItemId.value = null
      return
    }
    if (findItem(id)) {
      activeItemId.value = id
    }
  }

  function setSelected(id: string, selected: boolean): void {
    const item = findItem(id)
    if (item) {
      item.selected = selected
    }
  }

  function selectAll(selected: boolean): void {
    for (const item of mediaItems.value) {
      item.selected = selected
    }
  }

  function setInspecting(id: string, inspecting: boolean): void {
    const item = findItem(id)
    if (item) {
      item.inspecting = inspecting
    }
  }

  function setItemInfo(id: string, info: VideoInfo | null): void {
    const item = findItem(id)
    if (item) {
      item.info = info
    }
  }

  function replaceItemConfig(
    id: string,
    partial: {
      decodeConfig?: DecodeConfig
      encodeConfig?: EncodeConfig
      workflowConfig?: WorkflowConfig
      outputConfig?: OutputConfig
    },
  ): void {
    const item = findItem(id)
    if (!item) {
      return
    }
    if (partial.decodeConfig) item.decodeConfig = partial.decodeConfig
    if (partial.encodeConfig) item.encodeConfig = partial.encodeConfig
    if (partial.workflowConfig) item.workflowConfig = partial.workflowConfig
    if (partial.outputConfig) item.outputConfig = partial.outputConfig
  }

  return {
    mediaItems,
    activeItemId,
    selectedIds,
    selectedItems,
    activeItem,
    allSelected,
    findItem,
    getEditableTargetIds,
    appendItems,
    removeItem,
    setActive,
    setSelected,
    selectAll,
    setInspecting,
    setItemInfo,
    replaceItemConfig,
  }
})
