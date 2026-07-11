import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { DecodeConfig, EncodeConfig, OutputConfig, VideoInfo, WorkflowConfig } from '@/types/protocol'
import type { MediaItem } from '@/types/domain/media'

// Phase 6d — ``operationIssue`` / ``setOperationIssue`` /
// ``clearOperationIssue`` moved to the dedicated ``useIssueStore``
// (``@/stores/issue``). Media item state and global error-banner
// state used to share this file; splitting them keeps the media
// store focused on the media list itself.
//
// Phase 13.1 — ``taskState`` / ``issue`` / ``lastOutputPath`` 的写入路径
// 进一步迁出到 [[useMediaRunState]]。``useMediaStore`` 现在就是"list
// CRUD + 激活/选中 + info inspection"四件事,batch lifecycle 与 IPC
// 事件改往 ``mediaRunState`` 写入,视图侧读取也按 itemId 二级查找。
// 这样 batch-runner 注入函数从 13 个降到 8 个,store 关注点从 5 个降到 1 个。

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

  // Phase 17 — ``forEachEditableItem`` 下线(原来 grep 全仓 0 production callers,
  // 只有 ``getEditableTargetIds`` 真在用)。若将来需要遍历 editable items,
  // 直接在 caller 里写 `mediaItems.filter((item) => targetIds.has(item.id))`,
  // 不需要在 store 上暴露 callback 接口。

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
