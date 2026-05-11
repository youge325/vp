import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig } from '@/types/protocol'
import type {
  MediaItem,
  MediaTaskState,
  OperationIssue,
  OperationIssueScope,
  TaskError,
  VideoInfoResult,
} from '@/types/domain/media'
import { createIdleTaskState } from '@/services/task/events'

export const useMediaStore = defineStore('media', () => {
  const mediaItems = ref<MediaItem[]>([])
  const activeItemId = ref<string | null>(null)
  const operationIssue = ref<OperationIssue | null>(null)

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

  function forEachEditableItem(callback: (item: MediaItem) => void): void {
    const targetIds = getEditableTargetIds()
    for (const item of mediaItems.value) {
      if (targetIds.has(item.id)) {
        callback(item)
      }
    }
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

  function setItemInfo(id: string, info: VideoInfoResult | null): void {
    const item = findItem(id)
    if (item) {
      item.info = info
    }
  }

  function setItemIssue(id: string, issue: TaskError | null): void {
    const item = findItem(id)
    if (item) {
      item.issue = issue
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

  function setItemTaskState(id: string, state: MediaTaskState): void {
    const item = findItem(id)
    if (item) {
      item.taskState = state
    }
  }

  function setItemLastOutputPath(id: string, path: string): void {
    const item = findItem(id)
    if (item) {
      item.lastOutputPath = path
    }
  }

  function resetItemRunState(id: string, preserveLogs = false): void {
    const item = findItem(id)
    if (!item) {
      return
    }
    const existingLogs = preserveLogs ? item.taskState.logs : []
    item.taskState = { ...createIdleTaskState(), logs: existingLogs }
    item.issue = null
    item.lastOutputPath = ''
  }

  function resetItemsRunState(ids: Set<string>, preserveLogs = false): void {
    for (const item of mediaItems.value) {
      if (ids.has(item.id)) {
        resetItemRunState(item.id, preserveLogs)
      }
    }
  }

  function setOperationIssue(scope: OperationIssueScope, error: TaskError): void {
    operationIssue.value = { scope, error }
  }

  function clearOperationIssue(scope?: OperationIssueScope): void {
    if (!scope || operationIssue.value?.scope === scope) {
      operationIssue.value = null
    }
  }

  return {
    mediaItems,
    activeItemId,
    operationIssue,
    selectedIds,
    selectedItems,
    activeItem,
    allSelected,
    findItem,
    getEditableTargetIds,
    forEachEditableItem,
    appendItems,
    removeItem,
    setActive,
    setSelected,
    selectAll,
    setInspecting,
    setItemInfo,
    setItemIssue,
    replaceItemConfig,
    setItemTaskState,
    setItemLastOutputPath,
    resetItemRunState,
    resetItemsRunState,
    setOperationIssue,
    clearOperationIssue,
  }
})
